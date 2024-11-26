#%%
from jh_options import *
from jh_utilities import *
from jh_optionTrader import *

logger = get_logger(__name__)


#%%
'''TODO:
 1. Incorporate volume and OI to option selection
 2. Reduce price carefully instead of hard code minus 1 cent
'''
def main():
    login(days=3)
    trader = OptionTrader(symbol_list=settings['symbol_list'], mode=settings['mode'])
    trader.run_cc(risk_level=settings['risk_level'],
                  delta=settings['delta'], 
                  MAX_ATTEMPT=3, 
                  only_manage_existing=settings['only_manage_existing']
                  )


if __name__ == "__main__":
    main()
