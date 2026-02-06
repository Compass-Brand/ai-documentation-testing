# Security Policy

Guidelines for reporting vulnerabilities and security practices in DataForge.

## Reporting Vulnerabilities

If you discover a security issue, please report it responsibly:

1. Do **not** open a public GitHub issue
2. Email security@example.com with a description
3. Include steps to reproduce if possible
4. We will acknowledge within 48 hours and provide a fix timeline

## Security Practices

### Input Validation

All user-supplied data passes through validation before processing:

```python
from dataforge.validation import sanitize_input

clean_data = sanitize_input(raw_data, schema=pipeline_schema)
```

### SQL Injection Prevention

The framework uses parameterized queries exclusively:

```python
# Safe - parameterized
session.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})

# Unsafe - never do this
session.execute(text(f"SELECT * FROM users WHERE id = {user_id}"))
```

### Dependency Scanning

Run `pip-audit` to check for known vulnerabilities:

```bash
pip install pip-audit
pip-audit
```

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.3.x   | Yes       |
| 2.2.x   | Security fixes only |
| < 2.2   | No        |

See [Contributing](CONTRIBUTING.md) for development practices and [Changelog](changelog.md) for security-related fixes.
