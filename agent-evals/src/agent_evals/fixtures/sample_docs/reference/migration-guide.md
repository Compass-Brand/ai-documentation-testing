# Migration Guide

Upgrading between major DataForge versions.

## v1.x to v2.0

### Breaking Changes

1. **Database sessions**: Sync sessions removed, async only
   ```python
   # Before (v1)
   session = SessionLocal()
   # After (v2)
   async with SessionLocal() as session:
   ```

2. **Auth middleware**: Constructor signature changed
   ```python
   # Before
   AuthMiddleware(secret="xxx")
   # After
   AuthMiddleware(JWTConfig(secret_key="xxx"))
   ```

3. **Error responses**: Envelope format standardized
   ```json
   // Before: {"detail": "Not found"}
   // After: {"error": {"code": "NOT_FOUND", "message": "..."}}
   ```

### Migration Steps

1. Update dependency: pip install dataforge>=2.0
2. Run migration script: dataforge migrate-config
3. Update import paths (see changelog)
4. Run test suite and fix any failures

See [Changelog](../repo/changelog.md) for full version history.
