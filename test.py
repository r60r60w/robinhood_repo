
import robin_stocks.robinhood as rh
import robin_stocks as rs
import datetime as dt
import time
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

import config
import yfinance as yf

class option():
    def __init__(self):
        self.symbol = 'XYZ'
        self.exp = '1900-12-31'
        self.strike = 0
        self.type = 'call'
        self.limitPrice = 0

yf.Ticker.options

def login(days):
    time_logged_in = 60*60*24*days
    rh.authentication.login(username=config.USERNAME,
                            password=config.PASSWORD,
                            expiresIn=time_logged_in,
                            scope='internal',
                            by_sms=True,
                            store_session=True)
    user_profile = rh.profiles.load_user_profile()
    account_profile = rh.profiles.load_account_profile()
    print('-----Logged in to account belong to:', user_profile['first_name'], user_profile['last_name'], '-----')
  #  print(account_profile)
login(1)

symbol = 'AAPL'
symbol_name = rh.get_name_by_symbol(symbol)
expirationDate = '2024-09-20' # format is YYYY-MM-DD.
strike = 150
optionType = 'call' # available options are 'call' or 'put' or None.
interval = 'hour' # available options are '5minute', '10minute', 'hour', 'day', and 'week'.
span = 'week' # available options are 'day', 'week', 'year', and '5year'.
bounds = 'regular' # available options are 'regular', 'trading', and 'extended'.
info = None
#!!!

historicalData = rh.get_option_historicals(symbol, expirationDate, strike, optionType, interval, span, bounds, info)

dates = []
closingPrices = []
openPrices = []

for data_point in historicalData:
    dates.append(data_point['begins_at'])
    closingPrices.append(data_point['close_price'])
    openPrices.append(data_point['open_price'])

# change the dates into a format that matplotlib can recognize.
x = [dt.datetime.strptime(d,'%Y-%m-%dT%H:%M:%SZ') for d in dates]

# plot the data.
plt.plot(x, closingPrices, 'ro')
plt.plot(x, openPrices, 'bo')
plt.title("Option price for {} over time".format(symbol_name))
plt.xlabel("Dates")
plt.ylabel("Price")
plt.show()