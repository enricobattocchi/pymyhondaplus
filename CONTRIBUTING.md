# Contributing

Thanks for your interest in contributing to pymyhondaplus!

## Reporting issues

If something isn't working, please [open an issue](https://github.com/enricobattocchi/pymyhondaplus/issues) with:

- Your vehicle model (e.g. Honda e, ZR-V, e:Ny1)
- Python version
- The command you ran and the output you got (redact any personal data)

## Development setup

```bash
git clone https://github.com/enricobattocchi/pymyhondaplus.git
cd pymyhondaplus
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests and linting

```bash
pytest
ruff check src/ tests/
mypy src/
```

All three must pass before a PR can be merged. CI runs these automatically on Python 3.11, 3.12, and 3.13.

## Submitting changes

1. Fork the repo and create a branch from `main`.
2. Make your changes. Add tests if you're adding new functionality.
3. Run `pytest`, `ruff check`, and `mypy` locally.
4. Open a pull request with a clear description of what you changed and why.

## Vehicle testing

This library is only fully tested on the Honda e. If you own a different Honda Connect Europe vehicle and can confirm that a feature works (or doesn't), that's one of the most valuable contributions you can make — just open an issue with your findings.

## Code style

- Follow existing patterns in the codebase.
- Type hints are expected for public functions.
- Keep dependencies minimal — don't add new ones without a good reason.
