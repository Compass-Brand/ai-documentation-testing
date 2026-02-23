# JavaScript SDK

Official JavaScript/TypeScript client for DataForge.

## Installation

```bash
npm install @dataforge/sdk
```

## Setup

```typescript
import { DataForge } from "@dataforge/sdk";

const client = new DataForge({
  baseUrl: "https://api.example.com",
  apiKey: "df_live_xxx",
});
```

## Usage

```typescript
// Async/await
const users = await client.users.list({ page: 1 });

// Create user
const user = await client.users.create({
  email: "bob@example.com",
  name: "Bob",
});
```

## TypeScript Types

All responses are fully typed:

```typescript
import type { User, PaginatedResponse } from "@dataforge/sdk";

const response: PaginatedResponse<User> = await client.users.list();
```

See [Authentication](../api/auth.md) for token-based auth in browser apps.
