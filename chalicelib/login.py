import pickle, os
from tda import client
from chalicelib import auth
from chalicelib.config import *

import boto3
s3 = boto3.client('s3')

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
