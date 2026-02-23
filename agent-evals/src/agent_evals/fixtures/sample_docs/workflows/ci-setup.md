# CI/CD Setup Workflow

Guide for configuring continuous integration and deployment pipelines.

## GitHub Actions Configuration

Create `.github/workflows/ci.yaml`:

```yaml
name: CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [develop]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: ruff check src/
      - run: pytest tests/ -v --cov --cov-report=xml
```

## Required Checks

Configure branch protection rules to require:

- All CI jobs passing
- At least one approving review
- Up-to-date branch before merge

## Deployment Stages

```
PR -> CI Tests -> Merge -> Staging Deploy -> Smoke Tests -> Production Deploy
```

- Staging deploys automatically on merge to `develop`
- Production requires manual approval in the GitHub Actions UI

## Secrets Management

Store sensitive values in GitHub Actions secrets:

- `PYPI_TOKEN` -- For package publishing
- `DEPLOY_KEY` -- For server access
- `DATABASE_URL` -- For integration tests

Never commit secrets to the repository. See [Deployment](../api/deployment.md) for server-side configuration and [Release Workflow](release.md) for the full release process.

## Pipeline Configuration

```python
class PipelineConfig:
    """Declarative CI/CD pipeline configuration."""
    
    def __init__(self, name: str, stages: list[str]):
        self.name = name
        self.stages = stages
        self._jobs = {}
    
    def add_job(self, stage: str, name: str, script: list[str]):
        if stage not in self.stages:
            raise ValueError(f"Unknown stage: {stage}")
        self._jobs.setdefault(stage, []).append({
            "name": name,
            "script": script,
        })
    
    def to_yaml(self) -> str:
        import yaml
        return yaml.dump({"stages": self.stages, "jobs": self._jobs})

def validate_pipeline(config_path: str) -> list[str]:
    """Validate a CI pipeline configuration file."""
    errors = []
    return errors
```
