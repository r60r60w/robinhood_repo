import datetime as dt
import time
import logging
import robin_stocks.robinhood as rh
from jh_options import *
from jh_utilities import *
from jh_optionTrader import *


'''TODO:
1. Reduce unnecessary updates
2. close_short_call(): closing logic changed to option moneyness.
'''
def main():
    # Test roll option_ioc in closing short call strat and add ioc.
    login(days=1)
    mode = 'test'
    trader = OptionTrader(['AAPL', 'MSFT'], mode)
#    optionPositions = OptionPosition()
#    optionPositions.print_all_positions()
#    trader.print_all_positions()
    trader.run_cc('low', MAX_ATTEMPT=0)
#    option_position = op.OptionPosition()
#    option_position.print_all_positions()
#    
#    option_market_info_temp = rh.get_option_market_data_by_id(option_id)
#    option_market_info = option_market_info_temp[0]
#    bid_price = float(option_market_info['bid_price'])
#    ask_price = float(option_market_info['ask_price'])
#    limit_price = round((bid_price + ask_price)/2-0.2, 2) 
#    print(limit_price)

 #   order_info = close_short_option_by_id(option_id, limit_price, 1)
#    order_id = order_info['id']
 



if __name__ == "__main__":
    main()
