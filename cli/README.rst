==========
Plz CLI
==========

*Say the magic word.*

Dependencies
============

This application depends on Python 3.6 or newer.

Usage
=====

First, create a configuration file called *plz.config.json* in your project directory.

Here's an example::

    {
      "user": "alice",
      "project": "test",
      "host": "plz.inside.your.corp",
      "port": 5000,
      "image": "python:3-slim",
      "command": ["src/main.py"],
      "excluded_paths": [
        ".git",
        "venv",
        "**/__pycache__"
      ]
    }

Then run it from the same directory::

    plz run
