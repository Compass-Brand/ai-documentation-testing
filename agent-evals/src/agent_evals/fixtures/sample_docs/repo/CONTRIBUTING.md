# Contributing to DataForge

We welcome contributions from the community. Please follow these guidelines.

## Development Setup

```bash
git clone https://github.com/example/dataforge.git
cd dataforge
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Branch Strategy

- `main` -- Stable releases only
- `develop` -- Integration branch for next release
- `feature/*` -- New features branch off `develop`
- `fix/*` -- Bug fixes branch off `develop`

## Pull Request Process

1. Create a feature or fix branch from `develop`
2. Write tests for any new functionality
3. Ensure all tests pass: `pytest tests/ -v`
4. Run linting: `ruff check src/`
5. Update documentation if public API changes
6. Open a PR against `develop` with a clear description

## Code Style

- Follow PEP 8 conventions
- Use type hints for all public functions
- Maximum line length: 100 characters
- Docstrings in Google style format

## Commit Messages

Use conventional commit format:

```
feat(pipeline): add retry logic for failed transforms
fix(loader): handle null values in PostgreSQL batch insert
docs(readme): update quick start example
```

See [Architecture](architecture.md) for understanding the codebase structure before contributing.
