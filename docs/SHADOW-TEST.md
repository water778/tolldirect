# TollDirect shadow test on iPhone

Simulation only. No Uber login, no E-ZPass login, and no credentials.

## What it does

You enter redacted trip and toll amounts. The existing Python engine compares them and shows the simulated passenger-to-E-ZPass flow. A full card number or a password field is rejected.

## Secure iPhone test

This is not a public deployment. The page stays on your private network.

1. On a computer on the same private Wi-Fi as the iPhone, open the `backend` folder.
2. Run:

```bat
python shadow.py --lan
```

3. Find the computer's private address. On Windows:

```bat
ipconfig
```

Use the IPv4 address on the Wi-Fi adapter, for example `192.168.1.25`.

4. On the iPhone 13, open Safari and go to:

```text
http://192.168.1.25:8765
```

Replace the address with the computer's private address.

5. Enter only redacted values: a short trip reference, a vehicle code, the E-ZPass ending, the gantry, and the two dollar amounts.

## Do not

- Do not forward port 8765 to the internet.
- Do not enter a password, PIN, full card number, or full E-ZPass account number.
- Do not treat the result as a real charge or a real E-ZPass credit.

To stop the server, press Ctrl+C in the terminal.
