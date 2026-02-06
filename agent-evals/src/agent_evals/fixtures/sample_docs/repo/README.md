# DataForge

DataForge is a Python library for building and running ETL pipelines with built-in validation and monitoring.

## Features

- Declarative pipeline definitions using YAML or Python
- Built-in data validation with schema enforcement
- Parallel execution with configurable worker pools
- Monitoring dashboard with real-time metrics
- Plugin system for custom transformers and loaders

## Quick Start

```bash
pip install dataforge
dataforge init my-pipeline
cd my-pipeline
dataforge run pipeline.yaml
```

## Example Pipeline

```python
from dataforge import Pipeline, CSVSource, PostgresLoader

pipeline = Pipeline("daily-import")
pipeline.source(CSVSource("data/input.csv"))
pipeline.transform(validate_schema, deduplicate, normalize_dates)
pipeline.load(PostgresLoader(table="events"))
pipeline.run()
```

## Documentation

- [Architecture](architecture.md) -- System design and component overview
- [Contributing](CONTRIBUTING.md) -- How to contribute
- [Changelog](changelog.md) -- Version history
- [Troubleshooting](troubleshooting.md) -- Common issues and solutions

## License

MIT License. See `LICENSE` file for details.
