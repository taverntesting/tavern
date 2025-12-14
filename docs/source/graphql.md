# GraphQL integration testing

The GraphQL plugin allows you to test GraphQL APIs using Tavern. It provides specialized request and response handling
that understands GraphQL's unique structure and requirements.

## Important Note on Query Formatting

**GraphQL queries cannot use Tavern's standard variable formatting (curly braces `{}`)** because GraphQL syntax itself
uses curly braces. If you try to use formatting like `{variable}` in your GraphQL queries, it will fail because Tavern
will attempt to format them before sending the query.

**Instead, use GraphQL variables for any dynamic content:**

```yaml
# ✅ GOOD - Use GraphQL variables
stages:
  - name: Query user with variable
    graphql_request:
      url: "{graphql_server_url}/graphql"    # URL formatting works fine
      query: |
        query GetUser($id: ID!) {
          user(id: $id) {                     # GraphQL variables work fine
            id
            name
            email
          }
        }
      variables:
        id: "{user_id}"                      # Variables in the variables object support formatting

# ❌ BAD - Don't use formatting in queries
stages:
  - name: Query user with formatting in query
    graphql_request:
      url: "{graphql_server_url}/graphql"
      query: |
        query GetUser {
          user(id: "{user_id}") {             # This will fail - formatting in query
            id
            name
          }
        }
```

## Configuration

Configure GraphQL connection settings at the test level:

```yaml
---
test_name: GraphQL API tests

graphql:
  client:
    headers:
      Authorization: "Bearer {token}"
      User-Agent: "Tavern GraphQL Test"

stages:
  - name: Query data
    graphql_request:
    # ... request details
```

## Requests

### Basic Query

```yaml
stages:
  - name: Get user by ID
    graphql_request:
      url: "{graphql_server_url}/graphql"
      query: |
        query GetUser($id: ID!) {
          user(id: $id) {
            id
            name
            email
          }
        }
      variables:
        id: "1"
```

### Query with Variables

Use variables for dynamic data. Variables support standard Tavern formatting:

```yaml
stages:
  - name: Create user with test variables
    graphql_request:
      url: "{graphql_server_url}/graphql"
      query: |
        mutation CreateUser($name: String!, $email: String!) {
          createUser(name: $name, email: $email) {
            id
            name
            email
          }
        }
      variables:
        name: "{user_name}"        # Formatting works in variables
        email: "{user_email}"
```

### Query with Headers

```yaml
stages:
  - name: Authenticated query
    graphql_request:
      url: "{graphql_server_url}/graphql"
      headers:
        Authorization: "Bearer {auth_token}"
        Content-Type: "application/json"  # Automatically added if not present
      query: |
        query GetUserData {
          me {
            id
            name
          }
        }
```

### Query with Operation Name

```yaml
stages:
  - name: Named operation
    graphql_request:
      url: "{graphql_server_url}/graphql"
      query: |
        query GetUserProfile($id: ID!) {
          user(id: $id) {
            id
            name
            profile {
              bio
              avatar
            }
          }
        }
      operation_name: GetUserProfile      # Optional operation name
      variables:
        id: "1"
```

### Multiple Operations in One Query

```yaml
stages:
  - name: Multiple operations
    graphql_request:
      url: "{graphql_server_url}/graphql"
      query: |
        query GetUser($id: ID!) {
          user(id: $id) {
            id
            name
          }
        }

        mutation UpdateUser($id: ID!, $name: String!) {
          updateUser(id: $id, name: $name) {
            id
            name
          }
        }
      operation_name: GetUser           # Specify which operation to execute
      variables:
        id: "1"
```

> **Note**: While `operation_name` isn't required for most use cases, it becomes essential when you're using the
> `!include` tag to import an external GraphQL file that contains multiple operations. In such cases, `operation_name`
> helps identify which specific operation you want to execute from the included file.

## Responses

GraphQL responses follow the standard GraphQL format with `data` and/or `errors` at the top level:

### Successful Response

```yaml
stages:
  - name: Query user
    graphql_request:
      url: "{graphql_server_url}/graphql"
      query: |
        query GetUser($id: ID!) {
          user(id: $id) {
            id
            name
          }
        }
      variables:
        id: "1"
    graphql_response:
      json:
        data:
          user:
            id: "1"
            name: "John Doe"
```

### Response with Errors

```yaml
stages:
  - name: Query non-existent user
    graphql_request:
      url: "{graphql_server_url}/graphql"
      query: |
        query GetUser($id: ID!) {
          user(id: $id) {
            id
            name
          }
        }
      variables:
        id: "999"
    graphql_response:
      # status_code: 200  # GraphQL errors still return 200
      json:
        data:
          user: null
        errors:
          - message: "User not found"
```

### Error Response

```yaml
stages:
  - name: Invalid query
    graphql_request:
      url: "{graphql_server_url}/graphql"
      query: |
        query InvalidQuery {
          invalidField {
            id
          }
        }
    graphql_response:
      # status_code: 200  # Validation errors return 200
      json:
        errors:
          - message: "Cannot query field 'invalidField' on type 'Query'."
```

## Client options

If using the default `gql` backend for graphql,
default options can be passed to the underlying HTTP transport in the "gql" block at the top level fo a test.
The GraphQL configuration schema supports these options:

```yaml
gql:
  headers:
    string: string              # Default headers for all requests
```

For example, to make a query with an authorization header:

```yaml
---

test_name: Query with authorization header

gql:
  headers:
    Authorization: "Bearer test-token"

stages:
  - name: Query with authorization header
    graphql_request:
      ...
```

## Strictness

As described in the [strict key checking](./basics.md#strict-key-checking) section in the basics, GraphQL responses 
can use the `strict` key to check that the response contains all or some of the expected keys. See that section
for more details.

## Limitations

### Current Limitations

- **No WebSocket Support**: GraphQL subscriptions over WebSocket are not supported yet
- **Query Formatting**: Cannot use `{variable}` formatting in GraphQL queries themselves - use GraphQL variables instead
- **Streaming**: No support for streaming responses (defer/stream directives)

### Future Plans

- Improved error message formatting

## Error Handling

The GraphQL plugin provides specific error handling for common GraphQL scenarios:

### Response Structure Validation

Tavern automatically validates that GraphQL responses have the correct structure:

- Must contain only `data` or `errors` at the top level
- Cannot have other top-level keys

### Status Code Handling

GraphQL responses should always return HTTP 200 status codes, even for:

- Validation errors
- Business logic errors
- Missing required fields

Non-200 status codes indicate HTTP-level problems (authentication, network issues, etc.).
