# GraphQL Example with Strawberry

This example demonstrates how to use GraphQL with Tavern for testing, using a server implementation built
with [Strawberry](https://strawberry.rocks/).

## Server Features

The example GraphQL server (`tavern_graphql_example/server.py`) implements:

- **Query operations**: Fetch users, posts, and user posts
- **Mutation operations**: Create and update users and posts
- **Subscription support**: Real-time updates for user changes
- **Authentication**: Bearer token authentication on certain endpoints

## Tests

The `tests/` directory contains various Tavern test files demonstrating:

- Basic GraphQL queries
- Mutations with variables
- Subscription handling
- Authentication flows
- Error handling scenarios

You can run the tests using Tavern to verify the GraphQL server behaves as expected.