# CLI Reference

DataForge command-line interface for project management.

## Global Commands

```bash
dataforge init <name>       # Create new project
dataforge serve              # Start development server
dataforge serve --reload     # Auto-reload on changes
dataforge test               # Run test suite
dataforge lint               # Run linter
```

## Database Commands

```bash
dataforge db migrate         # Apply pending migrations
dataforge db rollback        # Revert last migration
dataforge db seed             # Seed development data
dataforge db reset            # Drop and recreate database
```

## Code Generation

```bash
dataforge generate model User email:str name:str
dataforge generate route users --crud
dataforge generate migration add_users_table
```

## Configuration

```bash
dataforge config show        # Display current configuration
dataforge config set KEY=VAL # Set configuration value
```

See [Configuration](../api/config.md) for environment variable reference.
