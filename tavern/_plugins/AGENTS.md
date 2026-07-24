# Plugins Module Knowledge Base

**Generated:** 2025-04-02

## Overview

Protocol-specific backends for REST, MQTT, gRPC, and GraphQL. Each plugin implements the Tavern plugin interface.

## Structure

```
tavern/_plugins/
├── rest/             # HTTP/REST backend
│   ├── tavernhook.py # Plugin entry point
│   ├── request.py    # HTTP request handling
│   └── response.py   # HTTP response handling
├── mqtt/             # MQTT backend
│   ├── tavernhook.py
│   ├── client.py
│   └── request.py
├── grpc/             # gRPC backend
│   ├── tavernhook.py
│   ├── client.py
│   └── protos.py
├── graphql/          # GraphQL backend
│   ├── tavernhook.py
│   ├── client.py
│   └── request.py
└── common/           # Shared plugin utilities
    └── response.py
```

## Plugin Interface

Each plugin must implement `PluginHelperBase` and register via entry point:

```python
# pyproject.toml
[project.entry-points.tavern_http]
requests = "tavern._plugins.rest.tavernhook:TavernRestPlugin"
```

## Where to Look

| Protocol | Entry Point | Request | Response |
|----------|-------------|---------|----------|
| HTTP | `rest/tavernhook.py` | `rest/request.py` | `rest/response.py` |
| MQTT | `mqtt/tavernhook.py` | `mqtt/request.py` | `mqtt/response.py` |
| gRPC | `grpc/tavernhook.py` | `grpc/request.py` | `grpc/response.py` |
| GraphQL | `graphql/tavernhook.py` | `graphql/request.py` | `graphql/response.py` |

## Conventions

- Each plugin has `tavernhook.py` as entry point
- Plugins inherit from `PluginHelperBase` in `_core/plugins.py`
