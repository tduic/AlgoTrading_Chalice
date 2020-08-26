from chalice import Chalice
from tda import client
from tda import utils
from tda.orders.options import *
from chalicelib.constants import *
from chalicelib.login import Login

app = Chalice(app_name='AlgoTrading_Chalice')


@app.route('/')
def index():
    return {'hello': 'world'}

# @app.route('/quote/{symbol}')
# def quote(symbol):
#     t = Login()
#     response = t.get_quote(symbol).json()
#     return response

# @app.route('/option/chain/{symbol}')
# def option_chain(symbol):
#     t = Login()
#     response = t.get_option_chain(symbol).json()
#     return response

# @app.route('/option/order', methods=['POST'])
# def option_order():
#     t = Login()

#     webhook_message = app.current_request.json_body
#     if 'passphrase' not in webhook_message:
#         return {
#             'code': 'error',
#             'message': 'unauthorized, passphrase not present'
#         }
#     if webhook_message['passphrase'] != PASSPHRASE:
#         return {
#             'code': 'error',
#             'message': 'unauthorized, passphrase invalid'
#         }

#     symbol = OptionSymbol(
#         webhook_message['ticker'],
#         webhook_message['expiry'],
#         webhook_message['putCall'],
#         webhook_message['strike']
#     ).build()
#     order_spec = option_buy_to_open_limit(
#         symbol,
#         webhook_message['quantity'],
#         webhook_message['price']
#     ).build()

#     r = t.place_order(ACCOUNT_ID, order_spec)
#     order_id = utils.Utils(t, ACCOUNT_ID).extract_order_id(r)
#     assert order_id is not None

#     return {
#         'code': 'success',
#         'message': 'order placed, id={}'.format(order_id),
#     }
