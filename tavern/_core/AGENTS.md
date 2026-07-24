# Core Module Knowledge Base

**Generated:** 2025-04-02

## Overview

Central module containing pytest integration, schema validation, test execution, and plugin system.

## Structure

```
tavern/_core/
├── pytest/           # Pytest integration
│   ├── file.py       # File discovery and loading
│   ├── item.py       # Test item (YamlItem)
│   ├── hooks.py      # Pytest hooks
│   └── util.py       # Utility functions
├── schema/           # JSON Schema validation
│   ├── files.py      # Schema file loading
│   └── extensions.py # Schema extensions
├── run.py            # Test execution engine
├── plugins.py        # Plugin base classes
├── loader.py         # YAML loader with includes
└── exceptions.py     # Custom exceptions
```

## Key Classes

| Class | Location | Purpose |
|-------|----------|---------|
| `YamlItem` | `pytest/item.py` | Pytest test item for YAML tests |
| `PluginHelperBase` | `plugins.py` | Base class for all plugins |
| `TavernArgParser` | `entry.py` | CLI argument parser |

## Conventions

- Plugin registration via entry points in `pyproject.toml`
- Exceptions inherit from `tavern._core.exceptions`
- Use `Box` for dict-like access to test data

## Where to Look

| Task | File |
|------|------|
| Add pytest hook | `pytest/hooks.py` |
| Modify test loading | `pytest/file.py` |
| Change schema | `schema/files.py` |
| Add plugin base | `plugins.py` |
