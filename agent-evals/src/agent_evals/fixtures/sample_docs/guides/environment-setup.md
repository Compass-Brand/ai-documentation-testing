# Environment Setup

Detailed development environment configuration for DataForge.

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.11 | 3.12 |
| PostgreSQL | 14 | 16 |
| RAM | 4 GB | 8 GB |
| Disk | 2 GB | 5 GB |

## Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate      # Windows
pip install -e ".[dev]"
```

## IDE Configuration

### VS Code

Install recommended extensions:
- Python (Microsoft)
- Pylance
- Ruff

### PyCharm

Enable the Django/FastAPI plugin for template support.

See [Configuration](../api/config.md) for runtime settings.
