# TollDirect Windows demonstration

Commit `8736148`. Simulation only. No network connection is required.

## 1. Install Python

1. Download Python 3.10 or newer from [python.org/downloads/windows](https://www.python.org/downloads/windows/).
2. Run the installer.
3. Check **Add python.exe to PATH**.
4. Finish the installation.

## 2. Get the code

If Git is installed:

```bat
git clone https://github.com/water778/tolldirect.git
cd tolldirect
```

Otherwise download the repository as a ZIP from GitHub, extract it, and open Command Prompt in the extracted folder.

## 3. Confirm the environment

```bat
python --version
cd backend
python -m unittest discover -s tests -q
```

Expected result: `Ran 58 tests` and `OK`.

If `python` is not recognized, use `py -3` in every command below.

## 4. Run the complete demonstration

```bat
cd backend
python poc_demo.py
```

The script:

- creates a local SQLite file in the Windows temporary directory
- does not contact Uber, Lyft, E-ZPass, a bank, or a card network
- prints the matched trip, payment stages, both zero-balance scenarios, duplicate blocking, and the ledger

## 5. Read the printed result

Look for these lines:

- `Matched trip T-UBER-100 to E-ZPass EZ-MA-441`
- `Status after official post: reconciled  amount 350 cents`
- `Driver bank account: not present`
- `Duplicates blocked: 1`
- `Passenger charges: 1`
- `balanced: True`
- ledger rows `passenger_charged` and `credited_to_ezpass` for `GX-TOBIN-2201`

The readable report of that same $3.50 toll is in `docs/TRANSACTION-REPORT.md`.

## 6. Optional timing-only view

```bat
python demo_timing.py
```

This prints authorization, capture, settlement, and confirmed simulated credit. Authorization does not change the E-ZPass balance. Real-time external E-ZPass credit is printed as not verified.

## What this does not do

- It does not move money.
- It does not log in to E-ZPass or a rideshare platform.
- It does not prove that MassDOT can accept an external credit.
- It does not prove that a credit can arrive before a toll is assessed.
