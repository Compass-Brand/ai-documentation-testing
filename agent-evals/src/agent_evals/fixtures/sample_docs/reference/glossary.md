# Glossary

Key terms and definitions used across DataForge documentation.

## Terms

**Access Token** -- Short-lived JWT used to authenticate API requests. Expires after 1 hour.

**Alembic** -- Database migration tool for SQLAlchemy. Manages schema changes.

**Background Task** -- Async operation that runs outside the request-response cycle.

**CORS** -- Cross-Origin Resource Sharing. Controls which domains can access the API.

**Cursor Pagination** -- Pagination method using an opaque cursor for efficient page traversal.

**DocTree** -- Hierarchical representation of documentation files used by the indexer.

**Middleware** -- Request/response processing layer. Runs before and after route handlers.

**RBAC** -- Role-Based Access Control. Authorization model using roles and permissions.

**Refresh Token** -- Long-lived token used to obtain new access tokens without re-authentication.

**Soft Delete** -- Marks records as deleted without removing from the database.

**TTL** -- Time To Live. Duration before a cached value expires.

**Webhook** -- HTTP callback triggered by an event. Used for integrations.

See [Architecture](../repo/architecture.md) for system design concepts.
