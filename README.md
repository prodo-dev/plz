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

## Connecting to the VPN

Create yourself a key with:

    ./machines/vpn/new-client-key.sh NAME@prodo.ai OUTPUT-FILE.zip

Unzip the zip file and load *prodo-ai.ovpn* into your favourite OpenVPN client.

  * On Windows, try [the official OpenVPN Client](https://openvpn.net/index.php/open-source/downloads.html).
  * If you're on macOS, try [Tunnelblick](https://www.tunnelblick.net/).
  * On Ubuntu, copy the files to */etc/openvpn* and start the *openvpn@prodo-ai* service.
  * On Linux or macOS, you can install *openvpn* and then run *sudo openvpn prodo-ai.conf*.
  
One you're connected, you should be able to access everything inside the AWS VPC.
