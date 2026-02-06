# Changelog

All notable changes to DataForge are documented here.

## [2.3.0] - 2025-01-15

### Added

- S3Source for reading from AWS S3 buckets
- Pipeline retry configuration with exponential backoff
- `--dry-run` flag for pipeline validation without execution

### Changed

- Upgraded SQLAlchemy dependency to 2.0
- Improved batch insert performance by 40% for PostgreSQL loader

### Fixed

- Memory leak in streaming CSV source for files larger than 2 GB
- Incorrect row count in monitoring dashboard for parallel pipelines

## [2.2.0] - 2024-10-01

### Added

- Monitoring dashboard with real-time pipeline metrics
- Plugin system for custom sources and loaders
- YAML pipeline definitions alongside Python API

### Breaking Changes

- `Pipeline.execute()` renamed to `Pipeline.run()` for consistency
- `Source.fetch()` renamed to `Source.read()`
- Minimum Python version raised from 3.9 to 3.10

## [2.1.0] - 2024-07-20

### Added

- Parallel execution with configurable worker pool
- Data validation with schema enforcement
- Deduplication transformer

See [README](README.md) for current usage patterns and [Contributing](CONTRIBUTING.md) for development setup.
