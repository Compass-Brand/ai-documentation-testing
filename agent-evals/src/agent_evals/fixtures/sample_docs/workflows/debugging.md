# Debugging Workflow

A systematic approach to diagnosing and resolving issues in DataForge pipelines.

## Step 1: Reproduce the Issue

Before debugging, confirm you can consistently trigger the problem:

```bash
export LOG_LEVEL=DEBUG
dataforge run pipeline.yaml --verbose 2>&1 | tee debug.log
```

## Step 2: Isolate the Component

DataForge pipelines have distinct stages. Narrow down which stage fails:

1. **Source** -- Does the source return data? Check with `dataforge inspect source`
2. **Transform** -- Add logging between transforms to find where data corrupts
3. **Validate** -- Run validation standalone: `dataforge validate --schema schema.yaml data.csv`
4. **Load** -- Test the loader with a small sample dataset

## Step 3: Check Common Causes

- **Connection timeouts** -- Increase `CONNECT_TIMEOUT` for database and API sources
- **Schema mismatches** -- Compare source schema against expected types
- **Missing environment variables** -- Run `dataforge check-env` to verify
- **Dependency conflicts** -- Check `pip list` for version mismatches

## Step 4: Use the Debugger

```python
import pdb

def my_transform(df):
    pdb.set_trace()  # drops into interactive debugger
    return df.dropna()
```

## Step 5: Write a Regression Test

Once fixed, add a test that reproduces the original failure:

```python
def test_null_handling_in_transform():
    df = pd.DataFrame({"col": [1, None, 3]})
    result = my_transform(df)
    assert len(result) == 2
```

See [Troubleshooting](../repo/troubleshooting.md) for known issues and [Architecture](../repo/architecture.md) for component details.

## Release Automation

```python
class ReleaseManager:
    """Automate the release process with semantic versioning."""
    
    def __init__(self, repo_path: str, version: str):
        self.repo_path = repo_path
        self.version = version
    
    def bump_version(self, part: str = "patch") -> str:
        major, minor, patch = map(int, self.version.split("."))
        if part == "major":
            return f"{major + 1}.0.0"
        elif part == "minor":
            return f"{major}.{minor + 1}.0"
        return f"{major}.{minor}.{patch + 1}"
    
    def create_changelog(self, commits: list[str]) -> str:
        lines = [f"## {self.version}", ""]
        for commit in commits:
            lines.append(f"- {commit}")
        return "\n".join(lines)

def tag_release(version: str, message: str) -> None:
    """Create an annotated git tag for the release."""
    import subprocess
    subprocess.run(["git", "tag", "-a", version, "-m", message])
```
