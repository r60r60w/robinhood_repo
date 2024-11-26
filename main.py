#%%
from jh_options import *
from jh_utilities import *
from jh_optionTrader import *
import json
logger = get_logger(__name__)

with open('settings.json', 'r') as f:
    settings = json.load(f)

#%%
'''TODO:
 1. Incorporate volume and OI to option selection
 2. Reduce price carefully instead of hard code minus 1 cent
'''
def main():
    login(days=1)
    mode = settings['mode']
    symbol_list=settings['symbol_list']
    risk_level=settings['risk_level']
    delta = settings['delta']
    only_manage_existing = settings['only_manage_existing']
    trader = OptionTrader(symbol_list=symbol_list, mode=mode)
    trader.run_cc(risk_level=risk_level, delta=delta, MAX_ATTEMPT=3, only_manage_existing=only_manage_existing)


if __name__ == "__main__":
    main()
