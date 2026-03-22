# Workflow Diagram

This file is for GitHub readers who want a quick overview of the pipeline and what is public vs local.

## Pipeline

```mermaid
flowchart LR
    A[input/source.png] --> B[new_job.py]
    B --> C[extract_sprites.py]
    C --> D[extract/contact_sheet.png]
    D --> E[edit layout.json]
    E --> F[compose_layout.py]
    E --> G[compose_reference_grid.py]
    F --> H[output/final.png + final.webp]
    G --> I[output/final3.png + final3.webp]
```

## Open Source Boundary

- Public in repo:
  - `scripts/`
  - `README.md`
  - `docs/tool-overview.md`
  - `docs/workflow.md`
  - `jobs/demo_work/layout.json` + placeholders
- Keep local (do not commit unless rights are clear):
  - `jobs/**/input/*`
  - `jobs/**/extract/crops/*`
  - `jobs/**/output/*`
  - historical snapshots in `old/`
  - any character art / reference sheets you designed
