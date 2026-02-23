# Release Workflow

Steps for cutting a new DataForge release.

## Pre-release Checklist

1. Ensure all PRs for the release are merged to `develop`
2. Run the full test suite: `pytest tests/ -v --cov`
3. Verify coverage meets the 90% threshold
4. Update `changelog.md` with all changes since last release
5. Review and update documentation for any API changes

## Version Bumping

Use `bump2version` to manage semantic versioning:

```bash
# Patch release (bug fixes): 2.3.0 -> 2.3.1
bump2version patch

# Minor release (new features): 2.3.0 -> 2.4.0
bump2version minor

# Major release (breaking changes): 2.3.0 -> 3.0.0
bump2version major
```

## Release Steps

1. Create a release branch from `develop`:
   ```bash
   git checkout -b release/v2.4.0 develop
   ```

2. Bump the version and commit
3. Open a PR from `release/v2.4.0` to `main`
4. After merge, tag the release:
   ```bash
   git tag v2.4.0
   git push origin v2.4.0
   ```

5. The CI pipeline builds and publishes to PyPI automatically
6. Merge `main` back to `develop` to sync version numbers

## Hotfix Process

For critical production bugs:

1. Branch from `main`: `git checkout -b fix/critical-bug main`
2. Apply fix and bump patch version
3. PR to both `main` and `develop`

See [Contributing](../repo/CONTRIBUTING.md) for branch strategy and [Changelog](../repo/changelog.md) for version history format.

## Debug Utilities

```python
class DebugContext:
    """Context manager for structured debug sessions."""
    
    def __init__(self, module: str, level: str = "INFO"):
        self.module = module
        self.level = level
        self._start = None
    
    def __enter__(self):
        import time
        self._start = time.monotonic()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        elapsed = time.monotonic() - self._start
        print(f"[{self.module}] completed in {elapsed:.3f}s")
        return False

def trace_calls(func):
    """Decorator to trace function calls with arguments."""
    def wrapper(*args, **kwargs):
        print(f"TRACE: {func.__name__}({args}, {kwargs})")
        result = func(*args, **kwargs)
        print(f"TRACE: {func.__name__} -> {result!r}")
        return result
    return wrapper
```
