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
    login(days=1)
    mode = 'normal'
    symbol_list=['GOOGL','TSM','INTC','AMD','NVDA']
    trader = OptionTrader(symbol_list=[], mode=mode)
    trader.run_cc(risk_level='medium', delta=0.25, MAX_ATTEMPT=3)


if __name__ == "__main__":
    main()
