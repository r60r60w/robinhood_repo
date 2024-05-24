import datetime as dt
import robin_stocks.robinhood as rh
import jh_stock_objects as jh_o

def find_options_by_delta(symbol, exp, type, delta_min, delta_max):
    """
    Find options for a given symbol within a specific delta range, expiration date, and type (call or put).

    :param symbol: The stock symbol ticker.
    :param exp: Expiration date of the options in 'YYYY-MM-DD' format.
    :param type: 'call' or 'put'.
    :param delta_min: Minimum delta value.
    :param delta_max: Maximum delta value.
    :return: A list of options in Option object that match the criteria.
    """
    
    # Get all options for the specified symbol and expiration date
    options_rh = rh.find_options_by_expiration(symbol, expirationDate=exp, optionType=type)
    
    matching_options = []
    
    for option_rh in options_rh:
        # Fetch the greeks for the option
        option_data_tmp = rh.get_option_market_data_by_id(option_rh['id'])
        option_data = option_data_tmp[0]
        
        # Extract the delta value
        delta = float(option_data['delta'])
        
        # Check if the delta is within the specified range
        if delta_min <= delta <= delta_max:
            option = jh_o.Option(symbol, option_rh['expiration_date'], float(option_rh['strike_price']), option_rh['type'])
            matching_options.append(option)
    
    return matching_options


#options = find_options_by_delta('AAPL', '2024-05-24', 'call', 0.2, 0.8)
#
#options_sorted = sorted(options, key=lambda x: x.get_delta())
#for option in options_sorted:
#    option.print()