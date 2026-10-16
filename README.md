# ShiaArts Visual Design Skills

[نسخهٔ فارسی](README.fa.md)

Evidence-bound Codex skills for creating original Persian religious and cultural visual designs, based on a public, attributed study of [ShiaArts](https://shiaarts.ir/).

## What is included

- `skills/shiaarts-graphic-designer/`: shared design workflow, Persian/Arabic typography QA, rights boundaries, and evidence contract.
- `skills/shiaarts-artist-*/`: separate routing skills for source-listed artist identities. Each profile states its visual-evidence coverage and does not invent a style when works are not reviewed.
- `research/`: source metadata, artist/taxonomy indexes, review queue, coverage ledger, and provenance notes.
- `tools/`: resumable public-GET crawler, skill packager, and refresh helper. The full offline test suite remains in the development workspace because it uses private HTML fixtures.

## Evidence status

This repository is an incremental research snapshot, not a trained or fine-tuned model. Check `research/coverage.json` and `research/visual-review-queue.jsonl` before making any completeness claim. Downloading an image, OCR, a filename, or an artist taxonomy entry is not a visual review. A source page’s subject tag or publication date is not automatically an occasion or commission date.

## Install in Codex

Copy the directories under `skills/` into `%USERPROFILE%\.codex\skills\`. Invoke the shared skill with `$shiaarts-graphic-designer`; invoke an artist-specific skill only when its evidence status supports the requested work.

## Continue the audit

The crawler obeys `robots.txt`, uses public sequential GETs, serializes requests with a persistent lock, and keeps archival `/file/.../download` URLs as metadata only. It does not ship raw HTML snapshots, the SQLite state database, local caches, or downloaded source images. See `research/README-fa.md` for resumable commands.

## Rights and attribution

This repository does not grant a blanket license to ShiaArts artwork files or artist works. The site’s per-work notice requires source attribution and copyright-holder permission for economic use, reproduction, and republication. The skills are for original designs informed by observed principles: do not copy a complete layout, signature, watermark, or imply an artist’s endorsement.
