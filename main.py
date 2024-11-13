#%%
import datetime as dt
import time
import robin_stocks.robinhood as rh
from jh_options import *
from jh_utilities import *
from jh_optionTrader import *
logger = get_logger(__name__)

#%%
symbol = 'GOOGL'

#%%
'''TODO:
 1. How to let run_cc run in a loop
 2. run_cc closing logic problematic. 
'''
def main():
    login(days=1)
    mode = 'normal'
    trader = OptionTrader(['NVDA', 'TSLA', 'TSM'], mode)
    trader.run_cc('medium', MAX_ATTEMPT=3)

 



if __name__ == "__main__":
    main()

#%%
print('hello world')
print('hello2')
# %%
