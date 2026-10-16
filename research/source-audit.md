# Shiaarts source audit

Verified 2026-10-16 against public HTTP responses. No artwork image assets or original files downloaded by this investigation.

## Source system and crawl constraints

- Public HTML is Drupal, not WordPress: `Drupal.settings`, `node-dexp-portfolio`, `views_infinite_scroll`, taxonomy terms, and Drupal theme/module paths are directly visible in source.
- `https://shiaarts.ir/robots.txt` responds successfully and specifies `User-agent: *` with `Crawl-delay: 10`. Use one shared limiter across metadata and images. Do not crawl admin, login, registration, `/search/`, `/flag/`, or blocked system paths.
- `https://shiaarts.ir/sitemap.xml` responds 200 but contains exactly one URL: `http://www.shiaarts.ir/`. It cannot establish artwork completeness.
- Browser/web text extraction of the home page omitted the gallery because the teaser images are inline CSS backgrounds and the title text is hidden RDF metadata. Inspect HTML, not extracted prose alone.

## Saved evidence

All files reside in the `work` directory:

| File | Public source | Observation |
| --- | --- | --- |
| `source-home.html` | `https://shiaarts.ir/` | 90 portfolio teasers, first node 1803; CSS background preview per item |
| `source-categories.html` | `https://shiaarts.ir/Categories` | Taxonomy directory including 262 artist-term entries, branches, subjects, execution techniques, dates |
| `source-artists.html` | `https://shiaarts.ir/jebhe` | Separate community publication area with 116 distinct visible node IDs; not the creator taxonomy |
| `source-graphics.html` | `https://shiaarts.ir/taxonomy/term/105` | 138 gallery node teasers; no pager in returned HTML |
| `source-work-detail.html` | `https://shiaarts.ir/node/1803` (canonical gallery alias requested) | Main gallery record, calligraphy, creator Ali Rezaeian |
| `source-graphic-detail.html` | `https://shiaarts.ir/node/1795` (canonical gallery alias requested) | Main graphic record, creator Hamed Maghroori |
| `source-sitemap.xml` | `https://shiaarts.ir/sitemap.xml` | Only the home URL |

The 262 artist-term entries are not 262 confirmed individual graphic designers. They include unknown artists, institutional/group credits, non-graphic creators, and duplicate displayed names under different term IDs. Examples: `احمد الهراوی` under IDs 1318 and 1319; `استاد کاظم چلیپا` and `کاظم چلیپا` are separately listed and require evidence before merging.

## Inventory entry points

- Home next-page link: `/node?page=1&destination=next`; zero-based pagination, 90 works on page zero. Follow actual next links until the pager disappears and deduplicate by node ID, not title.
- Exact graphic branch: `/taxonomy/term/105`, canonical alias `/نوع-اثر/گرافیک`, RSS `/taxonomy/term/105/all/feed`.
- The broad Persian expression "graphic designs" may also encompass calligraphy and typography. Exact graphic taxonomy alone would miss those. All home portfolio records should therefore be inventoried first and classification retained per record.
- Other displayed top-level art branch IDs: typography 194; motion graphics 1433; crafts 132; caricature 131; photo 101; drawing 100; painting 102; calligraphic painting 103. Calligraphy has child entries and is not represented by a direct top-level link in this narrow extraction.
- `/jebhe` is a separate artist-community area with `node-blog` posts and aliases `/jebhe/{account}/{title}` plus some `/node/{id}` paths. In the saved response its infinite-scroll pager contains an empty list item, not a next link. This does not independently prove that all community submissions are visible.
- `/jebhe/members` is linked as the community member directory; not fetched during this audit.

## Gallery metadata schema

Extract only the first/main portfolio node, excluding related-work nodes nested later in the page.

| Selector/field | Meaning |
| --- | --- |
| first `div.node-dexp-portfolio[id^=node-]` | Stable node ID and `about` gallery alias |
| `h3.portfolio-detail` / RDF `dc:title` | Work title |
| `.field-name-field-portfolio-images img` | Display image URL, declared width/height, alt/title; there may be multiple images |
| `.field-name-field-portfolio-categories` | Subject taxonomy; may contain multiple field items and hierarchy |
| `.field-name-field-style` | Execution technique, not an inferred visual style |
| `.field-name-field-teknikha` | Art branch and subtype hierarchy |
| `.field-name-field-artist` | Creator attribution and creator taxonomy URL; preserve multi-credit records |
| `.field-name-field-era` | Work creation period/year; distinct from publication date |
| `.field-name-body` | Descriptive text; may state commissioner, occasion, poet, or other contributor |
| `.date-created` | Publication date, displayed in Jalali calendar |
| `.views-field-field-phone` | Optional mobile-download variant |
| `.field-name-field-backgerond` / `.views-field-field-backgerond` | Original/high-quality download, MIME type and byte length |
| `.views-field-field-vector` | Optional vector download |
| `.copyright-works` | Per-work rights warning |

Do not infer an exact occasion solely from a subject or publication date. Store explicitly stated occasion separately from inferred context, each with evidence and confidence. Do not use related-work metadata for the main work.

## Verified example records (metadata only, no visual analysis)

- Node 1803: `سلام بر حضرت زینب کبری (علیها السلام)`; creator `علی رضاییان`; subject `حضرت زینب (س)`; execution `قلم و مرکب`; art branch `خوشنویسی › خط ثلث`; created `سال 1402`; published `1405/07/23`; preview declared 800×500. Body contains poetry credited to `سیدحمیدرضا برقعی` (poet is not the graphic designer).
- Node 1795: `تنگه هرمز، تنگه باب المندب`; creator `حامد مغروری`; subjects `استکبار ستیزی`, `مقاومت اسلامی`; execution `دیجیتال`; branch `گرافیک`; created `سال 1405`; published `1405/06/24`; preview declared 549×800. Body explicitly states `خلق اثر به سفارش حوزه هنری در سال 1405`; commissioner is verified but a specific event/date is not stated.

## Rights and attribution

The footer broadly allows use with source attribution. The individual artwork notice is stricter: works are offered for cultural/artistic use; economic exploitation, reproduction (whole or part), and republication require source attribution and copyright-holder permission. The two footer menu items named copyright policy and infringement report point back to `/` rather than a substantive standalone policy page.

The skill should produce original designs from high-level visual analysis, preserve source/creator provenance, avoid copying signatures/watermarks or exact layouts, and not claim permission for commercial reuse of source works. Do not package source images in a distributable skill without a separate rights decision.

## Remaining blind spots / completeness gates

- Home full pagination has not been enumerated by this subagent. The highest node ID is not an artwork count and includes non-artwork content gaps.
- Graphic taxonomy's 138 entries must be reconciled against the full home inventory and expected branch labels, not treated as all visual design on the site.
- Community blog submissions require their own detail parsing and author-versus-uploader distinction; `/jebhe/shiaarts/…` does not prove Shiaarts is the artist (the card can display another credited user).
- Sitemaps cannot validate total counts. A complete crawl needs terminal-page evidence, URL/node deduplication, error/retry ledger, and coverage metrics for records/images/visual analyses/artist profiles.
- Exact source dimensions, DPI, file format, colors, typography, composition and motifs need individual image inspection. HTML width/height describes the preview, not print specifications.
- No API was asserted or tested; no hidden/private endpoints were needed for the observed public inventory.
