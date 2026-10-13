"""Test bootstrap for a 2020 Chalice/TD Ameritrade webhook bot.

TD Ameritrade's API no longer exists and the app must never reach AWS, a
broker or a browser from a test, so before any project import this installs
stub modules in sys.modules for: chalice (a tiny route registry), tda (auth,
client, utils, orders, debug), boto3 (an in-memory S3), requests_oauthlib,
selenium and webdriver_manager. chalicelib/config.py is gitignored (it holds
real credentials), so tests load chalicelib/config.example.py in its place.

`holidays` and `pytz` are real (pure-Python) deps: the market-hours guard is
tested against the real NYSE holiday calendar.
"""
import pathlib
import runpy
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    parent, _, child = name.rpartition(".")
    if parent:
        setattr(sys.modules[parent], child, mod)
    return mod


def _unreachable(*a, **k):
    raise AssertionError("tests must not reach the real broker/browser/AWS")


# --- chalice -----------------------------------------------------------------

class Chalice:
    def __init__(self, app_name):
        self.app_name = app_name
        self.routes = {}
        self.current_request = None

    def route(self, path, methods=("GET",)):
        def register(fn):
            for method in methods:
                self.routes[(path, method)] = fn
            return fn
        return register


_stub("chalice", Chalice=Chalice)


# --- boto3 (in-memory S3) ----------------------------------------------------

class _Body:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Body, Bucket, Key):
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        return {"Body": _Body(self.objects[(Bucket, Key)])}


S3 = FakeS3()
_stub("boto3", client=lambda service: S3 if service == "s3" else _unreachable())


# --- tda ---------------------------------------------------------------------

class Client:
    def __init__(self, api_key, session):
        self.api_key, self.session = api_key, session


class Utils:
    def __init__(self, client, account_id):
        self.client, self.account_id = client, account_id

    def extract_order_id(self, response):
        return getattr(response, "order_id", None)


REDACTED = []


def equity_buy_limit(symbol, quantity, price):
    return {"side": "BUY", "symbol": symbol, "quantity": quantity, "price": price}


def equity_sell_limit(symbol, quantity, price):
    return {"side": "SELL", "symbol": symbol, "quantity": quantity, "price": price}


_stub("tda")
_stub("tda.auth", client_from_token_file=_unreachable,
      client_from_login_flow=_unreachable)
_stub("tda.client", Client=Client)
_stub("tda.utils", Utils=Utils)
_stub("tda.debug", register_redactions=REDACTED.append)
_stub("tda.orders")
_stub("tda.orders.equities", equity_buy_limit=equity_buy_limit,
      equity_sell_limit=equity_sell_limit)
_stub("tda.orders.options")


# --- requests_oauthlib ---------------------------------------------------------

class OAuth2Session:
    fetched = []

    def __init__(self, client_id, **kwargs):
        self.client_id, self.kwargs = client_id, kwargs

    def authorization_url(self, url):
        return f"{url}?client_id={self.client_id}", "state-123"

    def fetch_token(self, url, **kwargs):
        OAuth2Session.fetched.append((url, kwargs))
        return {"access_token": "ACCESS", "refresh_token": "REFRESH"}


_stub("requests_oauthlib", OAuth2Session=OAuth2Session)


# --- selenium / webdriver_manager ------------------------------------------------

class _ChromeDriverManager:
    def install(self):
        return "/fake/chromedriver"


_stub("selenium")
_stub("selenium.webdriver", Chrome=_unreachable)
_stub("webdriver_manager")
_stub("webdriver_manager.chrome", ChromeDriverManager=_ChromeDriverManager)


# --- chalicelib.config (gitignored) -> config.example.py ------------------------

import chalicelib  # noqa: E402

_stub("chalicelib.config", **{
    k: v for k, v in runpy.run_path(str(ROOT / "chalicelib" / "config.example.py")).items()
    if k.isupper()})
