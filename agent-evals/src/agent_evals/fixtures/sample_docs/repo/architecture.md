# Architecture

DataForge follows a pipeline architecture with pluggable components at each stage.

## Component Overview

```
Source -> Transformer -> Validator -> Loader -> Monitor
```

### Source

Reads data from external systems. Built-in sources:

- `CSVSource` -- Local or remote CSV files
- `SQLSource` -- SQL databases via SQLAlchemy
- `APISource` -- REST API endpoints with pagination
- `S3Source` -- AWS S3 buckets

### Transformer

Applies data transformations in sequence. Each transformer receives a `DataFrame` and returns a modified `DataFrame`.

### Validator

Enforces schema constraints and data quality rules:

```python
from dataforge.validation import Schema, Column, checks

schema = Schema([
    Column("email", dtype="string", checks=[checks.is_email]),
    Column("age", dtype="int", checks=[checks.between(0, 150)]),
])
```

### Loader

Writes validated data to target systems. Supports batch inserts and upsert strategies.

### Monitor

Collects pipeline metrics: row counts, error rates, throughput, and duration. Publishes to the monitoring dashboard.

## Plugin System

Register custom components:

```python
from dataforge.plugins import register_source

@register_source("kafka")
class KafkaSource:
    def read(self) -> DataFrame:
        ...
```

See [README](README.md) for usage examples and [Troubleshooting](troubleshooting.md) for debugging pipelines.
