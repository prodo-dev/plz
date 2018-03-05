# Batman 🦇

*I am the night.*

## Using the CLI

First, create a configuration file called *batman.config* in your project directory:

    {
      "user": "alice",
      "project": "danger",
      "port": 5000,
      "image": "024444204267.dkr.ecr.eu-west-1.amazonaws.com/ml-pytorch",
      "command": ["python", "main.py"],
      "excluded_paths": [
        "env"
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
   export ENVIRONMENT_CIDR_BLOCK='10.0.<UNIQUE>.0/24'
   ```
   Check with others to make sure the CIDR block is unique and non-overlapping.
4. Run `make deploy-test`.
