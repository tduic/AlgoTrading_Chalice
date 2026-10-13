"""Webhook routes in app.py, driven through the stub Chalice route registry
with a fake TD client. Verifies the guardrails (market hours, passphrase,
position and balance checks) gate every order, and that orders are built
from the webhook payload."""
import types

import pytest

import app as app_module
from chalicelib.config import PASSPHRASE

APP = app_module.app


class Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeTD:
    Account = types.SimpleNamespace(Fields=types.SimpleNamespace(POSITIONS="positions"))

    def __init__(self, cash=10000.0, positions=None, chain=None, order_id="ORD-1"):
        self.cash, self.positions = cash, positions or []
        self.account_reads = 0
        self.chain = chain or {"callExpDateMap": {"x": 1}, "putExpDateMap": {"y": 2}}
        self.order_id = order_id
        self.placed = []

    def get_quote(self, symbol):
        return Resp({symbol: {"lastPrice": 123.45}})

    def get_account(self, account_id, fields=None):
        self.account_reads += 1
        return Resp({"securitiesAccount": {
            "currentBalances": {"cashAvailableForTrading": self.cash},
            "positions": self.positions}})

    def get_option_chain(self, symbol):
        return Resp(self.chain)

    def place_order(self, account_id, spec):
        self.placed.append((account_id, spec))
        return types.SimpleNamespace(order_id=self.order_id)


@pytest.fixture
def td(monkeypatch):
    client = FakeTD()
    monkeypatch.setattr(app_module, "Login", lambda: client)
    monkeypatch.setattr(app_module, "afterHours", lambda: False)
    return client


def call(path, method="GET", body=None, **kwargs):
    APP.current_request = types.SimpleNamespace(json_body=body)
    return APP.routes[(path, method)](**kwargs)


def hook(**extra):
    body = {"passphrase": PASSPHRASE, "ticker": "AAPL", "quantity": 10, "price": 150.0}
    body.update(extra)
    return body


def test_routes_registered():
    assert set(APP.routes) == {
        ("/", "GET"), ("/quote/{symbol}", "GET"), ("/equity/buy", "POST"),
        ("/equity/sell", "POST"), ("/option/chain/{symbol}", "GET"),
        ("/option/order", "POST"), ("/orders", "GET")}
    assert APP.app_name == "AlgoTrading_Chalice"


def test_index():
    assert call("/") == {"hello": "world"}


def test_read_only_routes(td):
    assert call("/quote/{symbol}", symbol="AAPL") == {"AAPL": {"lastPrice": 123.45}}
    assert call("/option/chain/{symbol}", symbol="AAPL") == td.chain
    td.positions = [{"instrument": {"symbol": "MSFT"}}]
    assert call("/orders") == td.positions


# --- shared guardrails ------------------------------------------------------------

TRADE_ROUTES = ["/equity/buy", "/equity/sell", "/option/order"]


@pytest.mark.parametrize("path", TRADE_ROUTES)
def test_after_hours_blocks_trading(td, monkeypatch, path):
    monkeypatch.setattr(app_module, "afterHours", lambda: True)
    assert call(path, "POST", hook()) == {"code": "error", "message": "markets are not open"}
    assert td.placed == []


@pytest.mark.parametrize("path", TRADE_ROUTES)
def test_passphrase_missing_or_wrong(td, path):
    body = hook()
    del body["passphrase"]
    assert "passphrase not present" in call(path, "POST", body)["message"]
    assert "passphrase invalid" in call(path, "POST", hook(passphrase="nope"))["message"]
    assert td.placed == []


# --- /equity/buy ---------------------------------------------------------------

def test_buy_places_limit_order(td):
    got = call("/equity/buy", "POST", hook())
    assert got == {"code": "success", "message": "order placed, id=ORD-1"}
    (account, spec), = td.placed
    assert account == app_module.ACCOUNT_ID
    assert spec == {"side": "BUY", "symbol": "AAPL", "quantity": 10, "price": 150.0}


def test_buy_refuses_when_already_long(td):
    td.positions = [{"instrument": {"symbol": "AAPL"}, "averagePrice": 100.0}]
    got = call("/equity/buy", "POST", hook())
    assert got == {"code": "error", "message": "already long in AAPL"}
    assert td.placed == []


def test_buy_refuses_when_price_exceeds_cash(td):
    td.cash = 100.0
    got = call("/equity/buy", "POST", hook(price=150.0))
    assert got["message"] == "balance not enough to cover trade" and td.placed == []


def test_buy_compares_total_cost_not_share_price_to_cash(td):
    # Regression: 10 shares at $150 = $1,500 against $1,000 cash used to pass
    # because only the $150 share price was compared with the balance.
    td.cash = 1000.0
    got = call("/equity/buy", "POST", hook(quantity=10, price=150.0))
    assert got["message"] == "balance not enough to cover trade" and td.placed == []
    got = call("/equity/buy", "POST", hook(quantity=6, price=150.0))   # $900
    assert got["code"] == "success" and len(td.placed) == 1


def test_buy_reads_account_once(td):
    call("/equity/buy", "POST", hook(quantity=1))
    assert td.account_reads == 1


def test_buy_requires_an_order_id(td):
    td.order_id = None
    with pytest.raises(AssertionError):
        call("/equity/buy", "POST", hook())


# --- /equity/sell ----------------------------------------------------------------

def test_sell_requires_position(td):
    got = call("/equity/sell", "POST", hook())
    assert got == {"code": "error", "message": "must purchase asset before selling"}


def test_sell_never_below_average_price(td):
    td.positions = [{"instrument": {"symbol": "AAPL"}, "averagePrice": 150.0}]
    got = call("/equity/sell", "POST", hook(price=150.0))
    assert "less than purchase price" in got["message"] and td.placed == []


def test_sell_places_limit_order_above_cost(td):
    td.positions = [{"instrument": {"symbol": "MSFT"}, "averagePrice": 1.0},
                    {"instrument": {"symbol": "AAPL"}, "averagePrice": 140.0}]
    got = call("/equity/sell", "POST", hook(price=150.0, quantity=5))
    assert got == {"code": "success", "message": "order placed, id=ORD-1"}
    assert td.placed[0][1] == {"side": "SELL", "symbol": "AAPL", "quantity": 5,
                               "price": 150.0}


# --- /option/order -----------------------------------------------------------------

def test_option_order_only_prints_chain(td, capsys):
    got = call("/option/order", "POST", hook(putCall="callExpDateMap"))
    assert got == {"code": "success", "message": "printed AAPL option chain"}
    assert capsys.readouterr().out.strip() == "{'x': 1}"
    assert td.placed == []                      # order placement is commented out
