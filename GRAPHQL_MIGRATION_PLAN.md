# GraphQL Support Migration Plan

This document outlines the required changes to add GraphQL protocol support to Tavern, following the existing plugin architecture used for REST, gRPC, and MQTT protocols.

## Overview

Tavern currently supports three protocols through a plugin system:
- **REST** - HTTP-based REST APIs
- **gRPC** - gRPC protocol with protobuf
- **MQTT** - Message Queuing Telemetry Transport

This plan adds **GraphQL** as a fourth protocol, enabling testing of GraphQL APIs with the same level of integration as existing protocols.

## Implementation Structure

### 1. Plugin Directory Structure

Create new plugin directory following existing patterns:

```
tavern/_plugins/graphql/
├── __init__.py
├── tavernhook.py          # Main plugin entry point
├── request.py             # GraphQL request handling
├── response.py            # GraphQL response verification
├── client.py              # GraphQL client session management
└── jsonschema.yaml        # Validation schema
```

### 2. Entry Point Registration

**File:** `pyproject.toml`

Add new entry point namespace:

```toml
[project.entry-points.tavern_graphql]
graphql = "tavern._plugins.graphql.tavernhook"
```

### 3. Dependencies

**File:** `pyproject.toml`

**Core Dependencies:**
No additional dependencies required - GraphQL plugin will use existing `requests` library that's already a core Tavern dependency. This keeps the implementation lightweight and consistent with the REST plugin approach.

**Test Dependencies (optional):**
For testing infrastructure, GraphQL libraries can be added to dev dependencies:
```toml
[project.optional-dependencies]
dev = [
    # ... existing dev dependencies ...
    "graphene>=3,<4",  # For test server implementation
    "flask>=3,<4",     # For test server
]
```

**Optional Runtime Dependencies:**
WebSocket support for subscriptions can be optional:
```toml
[project.optional-dependencies]
graphql-ws = [
    "websockets>=12,<13",  # Only needed for GraphQL subscriptions
]
```

## Core Plugin Components

### 1. Plugin Hook (`tavernhook.py`)

Must implement required plugin interface:

```python
import logging
from os.path import abspath, dirname, join
import yaml

from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig
from tavern._core.plugins import PluginHelperBase

from .client import GraphQLClient
from .request import GraphQLRequest
from .response import GraphQLResponse

logger = logging.getLogger(__name__)

session_type = GraphQLClient
request_type = GraphQLRequest
request_block_name = "graphql_request"
verifier_type = GraphQLResponse
response_block_name = "graphql_response"

@staticmethod
def get_expected_from_request(
    response_block: dict, test_block_config: TestConfig, session: GraphQLClient
):
    if response_block is None:
        # GraphQL responses are optional for subscriptions
        return None

    f_expected = format_keys(response_block, test_block_config.variables)
    return f_expected

# Schema validation
schema_path: str = join(abspath(dirname(__file__)), "jsonschema.yaml")
with open(schema_path) as schema_file:
    schema = yaml.load(schema_file, Loader=yaml.SafeLoader)
```

### 2. GraphQL Client (`client.py`)

Session management for GraphQL using raw HTTP requests and WebSocket for subscriptions:

```python
import logging
from typing import Optional, Dict, Any
import requests
import json
import websockets
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class GraphQLClient:
    """GraphQL client for HTTP requests and WebSocket connections"""

    def __init__(self, **kwargs):
        self.session = requests.Session()
        self.default_headers = kwargs.get('headers', {})
        self.timeout = kwargs.get('timeout', 30)
        self.ws_url = kwargs.get('ws_url')

    def update_session(self, **kwargs):
        """Update session with new configuration"""
        if 'headers' in kwargs:
            self.session.headers.update(kwargs['headers'])

    def make_request(self, url: str, query: str, variables: Optional[Dict[str, Any]] = None,
                    operation_name: Optional[str] = None, method: str = "POST") -> requests.Response:
        """Execute GraphQL query over HTTP using raw requests"""
        payload = {
            'query': query,
            'variables': variables or {},
        }

        if operation_name:
            payload['operationName'] = operation_name

        headers = dict(self.default_headers)
        headers.update({'Content-Type': 'application/json'})

        if method.upper() == "GET":
            # For GET requests, encode query in URL parameters
            params = {'query': query}
            if variables:
                params['variables'] = json.dumps(variables)
            if operation_name:
                params['operationName'] = operation_name

            return self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout
            )
        else:
            # Default to POST for GraphQL queries
            return self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

    @contextmanager
    def subscription(self, url: str, query: str, variables: Optional[Dict[str, Any]] = None):
        """Context manager for GraphQL subscriptions over WebSocket"""
        ws_url = url.replace('http://', 'ws://').replace('https://', 'wss://')

        payload = {
            'type': 'start',
            'payload': {
                'query': query,
                'variables': variables or {},
            }
        }

        with websockets.connect(ws_url) as websocket:
            websocket.send(json.dumps(payload))
            yield websocket
```

### 3. GraphQL Request (`request.py`)

Request handling inheriting from `BaseRequest`:

