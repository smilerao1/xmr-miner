# Simple Monero CPU Miner

An open source educational Monero miner written in Python.
Connects to the MoneroOcean mining pool using the Stratum protocol.

## Requirements
- Python 3.7 or higher
- Windows / Linux / Mac

## Setup

1. Get a Monero wallet at https://mymonero.com
2. Open `miner.py` and replace `YOUR_WALLET_ADDRESS_HERE` with your wallet address
3. Run: `python miner.py`

## Configuration

Edit the top of `miner.py`:

| Setting | Description |
|---------|-------------|
| WALLET  | Your Monero wallet address |
| WORKER  | A name for your miner |
| THREADS | Number of CPU threads (start with 2) |

## Check your earnings

Visit https://moneroocean.stream and enter your wallet address.

## Note

This is an educational project. For maximum performance use XMRig.

## License
MIT
