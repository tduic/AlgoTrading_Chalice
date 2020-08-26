from chalice import Chalice
from constants import *
from login import Login
from tda import client

app = Chalice(app_name='AlgoTrading_Chalice')


@app.route('/')
def index():
    return {'hello': 'world'}

@app.route('/quote/{symbol}')
def quote(symbol):
    t = Login()
    response = t.get_quote(symbol).json()
    return response

@app.route('/option/chain/{symbol}')
def option_chain(symbol):
    t = Login()
    response = t.get_option_chain(symbol).json()
    return response

@app.route('option/order', methods=['POST'])
def option_order(symbol):
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

    order_spec = {
        'complexOrderStrategy': 'NONE',
        'orderType': 'LIMIT',
        'session': 'NORMAL',
        'price': '0.00',
        'duration': 'DAY',
        'orderStrategyType': 'SINGLE',
        'orderLegCollection': {
            'instruction': 'BUY_TO_OPEN',
            'quantity': 1,
            'instrument': {
                'symbol': 'AAPL_082820C500.0',
                'assetType': 'OPTION'
            }
        }
    }
    # 'price': webhook_message['price']
    # 'quantity': webhook_message['quantity']
    # 'symbol': webhook_message['symbol']
    response = t.place_order(ACCOUNT_ID, order_spec)
    return response

# example option order spec JSON
# {
#     'complexOrderStrategy': 'NONE',
#     'orderType': 'LIMIT',
#     'session': 'NORMAL',
#     'price': '6.45',
#     'duration': 'DAY',
#     'orderStrategyType': 'SINGLE',
#     'orderLegCollection': {
#         'instruction': 'BUY_TO_OPEN',
#         'quantity': 0,
#         'instrument': {
#             'symbol': 'MSFT_061220C182.5',
#             'assetType': 'OPTION'
#         }
#     }
# }