```python
import logging
from typing import Any, Dict, Optional
import box

from tavern._core import exceptions
from tavern._core.dict_util import format_keys, deep_dict_merge
from tavern._core.pytest.config import TestConfig
from tavern.request import BaseRequest

from .client import GraphQLClient

logger = logging.getLogger(__name__)

class GraphQLRequest(BaseRequest):
    """GraphQL request implementation"""

    def __init__(self, session: GraphQLClient, rspec: dict, test_block_config: TestConfig):
        self.session = session
        self.rspec = rspec
        self.test_block_config = test_block_config

        # Format request spec with test variables
        self._formatted_rspec = format_keys(rspec, test_block_config.variables)

        # Validate required fields
        self._validate_request()

    def _validate_request(self):
        """Validate GraphQL request structure"""
        if 'query' not in self._formatted_rspec:
            raise exceptions.MissingKeysError("GraphQL request must contain 'query' field")

        if 'url' not in self._formatted_rspec:
            raise exceptions.MissingKeysError("GraphQL request must contain 'url' field")

    @property
    def request_vars(self) -> box.Box:
        """Variables used in the request"""
        return box.Box({
            'url': self._formatted_rspec['url'],
            'query': self._formatted_rspec['query'],
            'variables': self._formatted_rspec.get('variables', {}),
            'operation_name': self._formatted_rspec.get('operation_name'),
            'headers': self._formatted_rspec.get('headers', {}),
        })

    def run(self):
        """Execute GraphQL request"""
        try:
            # Update session headers if provided
            if 'headers' in self._formatted_rspec:
                self.session.update_session(headers=self._formatted_rspec['headers'])

            # Execute request
            response = self.session.make_request(
                url=self._formatted_rspec['url'],
                query=self._formatted_rspec['query'],
                variables=self._formatted_rspec.get('variables'),
                operation_name=self._formatted_rspec.get('operation_name')
            )

            logger.debug("GraphQL response: %s", response.text)
            return response

        except Exception as e:
            logger.exception("Error executing GraphQL request")
            raise exceptions.TavernException(f"GraphQL request failed: {e}") from e
```

### 4. GraphQL Response (`response.py`)

Response verification inheriting from `BaseResponse`:

```python
import logging
from typing import Any, Dict, Optional

from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys
from tavern._core.pytest.config import TestConfig
from tavern.response import BaseResponse

logger = logging.getLogger(__name__)

class GraphQLResponse(BaseResponse):
    """GraphQL response verification"""

    def __init__(self, session, name: str, expected: Dict[str, Any], test_block_config: TestConfig):
        super().__init__(session, name, expected, test_block_config)
        self.test_block_config = test_block_config

    def _validate_response_format(self, response: Any):
        """Validate GraphQL response structure"""
        try:
            response_json = response.json()

            # Check for GraphQL-specific errors
            if 'errors' in response_json:
                logger.warning("GraphQL errors in response: %s", response_json['errors'])

            # Check for data field
            if 'data' not in response_json and 'errors' not in response_json:
                raise exceptions.BadSchemaError(
                    "GraphQL response must contain 'data' or 'errors' field"
                )

        except ValueError as e:
            raise exceptions.BadSchemaError(f"Invalid JSON response: {e}") from e

    def verify(self, response: Any):
        """Verify GraphQL response against expected"""
        # Basic HTTP status verification
        self._verify_status_code(response)

        # GraphQL-specific validation
        self._validate_response_format(response)

        # Standard response verification
        return super().verify(response)
```

### 5. JSON Schema Validation (`jsonschema.yaml`)

```yaml
# GraphQL Request/Response Schema
name: GraphQL
description: GraphQL API testing schema

# Request schema
request:
  type: map
  mapping:
    graphql_request:
      type: map
      required: true
      mapping:
        url:
          type: str
          required: true
          pattern: "^https?://.+$"
        query:
          type: str
          required: true
        variables:
          type: any
          required: false
        operation_name:
          type: str
          required: false
        headers:
          type: map
          required: false
          mapping:
            regex;.+:
              type: str

# Response schema
response:
  type: map
  mapping:
    graphql_response:
      type: map
      required: false
      mapping:
        status_code:
          type: int
          required: true
          range:
            min: 200
            max: 599
        json:
          type: any
          required: false
        headers:
          type: map
          required: false
          mapping:
            regex;.+:
              type: any
        verify:
          type: bool
          required: false
          default: true
```

## Testing Requirements

### 1. Unit Tests

**Directory:** `tests/unit/plugins/graphql/`

Test files needed:
- `test_graphql_client.py` - Test client functionality
- `test_graphql_request.py` - Test request handling
- `test_graphql_response.py` - Test response verification
- `test_tavernhook.py` - Test plugin integration

### 2. Integration Tests

**Directory:** `example/graphql/`

Test scenarios:
- Basic query execution
- Mutation operations
- Variable substitution
- Error handling
- Authentication
- Subscription handling (if implemented)

### 3. Test Server

**File:** `example/graphql/server.py`

