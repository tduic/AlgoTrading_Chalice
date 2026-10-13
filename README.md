# AlgoTrading_Chalice

A serverless algorithmic trading bot that turns inbound webhook alerts (e.g. from TradingView) into live orders on a TD Ameritrade brokerage account. Built with [AWS Chalice](https://aws.github.io/chalice/) and deployed to AWS Lambda + API Gateway.

## How it works

The app exposes a small HTTP API. Trade endpoints accept JSON webhook payloads, authenticate them with a shared passphrase, verify the market is open, and place limit orders through the [`tda-api`](https://tda-api.readthedocs.io/) client.

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Health check |
| `/quote/{symbol}` | GET | Get a real-time quote for a symbol |
| `/equity/buy` | POST | Place an equity buy limit order (webhook) |
| `/equity/sell` | POST | Place an equity sell limit order (webhook) |
| `/option/chain/{symbol}` | GET | Fetch an option chain |
| `/option/order` | POST | Inspect/place an option order (webhook) |
| `/orders` | GET | List current account positions |

### Safety & guardrails

- **Passphrase auth** — every trade webhook must include a matching `passphrase`, otherwise it's rejected.
- **Market hours check** — `afterHours()` blocks trades outside 09:30–16:00 ET, on weekends, and on NYSE market holidays (`holidays.financial_holidays('NYSE')`; early-close days are not modeled).
- **Position-aware** — won't double-buy a ticker it's already long, and won't sell below the position's average price.
- **Balance check** — refuses buys it can't cover with available cash.

### Authentication

OAuth tokens for the TD Ameritrade API are stored in and refreshed from an S3 bucket, so the Lambda can re-auth without manual intervention. A Selenium-based login flow (`replaceToken`) is provided for minting a fresh token locally.

## Webhook payload

```json
{
  "passphrase": "your-secret",
  "ticker": "AAPL",
  "quantity": 10,
  "price": 150.00
}
```

## Setup

```bash
pip install -r requirements.txt   # chalice, tda-api, holidays, pytz, webdriver_manager
chalice deploy                    # deploy to AWS Lambda + API Gateway
```

Configuration (API key, account ID, token path, redirect URI, passphrase) lives in `chalicelib/config.py`, which is gitignored. Copy `chalicelib/config.example.py` to `chalicelib/config.py` and fill in your own values.

> ⚠️ This is a personal project for educational purposes. Automated trading carries real financial risk — use at your own risk.
