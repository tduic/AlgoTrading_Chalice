"""chalicelib: market-hours guard (real US holiday calendar), file helpers,
the S3-backed OAuth token plumbing in auth.py, and login.py — all against
stubbed boto3/tda/requests_oauthlib/selenium."""
import datetime
import pickle
import sys

import pytest
import pytz
from conftest import REDACTED, S3, Client, OAuth2Session

from chalicelib import auth, helpers, login
from chalicelib.config import API_KEY, REDIRECT_URI, TOKEN_PATH

ET = pytz.timezone("US/Eastern")


def et(*args):
    return ET.localize(datetime.datetime(*args))


# --- helpers -----------------------------------------------------------------------

@pytest.mark.parametrize("now, closed", [
    (et(2020, 8, 18, 9, 29, 59), True),      # Tuesday, before the open
    (et(2020, 8, 18, 9, 30), False),         # opening bell
    (et(2020, 8, 18, 12, 0), False),
    (et(2020, 8, 18, 16, 0), False),         # closing bell itself still open
    (et(2020, 8, 18, 16, 0, 1), True),       # after the close
    (et(2020, 8, 22, 12, 0), True),          # Saturday
    (et(2020, 8, 23, 12, 0), True),          # Sunday
    (et(2020, 7, 3, 12, 0), True),           # Independence Day (observed)
    (et(2020, 12, 25, 12, 0), True),         # Christmas
])
def test_after_hours(now, closed):
    assert helpers.afterHours(now) is closed


def test_after_hours_defaults_to_now():
    assert helpers.afterHours() in (True, False)


def test_read_write_file(tmp_path):
    p = tmp_path / "f"
    helpers.writeFile(p, "wt", "a")
    helpers.writeFile(p, "at", "b")
    assert helpers.readFile(p, "rt") == "a\nb\n"


# --- auth: API key + token storage -------------------------------------------------

def test_normalize_api_key():
    normalize = getattr(auth, "__normalize_api_key")
    assert normalize("ABC") == "ABC@AMER.OAUTHAP"
    assert normalize("ABC@AMER.OAUTHAP") == "ABC@AMER.OAUTHAP"


def test_token_updater_writes_pickle_to_s3():
    getattr(auth, "__token_updater")("ignored-path")({"access_token": "T"})
    assert pickle.loads(S3.objects[("tdtoken", "token")]) == {"access_token": "T"}


def test_client_from_access_functions_builds_refreshing_session():
    def writer(token):
        pass
    c = auth.client_from_access_functions("KEY", lambda: {"access_token": "A"}, writer)
    assert isinstance(c, Client) and c.api_key == "KEY@AMER.OAUTHAP"
    kw = c.session.kwargs
    assert kw["token"] == {"access_token": "A"}
    assert kw["auto_refresh_url"] == "https://api.tdameritrade.com/v1/oauth2/token"
    assert kw["auto_refresh_kwargs"] == {"client_id": "KEY@AMER.OAUTHAP"}
    assert kw["token_updater"] is writer
    assert REDACTED[-1] == {"access_token": "A"}
    c = auth.client_from_access_functions("KEY", lambda: {"access_token": "B"})
    assert "token_updater" not in c.session.kwargs


def test_client_from_token_file_reads_s3():
    S3.put_object(Body=pickle.dumps({"access_token": "FROM-S3"}),
                  Bucket="tdtoken", Key="token")
    c = auth.client_from_token_file("ignored", "KEY")
    assert c.session.kwargs["token"] == {"access_token": "FROM-S3"}


# --- auth: browser login flow -----------------------------------------------------

class Driver:
    def __init__(self, urls):
        self._urls = list(urls)
        self.visited = []

    def get(self, url):
        self.visited.append(url)

    @property
    def current_url(self):
        return self._urls.pop(0) if len(self._urls) > 1 else self._urls[0]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_login_flow_waits_for_redirect_and_stores_token(monkeypatch):
    monkeypatch.setattr(auth.time, "sleep", lambda s: None)
    OAuth2Session.fetched.clear()
    d = Driver(["about:blank", "https://auth.tdameritrade.com/x",
                "https://127.0.0.1/cb?code=abc"])
    c = auth.client_from_login_flow(d, "KEY", "https://127.0.0.1/cb", "path")
    assert d.visited == ["https://auth.tdameritrade.com/auth?client_id=KEY@AMER.OAUTHAP"]
    (url, kw), = OAuth2Session.fetched
    assert kw["authorization_response"] == "https://127.0.0.1/cb?code=abc"
    assert kw["client_id"] == "KEY@AMER.OAUTHAP" and kw["access_type"] == "offline"
    assert pickle.loads(S3.objects[("tdtoken", "token")])["access_token"] == "ACCESS"
    assert c.session.kwargs["token"]["refresh_token"] == "REFRESH"


def test_login_flow_accepts_https_upgrade_of_http_redirect(monkeypatch, capsys):
    monkeypatch.setattr(auth.time, "sleep", lambda s: None)
    d = Driver(["https://localhost/cb?code=1"])
    auth.client_from_login_flow(d, "KEY", "http://localhost/cb", "path")
    assert "WARNING" in capsys.readouterr().out


def test_login_flow_times_out(monkeypatch):
    monkeypatch.setattr(auth.time, "sleep", lambda s: None)
    with pytest.raises(auth.RedirectTimeoutError):
        auth.client_from_login_flow(Driver(["about:blank"]), "KEY",
                                    "https://127.0.0.1/cb", "path", max_waits=5)


def test_easy_client_paths(monkeypatch):
    monkeypatch.setattr(auth, "client_from_token_file", lambda p, k: "from-token")
    assert auth.easy_client("KEY", "uri", "path") == "from-token"

    def missing(p, k):
        raise FileNotFoundError(p)
    monkeypatch.setattr(auth, "client_from_token_file", missing)
    with pytest.raises(FileNotFoundError):
        auth.easy_client("KEY", "uri", "path")
    monkeypatch.setattr(auth, "client_from_login_flow",
                        lambda d, k, u, p: ("from-login", d.visited))
    assert auth.easy_client("KEY", "uri", "path",
                            webdriver_func=lambda: Driver(["x"])) == ("from-login", [])


# --- login.py ---------------------------------------------------------------------

def test_login_uses_s3_token(monkeypatch):
    seen = []
    monkeypatch.setattr(login.auth, "client_from_token_file",
                        lambda p, k: seen.append((p, k)) or "client")
    assert login.Login() == "client"
    assert seen == [(TOKEN_PATH, API_KEY)]


def test_replace_token_runs_browser_login(monkeypatch):
    driver = Driver(["x"])
    monkeypatch.setattr(sys.modules["selenium.webdriver"], "Chrome", lambda path: driver)
    flows = []
    monkeypatch.setattr(login.auth, "client_from_login_flow",
                        lambda d, k, u, p: flows.append((d, k, u, p)) or "fresh")
    assert login.replaceToken() == "fresh"
    assert flows == [(driver, API_KEY, REDIRECT_URI, TOKEN_PATH)]
