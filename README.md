# Batman 🦇

*I am the night.*

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

Create yourself a key with:

    ./machines/vpn/new-client-key.sh NAME@prodo.ai OUTPUT-FILE.zip

Unzip the zip file and load *prodo-ai.ovpn* into your favourite OpenVPN client.

  * On Windows, try [the official OpenVPN Client](https://openvpn.net/index.php/open-source/downloads.html).
  * If you're on macOS, try [Tunnelblick](https://www.tunnelblick.net/).
  * On Ubuntu, install openvpn (sudo apt install openvpn), uznip the files to */etc/openvpn* and start the *openvpn@prodo-ai* service (sudo service openvpn@prodo-ai start). If DNS doesn't work, in /etc/systemd/resolved.conf under [Resolve] add

    DNS=10.8.0.1 8.8.8.8 8.8.4.4

and then run

    sudo systemctl restart systemd-resolved
  * On Linux or macOS, you can install *openvpn* and then run *sudo openvpn prodo-ai.conf*.

One you're connected, you should be able to access everything inside the AWS VPC.
