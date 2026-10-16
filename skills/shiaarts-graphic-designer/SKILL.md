---
name: shiaarts-graphic-designer
description: Create original Persian religious and cultural graphic designs using source-verified ShiaArts artwork analysis, with accurate occasion attribution, Persian typography, composition, and production QA. Use for posters, calligraphic graphics, illustrated campaigns, banners, and artwork-informed artist-style requests, not for claiming a model has been trained or an artist has authored the result.
---

# ShiaArts Graphic Designer

Turn an evidenced visual study into a finished original design, not a generic religious image or a copy of an existing poster. Treat ShiaArts as a collection of distinct works and contributors, never one uniform house style. A skill is an instruction-and-reference system; do not describe it as a fine-tuned model or a guarantee of the named artist's workmanship.

## Select the right evidence

- Search [references/artists.json](references/artists.json) to route a named artist to the matching skill. Use [references/catalog.jsonl](references/catalog.jsonl) for source metadata and [references/visual-reviews.jsonl](references/visual-reviews.jsonl) for actual visual observations; join by `artwork_id`. Retrieve the relevant records rather than loading the whole collection into context. A catalog entry is not a visual review, and a missing review must remain unreviewed.
- If the request names an artist, use that artist's accompanying skill/profile when available. Resolve Persian name variants against credited source pages. If attribution or identity is ambiguous, say so rather than assigning another artist's work.
- If the request names a visual style but no artist, select actual visually inspected reference works sharing that treatment. Do not equate every religious subject, gold ornament, or Arabic inscription with the same style.
- Read [references/evidence-contract.md](references/evidence-contract.md) when reviewing a work, selecting corpus evidence, resolving attribution, or updating an artist profile. Distinguish verified metadata, direct visual observation, and interpretation.
- A link, filename, download, OCR result, thumbnail, or contact sheet alone is not proof of detailed visual review. Open the work at a useful size and inspect relevant details before making design-specific claims. Do not report that the complete site was reviewed unless the coverage ledger proves that scope.
- If usable corpus evidence is absent, retrieve and inspect source references or ask for reference images. You can still deliver a clearly labeled general design exploration, but cannot call it a verified reproduction of an artist's visual language.

## Establish the brief

Preserve the user's exact Persian wording and specified format. Resolve missing details only where they change the result materially:

- Occasion, intended message, audience, emotional tone, and publishing context.
- Exact main inscription, supporting copy, date, logos, organizer/credit line, and which text is sacred or quoted.
- Intended output: print, story, post, screen, fabric/banner, or another medium; size, orientation, and required editable format.
- Requested artist or reference works; distinguish a style reference from an image to edit or a licensed component to incorporate.

Do not invent a Quranic verse, hadith, attribution, calendar date, historical event, sponsor, or organizer. A source page's occasion is not automatically the occasion of the new brief. Ask one focused question for a blocking omission; otherwise proceed with stated, reversible assumptions.

## Translate observation into design decisions

Write a compact internal design specification before rendering:

1. **Concept:** one visual argument tied to the message. Define why the motif, image, and typography belong together, rather than assembling religious symbols decoratively.
2. **Evidence-backed style grammar:** identify the chosen references and their relevant composition, lettering, image-making, ornament, color, texture, and spatial behavior. Separate a recurring artist tendency from a one-work experiment; limited evidence warrants a narrow claim.
3. **Original composition:** specify focal point, reading order, dominant and supporting masses, alignment logic, negative space, depth, and edge treatment. Do not trace the reference's distinctive full layout.
4. **Type/image relationship:** decide whether lettering is the subject, a structural shape, a caption, or an overlay. Plan meaningful interaction without harming legibility or cropping letters unintentionally.
5. **Palette and material:** define dominant/support/accent roles and value contrast. Label sampled colors as sampled and visually estimated colors as approximate. Choose texture at the final reproduction scale, not just at zoomed preview size.
6. **Transformation:** state which reusable visual principles are retained and which subject, arrangement, wording, motifs, or narrative are newly designed. A subject swap on an otherwise copied poster is not an original concept.

For mixed references, retain one coherent compositional logic. Do not combine unrelated signatures merely because they appear on the same site. When the user specifies an artist, that evidence takes precedence over broad genre conventions.

## Produce the artwork

- Read [references/persian-production.md](references/persian-production.md) for Persian/Arabic lettering, sacred text, layered assembly, and final output checks.
- Use the installed `imagegen` skill for genuinely raster generation/editing; follow its current tool availability and authorization rules. Do not silently substitute an SVG/HTML placeholder for a requested finished raster artwork. Do not silently switch to a paid API fallback when the normal generation tool is unavailable.
- For a reference-guided new design, explicitly label references as style/composition guidance, not edit targets. For edits, identify the target and list elements that must remain unchanged.
- Translate the internal specification into concrete visual instructions: medium, subject, composition, type placement, palette, lighting, texture, desired emotion, and prohibited additions. Do not rely solely on “in the style of [name]”.
- Use a type-safe layered workflow when exact text is essential. Generate or construct the pictorial field with the required clear space, then compose verified text in an editable typography layer. If attempting generated lettering, proof it visually character by character; rerender or replace the lettering if wrong.
- Make a complete design, including hierarchy and supporting copy where requested. An atmospheric background alone is not a finished poster. Keep a clean background-only version only when it is useful to the requested deliverable.
- Do not reproduce an artist's signature, watermark, or logo to imply authorship. Preserve legitimate credits in edits unless the user requests an authorized change. Do not remove someone else's credit to pass their existing work off as new.

## Review before delivery

Inspect the full design and relevant close-ups, then check it at its real viewing size and a small thumbnail. Confirm:

- The brief's message and intended emotional register are evident; the focal point and reading order work without explanation.
- Lettering, accents, diacritics, numerals, names, dates, and quoted religious text match the approved source exactly.
- Required information survives the medium's crop and safe area; small copy is usable at the actual reproduction size.
- Motifs and depictions fit the stated occasion and audience; no accidental anatomical, architectural, calligraphic, or symbolic artifacts remain.
- The design uses the observed principles meaningfully without duplicating an existing work's distinctive arrangement or implying the artist created it.
- The delivered pixel dimensions, aspect ratio, transparency, color mode, and file type are real. Do not claim a raster export is a layered PSD/vector master or that changing DPI metadata adds detail.

Fix the most consequential failure first, preserving the approved wording and successful parts. If visual inspection or final-format validation is unavailable, state exactly what remains unverified; do not label the work print-ready.

## Deliver concisely

Show the finished preview and link the actual saved deliverables. State the intended size/use, verified formats, short design rationale, and reference works/artist profile used. Describe it as an original work informed by the studied visual principles, not a commission authored by the referenced artist. Identify any unresolved text, rights, production, or evidence limitation explicitly. Preserve the prompt/specification with project deliverables when useful for reproducibility.
