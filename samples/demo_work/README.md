# demo_work

Release sample package built from local source image.

## Contents

- `input/source.png`
- `extract/contact_sheet.png`
- `extract/objects.json`
- `extract/crops/sprite_001.png` ~ `extract/crops/sprite_008.png`
- `layout.json` (uses IDs `002` to `007`)
- `output/final.png`
- `output/final.webp`
- `output/composition.json`

## Reference Strategy (with / without reference)

- This public sample is generated **without bundling a reference image**.
- For this sample, no-reference is enough and keeps package smaller.
- If you want reference-guided placement, provide `--reference` explicitly
  (or place `input/reference.webp` under the job dir).

No-reference command:

```bash
.venv/bin/python scripts/compose_layout.py \
  --job-dir jobs/demo_work \
  --style compact \
  --output jobs/demo_work/output/final.png \
  --output-webp jobs/demo_work/output/final.webp \
  --report jobs/demo_work/output/composition.json
```

With-reference command:

```bash
.venv/bin/python scripts/compose_layout.py \
  --job-dir jobs/demo_work \
  --style compact \
  --reference jobs/demo_work/input/reference.webp \
  --output jobs/demo_work/output/final.png \
  --output-webp jobs/demo_work/output/final.webp \
  --report jobs/demo_work/output/composition.json
```

Note:
- If the reference layout is not compatible with current row content,
  compose logic will automatically fall back to compact packing
  to avoid tiny or clipped sprites.

## How This Sample Was Generated

```bash
.venv/bin/python scripts/extract_sprites.py --job-dir jobs/demo_work
.venv/bin/python scripts/compose_layout.py \
  --job-dir jobs/demo_work \
  --style compact \
  --output jobs/demo_work/output/final.png \
  --output-webp jobs/demo_work/output/final.webp \
  --report jobs/demo_work/output/composition.json
```

`layout.json` is configured to compose only `002~007`.
