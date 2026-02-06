# Troubleshooting

Common issues and their solutions when working with DataForge.

## Pipeline Fails to Start

**Symptom:** `ConfigurationError: Missing required source configuration`

**Solution:** Ensure your pipeline YAML or Python definition includes a source block. Check that all required environment variables are set:

```bash
export DATABASE_URL="postgresql://user:pass@localhost/mydb"
dataforge validate pipeline.yaml
```

## Out of Memory on Large Files

**Symptom:** `MemoryError` when processing CSV files over 1 GB

**Solution:** Enable streaming mode in the source configuration:

```python
source = CSVSource("large_file.csv", streaming=True, chunk_size=10000)
```

## Slow Batch Inserts

**Symptom:** PostgreSQL loader takes over 10 minutes for 1M rows

**Solution:**

1. Increase batch size: `PostgresLoader(batch_size=5000)`
2. Disable index updates during load: `PostgresLoader(disable_indexes=True)`
3. Use `COPY` mode for bulk loading: `PostgresLoader(method="copy")`

## Schema Validation Errors

**Symptom:** `ValidationError: Column 'date' expected type 'datetime', got 'string'`

**Solution:** Add a date parser transformer before validation:

```python
pipeline.transform(parse_dates(columns=["date"], format="%Y-%m-%d"))
```

## Debug Logging

Enable verbose logging to diagnose issues:

```bash
export LOG_LEVEL=DEBUG
dataforge run pipeline.yaml --verbose
```

See [Architecture](architecture.md) for understanding component interactions and [README](README.md) for correct setup.
