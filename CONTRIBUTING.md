# Contributing

Thanks for your interest in improving this project.

## Scope

This repository is a tooling prototype for:

- sprite extraction
- layout-based composition
- edge cleanup for animation sheets

Please keep PRs focused and small.

## Development Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Typical Local Validation

```bash
.venv/bin/python scripts/new_job.py --help
.venv/bin/python scripts/extract_sprites.py --help
.venv/bin/python scripts/compose_layout.py --help
.venv/bin/python scripts/compose_reference_grid.py --help
```

## Coding Guidelines

- Keep CLI behavior backward compatible where possible.
- Prefer explicit arguments and predictable defaults.
- Keep generated assets out of code-only PRs unless needed for sample docs.
- Do not commit private or non-redistributable assets.

## Pull Request Checklist

- [ ] Problem and approach are clearly described.
- [ ] README/docs updated when behavior changed.
- [ ] Sample commands still work.
- [ ] No private assets accidentally included.

## Asset Boundary

- Code contributions are MIT.
- Asset rights are separate. See `ASSETS_LICENSE.md`.

