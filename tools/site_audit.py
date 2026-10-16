"""Resumable, rate-limited public ShiaArts research crawler.

Examples:
  python work/site_audit.py inventory --max-requests 20
  python work/site_audit.py crawl --mode all
  python work/site_audit.py status
  python work/site_audit.py export
  python work/site_audit.py review-export

Only displayed artwork images are downloaded; archival /file downloads are
recorded as metadata, never requested. A cached image is not a visual review.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from PIL import Image


BASE = "https://shiaarts.ir"
WORK = Path(__file__).resolve().parent
OUTPUT = WORK.parent / "outputs" / "shiaarts-research"
USER_AGENT = "ShiaArtsResearch/1.0 (public artwork inventory; sequential GET; 10s minimum delay)"
ART_SELECTOR = ".node-dexp-portfolio, .node-blog"
FIELD_NAMES = {
    "field-portfolio-categories": "subjects",
    "field-style": "execution_techniques",
    "field-teknikha": "art_branches",
    "field-artist": "artists",
    "field-era": "creation_era",
}
SENSITIVE_QUERY_KEYS = {"token", "access_token", "api_key", "apikey", "password", "secret", "session", "sid"}
SEEDS = (
    ("source-home.html", BASE + "/", "listing", 0),
    ("source-categories.html", BASE + "/Categories", "taxonomy", 1),
    ("source-graphics.html", BASE + "/taxonomy/term/105", "listing", 2),
    ("source-artists.html", BASE + "/jebhe", "listing", 3),
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def compact_text(element):
    return " ".join(element.get_text(" ", strip=True).split()) if element else ""


def normalized_url(value, source=BASE):
    if not value or value.startswith(("#", "javascript:", "mailto:", "tg:", "data:")):
        return None
    parsed = urlsplit(urljoin(source, value))
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("shiaarts.ir", "www.shiaarts.ir"):
        return None
    path = quote(unquote(parsed.path or "/"), safe="/!$&'()*+,-.:;=@_~")
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    if path == "/node" and not query:
        path = "/"
    return urlunsplit(("https", "shiaarts.ir", path, query, ""))


def public_url(url, asset=False):
    parsed = urlsplit(url)
    if normalized_url(url) != url:
        return False
    path = unquote(parsed.path)
    if asset:
        return path.startswith("/sites/default/files/") and "/private/" not in path
    if path == "/robots.txt":
        return True
    if any(key not in ("page", "destination") for key, _ in parse_qsl(parsed.query)):
        return False
    if path.startswith(("/file/", "/sites/", "/modules/", "/misc/", "/admin", "/user", "/flag/", "/search", "/views/", "/system/")):
        return False
    # Drupal taxonomy and gallery aliases may be Persian paths after a redirect.
    # Keep public content paths in scope while rejecting known action/private paths
    # above; robots.txt remains the final permission gate for network requests.
    return bool(path == "/" or path.strip("/") or re.fullmatch(r"/node/\d+", path))


def safe_download_reference(url):
    """Keep a public file path but never persist a secret query value."""
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    redacted = [(key, value) for key, value in query if key.lower() not in SENSITIVE_QUERY_KEYS]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(redacted), parsed.fragment)), any(key.lower() in SENSITIVE_QUERY_KEYS for key, _ in query)


def safe_export(value):
    if isinstance(value, dict):
        return {key: safe_export(item) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_export(item) for item in value]
    if isinstance(value, str) and value.startswith((BASE, "http://shiaarts.ir", "https://www.shiaarts.ir")):
        return safe_download_reference(value)[0]
    return value


def own_node(element, root):
    parent = element.find_parent(class_=lambda classes: classes and "node" in classes.split())
    return parent is root


def own_fields(root):
    return [element for element in root.select(".field") if own_node(element, root)]


def node_identity(node):
    matched = re.fullmatch(r"node-(\d+)", node.get("id", ""))
    if matched:
        return "node:" + matched.group(1)
    about = normalized_url(node.get("about"))
    return "url:" + about if about else None


def node_title(node):
    metadata = next((element for element in node.find_all(attrs={"property": "dc:title"}) if own_node(element, node)), None)
    if metadata and metadata.get("content"):
        return metadata["content"].strip()
    heading = next((element for element in node.select("h1, h2, h3, .title") if own_node(element, node)), None)
    return compact_text(heading)


def image_attributes(image, source):
    url = normalized_url(image.get("src") or image.get("data-src"), source)
    if not url or not public_url(url, asset=True):
        return None
    url, secret_present = safe_download_reference(url)
    if secret_present:
        return None
    def integer(value):
        return int(value) if str(value or "").isdigit() else None
    return {
        "url": url,
        "alt": image.get("alt", ""),
        "title": image.get("title", ""),
        "html_width": integer(image.get("width")),
        "html_height": integer(image.get("height")),
        "role": "displayed_artwork",
        "pixel_dimensions_verified": False,
    }


def listing_nodes(soup, source):
    records = []
    for node in soup.select(ART_SELECTOR):
        identity = node_identity(node)
        if not identity:
            continue
        about = normalized_url(node.get("about"), source)
        if not about:
            about = normalized_url(next((a["href"] for a in node.select("a[href]") if "/gallery/" in a["href"] or "/jebhe/" in a["href"]), ""), source)
        if not about or not public_url(about):
            continue
        records.append({
            "id": identity,
            "node_id": identity[5:] if identity.startswith("node:") else None,
            "source_url": about,
            "title": node_title(node),
            "collection": "community" if "node-blog" in node.get("class", []) else "gallery",
            "discovered_from": source,
        })
    return records


def listing_pagers(soup, source):
    targets = set()
    for anchor in soup.select("a[href]"):
        target = normalized_url(anchor["href"], source)
        if not target or not public_url(target) or "page=" not in target:
            continue
        path = urlsplit(target).path
        source_path = urlsplit(source).path
        if path == source_path or path == "/node" and source_path in ("/", "/node"):
            targets.add(target)
    return sorted(targets)


def taxonomy_terms(soup, source):
    terms = []
    for panel in soup.select(".panel"):
        heading = compact_text(panel.select_one(".panel-title"))
        for anchor in panel.select('a[href*="/taxonomy/term/"]'):
            target = normalized_url(anchor["href"], source)
            if not target or not re.fullmatch(r"/taxonomy/term/\d+", urlsplit(target).path):
                continue
            terms.append({
                "id": urlsplit(target).path.rsplit("/", 1)[-1],
                "name": compact_text(anchor),
                "group": heading,
                "is_artist": "هنرمندان" in heading or "خالقان" in heading,
                "source_url": target,
                "discovered_from": source,
            })
    return terms


def parse_detail(html, source, expected_id=None):
    soup = BeautifulSoup(html, "html.parser")
    roots = soup.select(ART_SELECTOR)
    if expected_id:
        root = next((node for node in roots if node_identity(node) == expected_id), None)
    else:
        root = roots[0] if roots else None
    if not root:
        raise ValueError("Expected artwork node absent; refusing to parse recommendations as artwork")
    fields = own_fields(root)
    metadata = {}
    exact_fields = []
    for field in fields:
        classes = field.get("class", [])
        name = next((value[11:] for value in classes if value.startswith("field-name-")), "")
        label = compact_text(field.select_one(".field-label"))
        items = field.select(".field-items > .field-item")
        values = []
        for item in items:
            lineage = item.select(".lineage-item")
            texts = [compact_text(value) for value in lineage] if lineage else [compact_text(item)]
            links = [{"label": compact_text(anchor), "url": normalized_url(anchor["href"], source)} for anchor in item.select("a[href]")]
            values.append({"text": compact_text(item), "lineage": texts, "links": links})
        if name in FIELD_NAMES:
            metadata[FIELD_NAMES[name]] = values
        exact_fields.append({"name": name, "label": label, "values": values})
    images = []
    seen = set()
    for field in fields:
        classes = " ".join(field.get("class", []))
        name = next((value[11:] for value in field.get("class", []) if value.startswith("field-name-")), "")
        if not ("field-portfolio-images" in classes or name in ("field-image", "field-blog-image", "field-images", "field-blog-images")):
            continue
        for image in field.select("img"):
            candidate = image_attributes(image, source)
            if candidate and candidate["url"] not in seen:
                candidate["position"] = len(images) + 1
                candidate["field_name"] = name
                images.append(candidate)
                seen.add(candidate["url"])
    body_fields = [field for field in fields if "field-name-body" in field.get("class", [])]
    if "node-blog" in root.get("class", []):
        for field in body_fields:
            for image in field.select("img"):
                candidate = image_attributes(image, source)
                if candidate and candidate["url"] not in seen:
                    candidate["position"] = len(images) + 1
                    candidate["field_name"] = "body"
                    images.append(candidate)
                    seen.add(candidate["url"])
        for image in root.select(".media_element > figure > img"):
            candidate = image_attributes(image, source)
            if candidate and candidate["url"] not in seen:
                candidate["position"] = len(images) + 1
                candidate["field_name"] = "media_element"
                images.append(candidate)
                seen.add(candidate["url"])
    descriptions = [field.get_text("\n", strip=True) for field in body_fields]
    downloads = []
    seen_downloads = set()
    for anchor in root.select('a[href*="/file/"][href*="/download"]'):
        if not own_node(anchor, root):
            continue
        target = normalized_url(anchor["href"], source)
        if target in seen_downloads:
            continue
        seen_downloads.add(target)
        file_span = anchor.find_parent(class_="file")
        size = file_span.select_one(".file-size") if file_span else None
        safe_target, secret_present = safe_download_reference(target)
        downloads.append({"url": safe_target, "sensitive_query_redacted": secret_present, "label": compact_text(anchor), "declared_type": anchor.get("type"), "declared_size": compact_text(size) or None, "downloaded": False})
    canonical = soup.find("link", rel="canonical")
    source_url = normalized_url(canonical.get("href"), source) if canonical else normalized_url(root.get("about"), source) or source
    publication = next((element for element in root.select(".date-created") if own_node(element, root)), None)
    copyright_element = next((element for element in root.select(".copyright-works") if own_node(element, root)), None)
    uploader = next((element for element in root.select('.submitted, .username, [property="sioc:name"]') if own_node(element, root)), None)
    explicit_occasions = []
    physical_sizes = []
    for field in exact_fields:
        if any(term in field["label"] or term in field["name"] for term in ("مناسبت", "occasion", "event")):
            explicit_occasions.append(field)
        if any(term in field["label"] or term in field["name"] for term in ("ابعاد", "اندازه اثر", "dimensions", "physical-size", "print-size")):
            physical_sizes.append(field)
    return {
        "id": node_identity(root),
        "node_id": root.get("id", "").removeprefix("node-") or None,
        "source_url": source_url,
        "requested_url": source,
        "title": node_title(root),
        "collection": "community" if "node-blog" in root.get("class", []) else "gallery",
        "checked_at": utc_now(),
        **metadata,
        "exact_fields": exact_fields,
        "description": "\n\n".join(descriptions),
        "publication_date_source_text": compact_text(publication) or None,
        "uploader_source_text": compact_text(uploader) or None,
        "author_attribution": "explicit_artist_field" if metadata.get("artists") else "unknown_not_inferred_from_uploader",
        "occasion": {"explicit_source_fields": explicit_occasions, "inferred": [], "status": "explicit" if explicit_occasions else "not_explicitly_stated"},
        "physical_dimensions": {"explicit_source_fields": physical_sizes, "status": "explicit" if physical_sizes else "unknown", "not_derived_from_image_pixels": True},
        "copyright_source_text": compact_text(copyright_element) or None,
        "archival_downloads_metadata_only": downloads,
        "images": images,
        "visual_review": {"status": "pending", "reviewed_image_positions": [], "evidence_path": None},
        "series": {"status": "unknown", "explicit_source_fields": []},
    }


class RobotsRules:
    def __init__(self, text, agent=USER_AGENT):
        self.rules = []
        self.delay = 10.0
        groups = []
        agents = []
        rules = []
        delays = []
        has_directive = False
        for raw in text.splitlines() + ["User-agent: __end__"]:
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if has_directive:
                    groups.append((agents, rules, delays))
                    agents, rules, delays, has_directive = [], [], [], False
                agents.append(value.lower())
            elif agents and key in ("allow", "disallow", "crawl-delay"):
                has_directive = True
                if key == "crawl-delay":
                    try:
                        delays.append(float(value))
                    except ValueError:
                        pass
                elif value:
                    rules.append((key == "allow", value))
        matching = [(max((len(value) for value in names if value != "*" and value in agent.lower()), default=0), names, entries, delays) for names, entries, delays in groups if "*" in names or any(value in agent.lower() for value in names)]
        if matching:
            specificity = max(value[0] for value in matching)
            for score, _, entries, delays in matching:
                if score == specificity:
                    self.rules.extend(entries)
                    self.delay = max([self.delay] + delays)

    def allowed(self, url):
        parsed = urlsplit(url)
        target = unquote(parsed.path + ("?" + parsed.query if parsed.query else ""))
        matches = []
        for allow, pattern in self.rules:
            end = pattern.endswith("$")
            expression = "^" + re.escape(unquote(pattern.rstrip("$") if end else pattern)).replace(r"\*", ".*") + ("$" if end else "")
            if re.search(expression, target):
                matches.append((len(pattern.replace("*", "").rstrip("$")), allow))
        return max(matches, default=(0, True))[1]


@contextmanager
def file_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.25)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class CrawlStopped(RuntimeError):
    pass


class BudgetReached(CrawlStopped):
    pass


class PublicClient:
    def __init__(self, work, max_requests=None):
        self.work = Path(work)
        self.cache = self.work / "http-cache"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.max_requests = max_requests
        self.request_count = 0
        self.rules = None
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,image/*;q=0.9,text/plain;q=0.8"})

    def paths(self, url):
        key = hashlib.sha256(url.encode()).hexdigest()
        return self.cache / (key + ".body"), self.cache / (key + ".json")

    def cached(self, url):
        body, metadata = self.paths(url)
        if body.exists() and metadata.exists():
            info = json.loads(metadata.read_text(encoding="utf8"))
            if info.get("status") == 200:
                return body.read_bytes(), info
        return None

    def import_fixture(self, path, url):
        if self.cached(url):
            return
        body, metadata = self.paths(url)
        body.write_bytes(path.read_bytes())
        metadata.write_text(json.dumps({"url": url, "final_url": url, "status": 200, "content_type": "text/html; charset=utf-8", "checked_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(), "imported_fixture": str(path), "sha256": hashlib.sha256(body.read_bytes()).hexdigest()}, ensure_ascii=False, indent=2), encoding="utf8")

    def ensure_robots(self):
        if self.rules is not None:
            return
        body, info = self.get(BASE + "/robots.txt", robots=True)
        if info["status"] in (401, 403):
            raise CrawlStopped("robots.txt denies access")
        if info["status"] == 404:
            self.rules = RobotsRules("")
        elif info["status"] == 200:
            self.rules = RobotsRules(body.decode("utf8", errors="replace"))
        else:
            raise CrawlStopped("robots.txt unavailable; refusing to guess permission")

    def defer(self, seconds):
        clock = self.work / "crawl-clock.json"
        with file_lock(self.work / "crawl-clock.lock"):
            state = json.loads(clock.read_text(encoding="utf8")) if clock.exists() else {}
            state["not_before"] = max(state.get("not_before", 0), time.time() + seconds)
            clock.write_text(json.dumps(state), encoding="utf8")

    def request(self, url):
        if self.max_requests is not None and self.request_count >= self.max_requests:
            raise BudgetReached("Per-run network request budget reached")
        with file_lock(self.work / "crawl-clock.lock"):
            clock = self.work / "crawl-clock.json"
            state = json.loads(clock.read_text(encoding="utf8")) if clock.exists() else {}
            delay = max(10, self.rules.delay if self.rules else 10)
            wait = max(state.get("last_started", 0) + delay, state.get("not_before", 0)) - time.time()
            if wait > 0:
                time.sleep(wait)
            state["last_started"] = time.time()
            state["last_url"] = url
            clock.write_text(json.dumps(state), encoding="utf8")
            self.request_count += 1
            response = self.session.get(url, timeout=(20, 90), allow_redirects=False, stream=True)
            chunks = []
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 40 * 1024 * 1024:
                    response.close()
                    raise CrawlStopped("Public response exceeds 40 MiB safety bound")
                chunks.append(chunk)
            response.close()
            return response, b"".join(chunks)

    def get(self, url, asset=False, robots=False):
        if not public_url(url, asset=asset):
            raise CrawlStopped("Rejected non-public or out-of-scope URL: " + url)
        cached = self.cached(url)
        if cached:
            return cached
        if not robots:
            self.ensure_robots()
            if not self.rules.allowed(url):
                raise PermissionError("robots.txt disallows: " + url)
        requested = url
        redirects = 0
        for attempt in range(3):
            try:
                response, content = self.request(url)
            except requests.RequestException as error:
                if attempt == 2:
                    raise CrawlStopped("Network retries exhausted: " + type(error).__name__) from error
                self.defer(20 * (attempt + 1))
                continue
            status = response.status_code
            if status in (301, 302, 303, 307, 308):
                target = normalized_url(response.headers.get("Location"), url)
                if not target or not public_url(target, asset=asset) or redirects >= 4:
                    raise CrawlStopped("Unsafe or excessive redirect rejected")
                if not robots and not self.rules.allowed(target):
                    raise PermissionError("robots.txt disallows redirect: " + target)
                url = target
                redirects += 1
                if attempt == 2:
                    raise CrawlStopped("Redirect bound reached; inspect source URL")
                continue
            if status == 429 or status in (500, 502, 503, 504):
                retry_after = response.headers.get("Retry-After", "")
                try:
                    pause = float(retry_after)
                except ValueError:
                    try:
                        pause = parsedate_to_datetime(retry_after).timestamp() - time.time()
                    except (ValueError, TypeError, OverflowError):
                        pause = 30 * (attempt + 1)
                self.defer(max(10, pause))
                if pause > 3600:
                    raise CrawlStopped("Server requested Retry-After over one hour; deferred persistently")
                if attempt == 2:
                    raise CrawlStopped("HTTP retry limit reached: " + str(status))
                continue
            if status in (401, 403) and not robots:
                raise CrawlStopped("Public request denied with HTTP " + str(status) + "; no authentication attempted")
            info = {"url": requested, "final_url": url, "status": status, "content_type": response.headers.get("Content-Type", ""), "checked_at": utc_now(), "sha256": hashlib.sha256(content).hexdigest()}
            body_path, metadata_path = self.paths(requested)
            if status == 200:
                body_path.write_bytes(content)
            metadata_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf8")
            return content, info
        raise CrawlStopped("Unexpected request loop termination")


class Audit:
    def __init__(self, work=WORK, output=OUTPUT, max_requests=None, scope="all"):
        self.work = Path(work)
        self.output = Path(output)
        self.work.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.work / "site-audit.sqlite3", timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS pages(url TEXT PRIMARY KEY, kind TEXT NOT NULL, priority INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'pending', source TEXT, checked_at TEXT, item_count INTEGER, pager_count INTEGER, error TEXT, attempts INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS works(id TEXT PRIMARY KEY, node_id TEXT, source_url TEXT NOT NULL, title TEXT, collection TEXT, state TEXT NOT NULL DEFAULT 'pending', metadata TEXT, checked_at TEXT, error TEXT);
            CREATE TABLE IF NOT EXISTS discoveries(work_id TEXT NOT NULL, source_url TEXT NOT NULL, PRIMARY KEY(work_id,source_url));
            CREATE TABLE IF NOT EXISTS aliases(url TEXT PRIMARY KEY, work_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS taxonomy(id TEXT PRIMARY KEY, name TEXT, group_name TEXT, is_artist INTEGER, source_url TEXT, discovered_from TEXT);
            CREATE TABLE IF NOT EXISTS assets(url TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'pending', local_path TEXT, sha256 TEXT, width INTEGER, height INTEGER, format TEXT, mode TEXT, bytes INTEGER, checked_at TEXT, error TEXT);
            CREATE TABLE IF NOT EXISTS work_assets(work_id TEXT NOT NULL, position INTEGER NOT NULL, url TEXT NOT NULL, metadata TEXT, PRIMARY KEY(work_id,position));
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        """)
        self.client = PublicClient(self.work, max_requests=max_requests)
        self.scope = scope

    def enqueue(self, url, kind="listing", priority=20, source=None):
        if url and public_url(url):
            self.db.execute("INSERT OR IGNORE INTO pages(url,kind,priority,source) VALUES (?,?,?,?)", (url, kind, priority, source))

    def seed(self):
        for filename, url, kind, priority in SEEDS:
            if self.scope == "graphics" and url in (BASE + "/", BASE + "/jebhe"):
                continue
            fixture = self.work / filename
            if not fixture.exists() and filename == "source-home.html":
                fixture = self.work / "home.html"
            if fixture.exists():
                self.client.import_fixture(fixture, url)
            self.enqueue(url, kind, priority)
        for fixture in sorted(self.work.glob("source-*-detail.html")):
            soup = BeautifulSoup(fixture.read_bytes(), "html.parser")
            root = soup.select_one(ART_SELECTOR)
            if root:
                target = normalized_url(root.get("about"))
                if target and public_url(target):
                    self.client.import_fixture(fixture, target)
        self.db.execute("INSERT OR REPLACE INTO settings VALUES ('scope',?)", (self.scope,))
        self.db.commit()

    def ingest_nodes(self, soup, source):
        records = listing_nodes(soup, source)
        for record in records:
            self.db.execute("INSERT OR IGNORE INTO works(id,node_id,source_url,title,collection) VALUES (?,?,?,?,?)", (record["id"], record["node_id"], record["source_url"], record["title"], record["collection"]))
            self.db.execute("INSERT OR IGNORE INTO aliases VALUES (?,?)", (record["source_url"], record["id"]))
            if record["node_id"]:
                self.db.execute("INSERT OR IGNORE INTO aliases VALUES (?,?)", (BASE + "/node/" + record["node_id"], record["id"]))
            self.db.execute("INSERT OR IGNORE INTO discoveries VALUES (?,?)", (record["id"], source))
        return len(records)

    def process_listing(self, row):
        content, info = self.client.get(row["url"])
        if info["status"] != 200:
            raise ValueError("Listing HTTP " + str(info["status"]))
        if "html" not in info.get("content_type", "").lower():
            raise ValueError("Listing returned non-HTML response")
        soup = BeautifulSoup(content, "html.parser")
        if not soup.find("body"):
            raise ValueError("Listing lacks HTML body; terminal page not proven")
        if soup.select_one('input[type="password"], form#user-login'):
            raise ValueError("Authentication page returned; no login attempted")
        count = self.ingest_nodes(soup, row["url"])
        pagers = listing_pagers(soup, row["url"])
        for target in pagers:
            self.enqueue(target, "listing", row["priority"] + 1, row["url"])
        if row["kind"] == "taxonomy":
            for term in taxonomy_terms(soup, row["url"]):
                self.db.execute("INSERT OR REPLACE INTO taxonomy VALUES (?,?,?,?,?,?)", (term["id"], term["name"], term["group"], int(term["is_artist"]), term["source_url"], term["discovered_from"]))
                if self.scope == "all" or term["id"] == "105":
                    # Close the canonical home/community listing streams first.
                    # Taxonomy pages are a secondary discovery cross-check and can
                    # number in the hundreds, so they must not starve pagination.
                    priority = 100 if term["is_artist"] else 110
                    self.enqueue(term["source_url"], "listing", priority, row["url"])
        self.db.execute("UPDATE pages SET state='done', checked_at=?, item_count=?, pager_count=?, error=NULL, attempts=attempts+1 WHERE url=?", (info["checked_at"], count, len(pagers), row["url"]))
        self.db.commit()

    def process_detail(self, row):
        content, info = self.client.get(row["source_url"])
        if info["status"] != 200:
            raise ValueError("Artwork HTTP " + str(info["status"]))
        record = parse_detail(content, row["source_url"], row["id"])
        record["checked_at"] = info["checked_at"]
        self.ingest_nodes(BeautifulSoup(content, "html.parser"), row["source_url"])
        self.db.execute("INSERT OR IGNORE INTO aliases VALUES (?,?)", (record["source_url"], row["id"]))
        self.db.execute("DELETE FROM work_assets WHERE work_id=?", (row["id"],))
        for candidate in record["images"]:
            self.db.execute("INSERT OR IGNORE INTO assets(url) VALUES (?)", (candidate["url"],))
            self.db.execute("INSERT OR REPLACE INTO work_assets VALUES (?,?,?,?)", (row["id"], candidate["position"], candidate["url"], json.dumps(candidate, ensure_ascii=False)))
        self.db.execute("UPDATE works SET state='done', metadata=?,checked_at=?,error=NULL WHERE id=?", (json.dumps(record, ensure_ascii=False), record["checked_at"], row["id"]))
        self.db.commit()

    def process_asset(self, row):
        content, info = self.client.get(row["url"], asset=True)
        if info["status"] != 200:
            raise ValueError("Image HTTP " + str(info["status"]))
        with Image.open(io.BytesIO(content)) as artwork_image:
            artwork_image.verify()
        with Image.open(io.BytesIO(content)) as artwork_image:
            width, height = artwork_image.size
            image_format, mode = artwork_image.format, artwork_image.mode
        digest = hashlib.sha256(content).hexdigest()
        extension = {"JPEG": ".jpg", "PNG": ".png", "GIF": ".gif", "WEBP": ".webp", "TIFF": ".tif"}.get(image_format, ".img")
        directory = self.work / "assets"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (digest + extension)
        if not path.exists():
            path.write_bytes(content)
        self.db.execute("UPDATE assets SET state='done',local_path=?,sha256=?,width=?,height=?,format=?,mode=?,bytes=?,checked_at=?,error=NULL WHERE url=?", (str(path), digest, width, height, image_format, mode, len(content), info["checked_at"], row["url"]))
        self.db.commit()

    def retry_errors(self):
        self.db.execute("UPDATE pages SET state='pending' WHERE state='error'")
        self.db.execute("UPDATE works SET state='pending' WHERE state='error'")
        self.db.execute("UPDATE assets SET state='pending' WHERE state='error'")
        self.db.commit()

    def next_task(self, command, mode, step):
        listing = self.db.execute("SELECT * FROM pages WHERE state='pending' ORDER BY priority,url LIMIT 1").fetchone()
        detail = self.db.execute("SELECT * FROM works WHERE state='pending' ORDER BY CASE collection WHEN 'gallery' THEN 0 ELSE 1 END, CAST(node_id AS INTEGER) DESC LIMIT 1").fetchone() if command != "inventory" and mode != "assets" else None
        asset = self.db.execute("SELECT * FROM assets WHERE state='pending' ORDER BY rowid LIMIT 1").fetchone() if command != "inventory" and mode in ("assets", "all") else None
        if command == "crawl" and mode == "assets":
            return ("asset", asset) if asset else (None, None)
        # Taxonomy cross-check pages are useful for discovery but can starve the
        # detail/image pass (there are hundreds). During crawl, process a pending
        # artwork before secondary taxonomy pages; inventory mode remains strict
        # and closes every listing page on its own.
        if command == "crawl" and listing and detail:
            listing_path = urlsplit(listing["url"]).path
            if listing_path.startswith("/taxonomy/term/") and listing_path != "/taxonomy/term/105":
                if asset and step % 40 == 39:
                    return "asset", asset
                return "detail", detail
        if listing and asset and step % 40 == 39:
            return "asset", asset
        if listing and detail and step % 20 == 19:
            return "detail", detail
        if listing:
            return "listing", listing
        if detail and asset:
            return ("asset", asset) if step % 2 else ("detail", detail)
        return ("detail", detail) if detail else (("asset", asset) if asset else (None, None))

    def crawl(self, command="crawl", mode="all", retry_errors=False):
        self.seed()
        if retry_errors:
            self.retry_errors()
        step = 0
        processors = {"listing": self.process_listing, "detail": self.process_detail, "asset": self.process_asset}
        while True:
            kind, row = self.next_task(command, mode, step)
            if row is None:
                break
            key = row["source_url"] if kind == "detail" else row["url"]
            print(json.dumps({"event": "processing", "kind": kind, "url": key, "network_requests": self.client.request_count, "at": utc_now()}, ensure_ascii=True), flush=True)
            try:
                processors[kind](row)
            except BudgetReached:
                print(json.dumps({"event": "budget_reached", "network_requests": self.client.request_count}), flush=True)
                break
            except (PermissionError, CrawlStopped, ValueError, OSError) as error:
                table = {"listing": "pages", "detail": "works", "asset": "assets"}[kind]
                column = "id" if kind == "detail" else "url"
                identity = row["id"] if kind == "detail" else row["url"]
                state = "blocked" if isinstance(error, PermissionError) else "error"
                self.db.execute(f"UPDATE {table} SET state=?,error=? WHERE {column}=?", (state, str(error), identity))
                self.db.commit()
                print(json.dumps({"event": "failed", "kind": kind, "url": key, "error": str(error)}, ensure_ascii=True), flush=True)
                if isinstance(error, CrawlStopped):
                    self.db.execute("INSERT OR REPLACE INTO settings VALUES ('last_stop',?)", (str(error),))
                    self.db.commit()
                    break
            step += 1
            if step % 20 == 0:
                self.export()
        return self.export()

    def coverage(self):
        def counts(table):
            return {row["state"]: row["count"] for row in self.db.execute(f"SELECT state,COUNT(*) AS count FROM {table} GROUP BY state")}
        pages, works, assets = counts("pages"), counts("works"), counts("assets")
        inventory_closed = bool(pages.get("done")) and all(state == "done" for state in pages)
        reviewed = 0
        total_images = 0
        for row in self.db.execute("SELECT metadata FROM works WHERE metadata IS NOT NULL"):
            record = json.loads(row["metadata"])
            total_images += len(record.get("images", []))
            review = record.get("visual_review", {})
            if review.get("status") == "complete" and record.get("images") and set(review.get("reviewed_image_positions", [])) >= set(image["position"] for image in record["images"]) and review.get("evidence_path"):
                reviewed += 1
        work_total = sum(works.values())
        ready_images = self.db.execute("SELECT COUNT(*) FROM work_assets JOIN assets ON assets.url=work_assets.url WHERE assets.state='done'").fetchone()[0]
        fully_reviewed = inventory_closed and work_total > 0 and works.get("done", 0) == work_total and reviewed == work_total and all(state == "done" for state in assets)
        external_reviews = 0
        external_reviews_path = self.output / "visual-reviews.jsonl"
        if external_reviews_path.exists():
            external_reviews = sum(1 for line in external_reviews_path.read_text(encoding="utf8").splitlines() if line.strip())
        return {
            "generated_at": utc_now(),
            "scope": self.scope,
            "inventory_closed": inventory_closed,
            "fully_reviewed": fully_reviewed,
            "pages": pages,
            "artworks": works,
            "unique_artwork_count": work_total,
            "displayed_image_count": total_images,
            "assets": assets,
            "visually_reviewed_artwork_count": reviewed,
            "external_visual_review_record_count": external_reviews,
            "pending_visual_review_artwork_count": work_total - reviewed,
            "image_records_ready_for_visual_review": ready_images,
            "image_records_not_yet_downloaded": total_images - ready_images,
            "visual_review_queue_file": str(self.output / "visual-review-queue.jsonl"),
            "taxonomy_term_count": self.db.execute("SELECT COUNT(*) FROM taxonomy").fetchone()[0],
            "artist_taxonomy_count": self.db.execute("SELECT COUNT(*) FROM taxonomy WHERE is_artist=1").fetchone()[0],
            "policy": {"minimum_request_interval_seconds": 10, "globally_serialized_request_lock": str(self.work / "crawl-clock.lock"), "archival_downloads_requested": False, "visual_review_not_inferred_from_download_or_pixels": True, "inventory_closed_definition": "Every seeded and discovered listing page completed without pending, error or blocked listing pages; terminal pagers are absent in fetched HTML. Snapshot only, not proof against unlinked works."},
            "failures": [{"kind": table, "key": row[0], "state": row[1], "error": row[2]} for table, column in (("pages", "url"), ("works", "id"), ("assets", "url")) for row in self.db.execute(f"SELECT {column},state,error FROM {table} WHERE state IN ('error','blocked')")],
        }

    def review_export(self):
        self.output.mkdir(parents=True, exist_ok=True)
        path = self.output / "visual-review-queue.jsonl"
        count = 0
        with path.open("w", encoding="utf8") as handle:
            for row in self.db.execute("SELECT * FROM works ORDER BY CAST(node_id AS INTEGER),id"):
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                common = {
                    "artwork_id": row["id"],
                    "node_id": row["node_id"],
                    "source_url": metadata.get("source_url", row["source_url"]),
                    "title": metadata.get("title", row["title"]),
                    "collection": row["collection"],
                    "metadata_status": row["state"],
                    "checked_at": row["checked_at"],
                    "metadata": {key: metadata.get(key) for key in ("artists", "author_attribution", "uploader_source_text", "subjects", "execution_techniques", "art_branches", "creation_era", "occasion", "description", "physical_dimensions", "copyright_source_text", "publication_date_source_text")},
                }
                images = metadata.get("images", [])
                for image in images or [None]:
                    asset = self.db.execute("SELECT * FROM assets WHERE url=?", (image["url"],)).fetchone() if image else None
                    record = {
                        **common,
                        "image_position": image.get("position") if image else None,
                        "image_url": image.get("url") if image else None,
                        "image_alt": image.get("alt") if image else None,
                        "local_asset_path": asset["local_path"] if asset else None,
                        "asset_status": asset["state"] if asset else "not_identified",
                        "actual_pixel_dimensions": {"width": asset["width"], "height": asset["height"]} if asset and asset["state"] == "done" else None,
                        "ready_for_visual_review": bool(asset and asset["state"] == "done"),
                        "pending_reason": None if asset and asset["state"] == "done" else ("image_download_pending" if image else ("metadata_pending" if row["state"] != "done" else "displayed_images_not_identified")),
                        "visual_review": {"status": "pending", "observations": {}, "limitations": [], "reviewed_at": None, "reviewer": None},
                    }
                    handle.write(json.dumps(safe_export(record), ensure_ascii=False) + "\n")
                    count += 1
        return {"path": str(path), "record_count": count, "observations_inferred": False}

    def export(self):
        self.output.mkdir(parents=True, exist_ok=True)
        asset_rows = {row["url"]: dict(row) for row in self.db.execute("SELECT * FROM assets ORDER BY url")}
        artists = {}
        for row in self.db.execute("SELECT * FROM taxonomy WHERE is_artist=1 ORDER BY id"):
            artists["term:" + row["id"]] = {"id": "term:" + row["id"], "name": row["name"], "taxonomy_url": row["source_url"], "artwork_ids": [], "attribution_status": "taxonomy_entry", "visual_profile_status": "not_reviewed"}
        catalog_path = self.output / "catalog.jsonl"
        with catalog_path.open("w", encoding="utf8") as handle:
            for row in self.db.execute("SELECT * FROM works ORDER BY CAST(node_id AS INTEGER),id"):
                record = json.loads(row["metadata"]) if row["metadata"] else {"id": row["id"], "node_id": row["node_id"], "source_url": row["source_url"], "title": row["title"], "collection": row["collection"], "checked_at": None, "visual_review": {"status": "pending"}}
                record["metadata_status"] = row["state"]
                record["metadata_error"] = row["error"]
                record["artwork_id"] = record.get("id", row["id"])
                record["discovered_from"] = [source[0] for source in self.db.execute("SELECT source_url FROM discoveries WHERE work_id=? ORDER BY source_url", (row["id"],))]
                record["aliases"] = [source[0] for source in self.db.execute("SELECT url FROM aliases WHERE work_id=? ORDER BY url", (row["id"],))]
                credits = []
                for artist_value in record.get("artists", []):
                    for link in artist_value.get("links", []):
                        credits.append({"name": link.get("label") or artist_value.get("text", ""), "role": "credited_artist", "artist_url": link.get("url"), "source_url": record.get("source_url"), "attribution_status": "explicit_artist_field"})
                record["credits"] = credits
                for candidate in record.get("images", []):
                    asset = asset_rows.get(candidate["url"], {})
                    candidate["asset"] = asset
                    candidate["pixel_dimensions_verified"] = asset.get("state") == "done"
                for artist_value in record.get("artists", []):
                    for link in artist_value.get("links", []):
                        candidates = [value for value in artists.values() if value["name"] == link["label"]]
                        matched = candidates[0] if len(candidates) == 1 else None
                        if matched is None:
                            identity = "artist-url:" + (link["url"] or link["label"])
                            matched = artists.setdefault(identity, {"id": identity, "name": link["label"], "taxonomy_url": link["url"], "artwork_ids": [], "attribution_status": "explicit_artist_field", "visual_profile_status": "not_reviewed"})
                        if row["id"] not in matched["artwork_ids"]:
                            matched["artwork_ids"].append(row["id"])
                handle.write(json.dumps(safe_export(record), ensure_ascii=False) + "\n")
        with (self.output / "assets-manifest.jsonl").open("w", encoding="utf8") as handle:
            for asset in asset_rows.values():
                asset["references"] = [dict(row) for row in self.db.execute("SELECT work_id,position FROM work_assets WHERE url=? ORDER BY work_id,position", (asset["url"],))]
                handle.write(json.dumps(asset, ensure_ascii=False) + "\n")
        for artist in artists.values():
            artist["artist_id"] = artist["id"]
            artist["url"] = artist["taxonomy_url"]
        (self.output / "artists.json").write_text(json.dumps(list(artists.values()), ensure_ascii=False, indent=2), encoding="utf8")
        (self.output / "taxonomy.json").write_text(json.dumps([dict(row) for row in self.db.execute("SELECT * FROM taxonomy ORDER BY group_name,id")], ensure_ascii=False, indent=2), encoding="utf8")
        (self.output / "listing-pages.json").write_text(json.dumps([dict(row) for row in self.db.execute("SELECT * FROM pages ORDER BY priority,url")], ensure_ascii=False, indent=2), encoding="utf8")
        self.review_export()
        coverage = self.coverage()
        (self.output / "coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf8")
        return coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("crawl", "inventory", "export", "status", "review-export", "review-queue"))
    parser.add_argument("--mode", choices=("metadata", "assets", "all"), default="all")
    parser.add_argument("--scope", choices=("all", "graphics"), default="all")
    parser.add_argument("--max-requests", type=int)
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--work-dir", type=Path, default=WORK)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    if arguments.max_requests is not None and arguments.max_requests < 0:
        parser.error("--max-requests must be nonnegative")
    audit = Audit(arguments.work_dir, arguments.output_dir, arguments.max_requests, arguments.scope)
    if arguments.command in ("crawl", "inventory"):
        coverage = audit.crawl(arguments.command, arguments.mode, arguments.retry_errors)
    elif arguments.command == "export":
        coverage = audit.export()
    elif arguments.command in ("review-export", "review-queue"):
        coverage = audit.review_export()
    else:
        coverage = audit.coverage()
    print(json.dumps(coverage, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    main()
