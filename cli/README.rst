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
      "input": "file:///data/for/processing",
      "excluded_paths": [
        "not/interesting"
      ],
      "included_paths": [
        "not/interesting/except/this/one"
      ]
    }

If you're using Git, ``plz`` will automatically exclude the same files as Git. You can override this by setting ``"included_paths"``, or set the ``"exclude_gitignored_files"`` property to ``false`` to disable this.

To run your application, run the following command from the same directory::

    plz run

If you want to provide parameters to your run, pass them in with ``--parameters=path/to/parameters.json``. They must be in the form of a JSON file.

The configuration file path will be passed into the application via the ``CONFIGURATION_FILE`` environment variable.

It will look something like this::

    {
      "input_directory": "...",
      "output_directory": "...",
      "parameters": {
        ...
      }
    }

If you've specified an input, it will be uploaded and put in a directory you can find by accessing the ``"input_directory"`` property in the configuration.

Any files you write to the directory in ``"output_directory"`` will be captured and downloaded at the end of the run.

You can read the parameters just as you usually would.

Take a look at the examples in the *test* directory to see how you can easily write an application compatible with ``plz``.
