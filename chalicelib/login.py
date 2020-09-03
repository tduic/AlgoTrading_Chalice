import os
from tda import auth, client
from chalicelib.config import *

def Login():
    t = auth.client_from_token_file(TOKEN_PATH, API_KEY)
    return t

def replaceToken():
    from selenium import webdriver
    from webdriver_manager.chrome import ChromeDriverManager
    with webdriver.Chrome(ChromeDriverManager().install()) as driver:
        t = auth.client_from_login_flow(
            driver, API_KEY, REDIRECT_URI, TOKEN_PATH)
    return t
