from chalice import Chalice
import datetime, os
from tda import auth, client, utils
from tda.orders.equities import *
from tda.orders.options import *
from chalicelib.config import *
from chalicelib.login import *
from chalicelib.helpers import *

app = Chalice(app_name='AlgoTrading_Chalice')


@app.route('/')
def index():
    return {'hello': 'world'}

@app.route('/quote/{symbol}')
def quote(symbol):
    t = Login()
    response = t.get_quote(symbol).json()
    return response

@app.route('/equity/buy', methods=['POST'])
def equity_buy():
    t = Login()

    webhook_message = app.current_request.json_body
    if 'passphrase' not in webhook_message:
        return {
            'code': 'error',
            'message': 'unauthorized, passphrase not present'
        }
    if webhook_message['passphrase'] != PASSPHRASE:
        return {
            'code': 'error',
            'message': 'unauthorized, passphrase invalid'
        }

    balance = t.get_account(ACCOUNT_ID, fields=t.Account.Fields.POSITIONS).json()['securitiesAccount']['currentBalances']['cashAvailableForTrading']
    positions = t.get_account(ACCOUNT_ID, fields=t.Account.Fields.POSITIONS).json()['securitiesAccount']['positions']

    for pos in positions:
        if webhook_message['ticker'] == pos['instrument']['symbol']:
            return {
                'code': 'error',
                'message': 'already long in {}'.format(webhook_message['ticker'])
            }

    if webhook_message['price'] < balance:
        order_spec = equity_buy_limit(
            webhook_message['ticker'],
            webhook_message['quantity'],
            webhook_message['price']
        )

        r = t.place_order(ACCOUNT_ID, order_spec)
        order_id = utils.Utils(t, ACCOUNT_ID).extract_order_id(r)
        assert order_id is not None

        return {
            'code': 'success',
            'message': 'order placed, id={}'.format(order_id),
        }

    return {
        'code': 'error',
        'message': 'balance not enough to cover trade'
    }

@app.route('/equity/sell', methods=['POST'])
def equity_sell():
    t = Login()

    webhook_message = app.current_request.json_body
    if 'passphrase' not in webhook_message:
        return {
            'code': 'error',
            'message': 'unauthorized, passphrase not present'
        }
    if webhook_message['passphrase'] != PASSPHRASE:
        return {
            'code': 'error',
            'message': 'unauthorized, passphrase invalid'
        }

    positions = t.get_account(ACCOUNT_ID, fields=t.Account.Fields.POSITIONS).json()['securitiesAccount']['positions']
    for pos in positions:
        if webhook_message['ticker'] == pos['instrument']['symbol']:
            if webhook_message['price'] > pos['averagePrice']:
                order_spec = equity_sell_limit(
                    webhook_message['ticker'],
                    webhook_message['quantity'],
                    webhook_message['price']
                )

                r = t.place_order(ACCOUNT_ID, order_spec)
                order_id = utils.Utils(t, ACCOUNT_ID).extract_order_id(r)
                assert order_id is not None

                return {
                    'code': 'success',
                    'message': 'order placed, id={}'.format(order_id),
                }
            return {
                'code': 'error',
                'message': 'will not sell asset for less than purchase price'
            }
    return {
        'code': 'error',
        'message': 'must purchase asset before selling'
    }

@app.route('/option/chain/{symbol}')
def option_chain(symbol):
    t = Login()
    response = t.get_option_chain(symbol).json()
    return response

@app.route('/option/order', methods=['POST'])
def option_order():
    t = Login()

    webhook_message = app.current_request.json_body
    if 'passphrase' not in webhook_message:
        return {
            'code': 'error',
            'message': 'unauthorized, passphrase not present'
        }
    if webhook_message['passphrase'] != PASSPHRASE:
        return {
            'code': 'error',
            'message': 'unauthorized, passphrase invalid'
        }

    optionChain = t.get_option_chain(webhook_message['ticker']).json()[webhook_message['putCall']]
    filepath = 'viableOptions'
    content = webhook_message['ticker'] + webhook_message['putCall'] + str(datetime.datetime.now())
    writeFile(filepath, 'at', content)

    return {
        'code': 'printed',
        'message': 'hello'
    }

    # symbol = OptionSymbol(
    #     webhook_message['ticker'],
    #     webhook_message['expiry'],
    #     webhook_message['putCall'],
    #     webhook_message['strike']
    # ).build()
    # order_spec = option_buy_to_open_limit(
    #     symbol,
    #     webhook_message['quantity'],
    #     webhook_message['price']
    # ).build()

    # r = t.place_order(ACCOUNT_ID, order_spec)
    # order_id = utils.Utils(t, ACCOUNT_ID).extract_order_id(r)
    # assert order_id is not None

    # return {
    #     'code': 'success',
    #     'message': 'order placed, id={}'.format(order_id),
    # }

@app.route('/orders')
def get_orders():
    t = Login()
    current_positions = t.get_account(ACCOUNT_ID, fields=t.Account.Fields.POSITIONS).json()['securitiesAccount']['positions']
    return current_positions
