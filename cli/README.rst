==========
Batman CLI
==========

*I am the night.*

Dependencies
============

This application depends on Python 3.6 or newer.

Usage
=====

First, create a configuration file called *batman.config.json* in your project directory.

Here's an example::

    {
      "user": "alice",
      "project": "test",
      "host": "batman.inside.your.corp",
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

    batman run
