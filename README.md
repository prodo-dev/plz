# plz 🙏

*Say the magic word.*

## Using the CLI

See the CLI's *README.rst*.

## Deploying a test environment

1. Clone this repository.
2. Install [direnv](https://direnv.net/).
3. Create a *.envrc* file in the root of this repository:
   ```
   export ENVIRONMENT_NAME='<YOUR NAME>'
   ```
4. Run `make deploy-test`.

## Connecting to the VPN

1. Clone [*prodo-ai/inside*](https://github.com/prodo-ai/inside).
2. `cd` to that directory.
3. Create a file named *bucket* with the contents:
   ```
   inside.secrets.prodo.ai
   ```
4. Download the state by running `make retrieve`.
5. Create yourself a key with:
   ```
   ./openvpn/new-client-key.sh NAME@prodo.ai OUTPUT-FILE.zip
   ```
6. Connect to the VPN by following the instructions in the *README*.

One you're connected, you should be able to access everything inside the AWS VPC.
