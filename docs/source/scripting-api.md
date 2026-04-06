# Modules

## Table of Contents

- 🅼 [starlark\.tavern\_helpers](#starlark-tavern_helpers)

<a name="starlark-tavern_helpers"></a>
## 🅼 starlark\.tavern\_helpers

Tavern helper functions for Starlark scripts\.

This module provides built-in functions for controlling test execution
in Tavern's Starlark pipeline feature\.

Usage:
    load\("@tavern\_helpers\.star", "run\_stage", "re", "time", "log"\)

- **Functions:**
  - 🅵 [run\_stage](#starlark-tavern_helpers-run_stage)
- **Structs:**
  - 🆂 [re](#starlark-tavern_helpers-re)
  - 🆂 [time](#starlark-tavern_helpers-time)

### Functions

<a name="starlark-tavern_helpers-run_stage"></a>
### 🅵 starlark\.tavern\_helpers\.run\_stage

```python
def run_stage(name, continue_on_fail = False, extra_vars = None):
```

Execute a test stage by its ID and return the response\.

**Parameters:**

- **name**: Stage ID to execute \(must have 'id' key in YAML\)
- **continue_on_fail**: If True, return failed response instead of raising
an exception\. Default: False
- **extra_vars**: Optional dict of variables to merge into stage config

**Returns:**

- `A struct with properties`: - failed \(bool\): True if stage failed
    - success \(bool\): True if stage succeeded
    - request\_vars: Variables captured during request execution
    - stage\_name: Name of the executed stage

For HTTP responses, also includes:
    - body: Response body \(parsed JSON if Content-Type is application/json\)
    - status\_code: HTTP status code
    - headers: Response headers
    - cookies: Response cookies

**Examples:**

```python
# Run a stage by ID
resp = run_stage("get_cookie")
if resp.failed:
    fail("Stage failed")

# Continue on failure
resp = run_stage("try_login", continue_on_fail=True)
if resp.failed:
    log("Login failed, using fallback")
    run_stage("fallback_login")
```

### Structs

<a name="re"></a>
### 🆂 re

Regex utilities for pattern matching and text manipulation\.

Provides Python regex-style operations for use in Starlark scripts\.

Available methods:
    match\(pattern, string\): Match pattern at start of string
    search\(pattern, string\): Search for pattern anywhere in string
    sub\(pattern, repl, string\): Replace all pattern occurrences

**Examples:**

```python
load("@tavern_helpers.star", "re")

resp = run_stage("get_data")

# Extract version number
match = re.search("v(\d+)\.", resp.body)
if match == None:
    fail("Version not found")
version = match.groups[0]

# Replace values
new_url = re.sub("OLD", "NEW", original_url)
```

**Methods:**

<a name="starlark-tavern_helpers-re-match"></a>
#### 🅵 starlark\.tavern\_helpers\.re\.match

```python
def match(pattern, s):
```

Match a regex pattern at the beginning of string\.

**Parameters:**

- **pattern**: Regular expression pattern
- **s**: String to match against

**Returns:**

- `A struct with match details, or None if no match`: - group0: Full match \(group 0\)
- groups: List of captured groups
- start: Start position of match
- end: End position of match
<a name="starlark-tavern_helpers-re-search"></a>
#### 🅵 starlark\.tavern\_helpers\.re\.search

```python
def search(pattern, s):
```

Search for a regex pattern anywhere in string\.

**Parameters:**

- **pattern**: Regular expression pattern
- **s**: String to search in

**Returns:**

- `A struct with match details, or None if no match`: - group0: Full match \(group 0\)
- groups: List of captured groups
- start: Start position of match
- end: End position of match
<a name="starlark-tavern_helpers-re-sub"></a>
#### 🅵 starlark\.tavern\_helpers\.re\.sub

```python
def sub(pattern, repl, s):
```

Substitute occurrences of pattern in string\.

**Parameters:**

- **pattern**: Regular expression pattern
- **repl**: Replacement string
- **s**: String to process

**Returns:**

- String with all occurrences replaced
<a name="time"></a>
### 🆂 time

Time utilities for delays and timing operations\.

Available methods:
    sleep\(seconds\): Pause execution for given seconds

**Examples:**

```python
load("@tavern_helpers.star", "time")

for i in range(0, 3):
    resp = run_stage("poll", continue_on_fail=True)
    if not resp.failed:
        break
    time.sleep(1)  # Wait 1 second before retry
```

**Methods:**

<a name="starlark-tavern_helpers-time-sleep"></a>
#### 🅵 starlark\.tavern\_helpers\.time\.sleep

```python
def sleep(seconds):
```

Sleep for specified seconds\.

**Parameters:**

- **seconds**: Number of seconds to sleep \(can be float\)

**Examples:**

```python
time.sleep(0.5)  # Sleep for 500ms
```
