
# Tavern API Testing

Tavern is an advanced pytest based API testing framework for HTTP, MQTT or other protocols.

Note that Tavern **only** supports Python 2.7/3.4 and up. At the time of writing we
test against Python 2.7/3.4-3.7 and pypy/pypy3. Using Python 3 is strongly
advised over using Python 2, and support for Python 2 is likely to be dropped in
future.

## Why Tavern

Choosing an API testing framework can be tough. Tavern was started in 2017 to address some of our concerns with other tesing frameworks.

In short, we think the best things about Taven are:

### It's Lightweight.
Tavern is a small codebase which uses pytest under the hood.

### Easy to Write, Easy to Read and Understand.
The yaml syntax allows you to abstract what you need with anchors, whilst using `pytest.mark` to organise your tests. Your tests should become more maintainable as a result.

### Test Anything
From the simplest API test through to the most complex of requests, tavern remains readable and easy to extend. We're aiming for developers to not need the docs open all the time!

### Extensible
Almost all common test usecases are covered, but for everything else it's very easy to drop in to python/pytest to extend. Use fixtures, hooks and things you already know.

### Growing Ecosystem
Tavern is still in active development and is used by 100s of companies.

# Contents

* [Basic Concepts](basics.md)
* [HTTP Integration testing](http.md)
* [MQTT Integration testing](mqtt.md)
* [Plugins](plugins.md)
* [Debugging Tests](debugging.md)
* [Examples](examples.md)
* [Advanced Cookbook](cookbook.md)