Mock GraphQL server for testing (can use GraphQL libraries for test infrastructure):
```python
from flask import Flask, request, jsonify
import graphene

class Query(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value="stranger"))

    def resolve_hello(self, info, name):
        return f"Hello {name}!"

class Mutation(graphene.ObjectType):
    echo = graphene.String(text=graphene.String(required=True))

    def resolve_echo(self, info, text):
        return text

schema = graphene.Schema(query=Query, mutation=Mutation)

app = Flask(__name__)

@app.route("/graphql", methods=["POST"])
def graphql():
    data = request.get_json()
    result = schema.execute(data["query"], variables=data.get("variables"))
    return jsonify({"data": result.data, "errors": [str(e) for e in result.errors] if result.errors else None})
```

## Integration Points

### 1. Plugin Loading

The plugin system automatically detects GraphQL plugins when:
- Test stages contain `graphql_request` blocks
- Backend configuration includes GraphQL

### 2. Configuration

GraphQL configuration in test files:
```yaml
# tavern.yaml
test_name: GraphQL API tests
stages:
  - name: Query user
    graphql_request:
      url: "{api_base}/graphql"
      query: |
        query GetUser($id: ID!) {
          user(id: $id) {
            id
            name
            email
          }
        }
      variables:
        id: "123"
    graphql_response:
      status_code: 200
      json:
        data:
          user:
            id: "123"
            name: "John Doe"
            email: "john@example.com"
```

### 3. Session Management

GraphQL sessions are managed like other protocols:
- Session configuration in test setup
- Connection reuse across stages
- Authentication handling

## Implementation Phases

### Phase 1: Core GraphQL Support (Priority 1)

**Features:**
- Basic query execution over HTTP
- Variable substitution
- JSON response handling
- Basic error handling
- Unit test coverage

**Files to create:**
- `tavern/_plugins/graphql/` directory structure
- Core plugin components
- Basic JSON schema
- Unit tests

### Phase 2: Advanced Features (Priority 2)

**Features:**
- Mutation support
- Authentication headers
- Advanced error handling
- Integration tests
- Test server implementation

**Files to modify:**
- Enhanced client with auth support
- Extended response verification
- Integration test suite

### Phase 3: Subscription Support (Priority 3)

**Features:**
- WebSocket-based subscriptions
- Subscription-specific validation

**Files to create:**
- WebSocket client implementation
- Request/response handling
- Subscription test utilities

### Phase 4: Documentation and Polish (Priority 4)

**Features:**
- Comprehensive documentation
- Examples and tutorials
- Performance optimization
- Code review and refinement

**Files to modify:**
- Documentation files
- Example tests
- README updates

## Migration Checklist

### Pre-Implementation

- [ ] Review existing plugin patterns thoroughly
- [ ] Choose GraphQL client library (sgqlc, graphql-core, etc.)
- [ ] Define test scenarios and edge cases
- [ ] Set up development environment with dependencies

### Implementation

- [ ] Create plugin directory structure
- [ ] Implement core plugin hook
- [ ] Develop GraphQL client class
- [ ] Create request handler
- [ ] Implement response verifier
- [ ] Add JSON schema validation
- [ ] Register entry points
- [ ] Add optional dependencies

### Testing

- [ ] Write comprehensive unit tests
- [ ] Create integration test suite
- [ ] Implement test GraphQL server
- [ ] Add end-to-end test scenarios
- [ ] Test error conditions
- [ ] Verify compatibility with existing features

### Documentation

- [ ] Update main documentation
- [ ] Create GraphQL-specific guide
- [ ] Add example test files
- [ ] Document configuration options
- [ ] Update changelog and release notes

### Quality Assurance

- [ ] Code review and refactoring
- [ ] Performance testing
- [ ] Security audit
- [ ] Compatibility testing
- [ ] Final integration testing

## Success Criteria

1. **Functional Parity**: GraphQL support matches feature completeness of existing protocols
2. **Test Coverage**: >90% code coverage for GraphQL plugin
3. **Documentation**: Complete user documentation and examples
4. **Performance**: No significant performance impact on existing functionality
5. **Compatibility**: Backward compatibility with existing Tavern features
6. **Quality**: Pass all existing tests and new GraphQL-specific tests

## Risks and Mitigations

### Risk 1: WebSocket Complexity
**Issue:** GraphQL subscriptions require WebSocket handling, increasing complexity
**Mitigation:** Implement basic HTTP queries first, add subscriptions in later phase

### Risk 2: Client Library Compatibility
**Issue:** GraphQL client library may not integrate well with existing patterns
**Mitigation:** Evaluate multiple libraries, create custom client if needed

### Risk 3: Performance Impact
**Issue:** Additional plugin may affect overall test performance
**Mitigation:** Lazy loading of GraphQL components, efficient connection reuse

### Risk 4: Breaking Changes
**Issue:** New plugin may inadvertently break existing functionality
**Mitigation:** Comprehensive regression testing, phased rollout

## Conclusion

This migration plan provides a structured approach to adding GraphQL support to Tavern while maintaining consistency with existing architecture and ensuring high quality implementation. The phased approach allows for incremental development and testing, reducing risks while delivering value to users progressively.

The plugin architecture of Tavern makes this addition straightforward, and following existing patterns will ensure seamless integration with the current ecosystem.