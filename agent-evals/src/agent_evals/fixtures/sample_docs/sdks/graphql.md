# GraphQL API

Optional GraphQL layer for the DataForge API.

## Schema

```graphql
type Query {
  user(id: ID!): User
  users(page: Int, perPage: Int): UserConnection!
  product(id: ID!): Product
}

type Mutation {
  createUser(input: CreateUserInput!): User!
  updateUser(id: ID!, input: UpdateUserInput!): User!
}
```

## Queries

```graphql
query GetUser {
  user(id: "123") {
    id
    email
    name
    orders {
      id
      total
    }
  }
}
```

## Subscriptions

```graphql
subscription OrderUpdates {
  orderStatusChanged(userId: "123") {
    orderId
    status
  }
}
```

See [Authentication](../api/auth.md) for GraphQL auth headers.
