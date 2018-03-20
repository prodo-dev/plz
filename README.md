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

Create yourself a key with:

```
./machines/vpn/new-client-key.sh NAME@prodo.ai OUTPUT-FILE.zip
```

Unzip the file and load *prodo-ai.conf* into your favourite OpenVPN client.

  * On Windows, try [the official OpenVPN Client](https://openvpn.net/index.php/open-source/downloads.html).
  * If you're on macOS, try [Tunnelblick](https://www.tunnelblick.net/).
  * On Ubuntu:
    1. Install OpenVPN: `sudo apt install openvpn`.
    2. Unzip the files to */etc/openvpn* .
    3. Start the *openvpn@prodo-ai* service: `sudo service openvpn@prodo-ai start`.
    4. Find out if DNS works by verifying that running `dig +short plz.inside.prodo.ai` returns an IP address.

       If it doesn't resolve, edit */etc/systemd/resolved.conf* and, in the `[Resolve]` section, add:

       ```
       DNS=10.8.0.1 8.8.8.8 8.8.4.4
       ```

       Then run `sudo systemctl restart systemd-resolved` to restart the DNS service.

One you're connected, you should be able to access everything inside the AWS VPC.
