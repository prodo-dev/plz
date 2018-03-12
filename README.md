# Batman 🦇

*I am the night.*

## Using the CLI

First, create a configuration file called *batman.config.json* in your project directory. Here's an example for running a fixture provided:

    {
      "user": "alice",
      "project": "test",
      "port": 5000,
      "image": "python:3-slim",
      "command": ["./cli/fixtures/test_configuration.py"],
      "excluded_paths": [
        ".git",
        ".git-crypt",
        "**/.terraform",
        "**/__pycache__",
        "**/env"
      ]
    }

Then run it from the same directory:

    <path to batman>/batman run

## Deploying a test environment

1. Clone this repository.
2. Install [direnv](https://direnv.net/).
3. Create a *.envrc* file in the root of this repository:
   ```
   export ENVIRONMENT_NAME='<YOUR NAME>'
   ```
4. Run `make deploy-test`.
