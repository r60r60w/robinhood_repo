import config

import robin_stocks.robinhood as rh
import datetime as dt
import time
import option as op

def login(days):
    time_logged_in = 60*60*24*days
    rh.authentication.login(username=config.USERNAME,
                            password=config.PASSWORD,
                            expiresIn=time_logged_in,
                            scope='internal',
                            by_sms=True,
                            store_session=True)
    profile = rh.profiles.load_user_profile()
    print('-----Logged in to account belong to:', profile['first_name'], profile['last_name'], '-----')

def logout():
    rh.authentication.logout()

def get_stocks():
    stocks = list()
    stocks.append('NVDA')
    stocks.append('AAPL')
    return(stocks)


def close_short_option_by_id_ioc(option_id, price, quantity=1):
    option_info = rh.options.get_option_instrument_data_by_id(option_id)
    symbol = option_info['chain_symbol']
    exp_date = option_info['expiration_date']
    strike_price = float(option_info['strike_price'])
    type = option_info['type']
    order_info = rh.order_buy_option_limit('close', 'debit', price, symbol, quantity, exp_date, strike_price, type, timeInForce='gfd')
    print(order_info)

    # Cancel order after waiting for 5min 
    time.sleep(300)
    pending_orders = rh.orders.get_all_open_option_orders()
    for pending_order in pending_orders:
        if order_info['id'] == pending_order['id']:
            rh.orders.cancel_option_order(pending_order['id'])
            print("Order cancelled since it is not filled after 5 min.")
            order_info = None
    return order_info



def is_market_open():
    today_date = dt.datetime.today().date()
    if today_date.weekday() >=5 or is_us_market_holiday(today_date): # See if today is weekend or US holiday
        return False

    time_now = dt.datetime.now().time()
    market_open = dt.time(6,30,0) # 6:30AM PST
    market_close = dt.time(12,55,0) # 12:55PM PST

    return time_now > market_open and time_now < market_close

def is_call_covered(short_call, short_call_quantity):
    # Check if there is short call postion already
    optionPositions = op.OptionPosition()
    if optionPositions.is_short_call_in_position(short_call.symbol):
        return False
       
    #TODO: continue from here make the below code a method in optionPosition
    # Check if there is long call positions to cover the short call
    print('--See if there are long call positions to cover the short call...')
    if optionPositions.is_long_call_in_position(shortCallSymbol):
        return True
    for position in option_positions:
        option_info = rh.options.get_option_instrument_data_by_id(position['option_id'])
        position_symbol = option_info['chain_symbol']
        if short_call_symbol == position_symbol and position['type'] == 'long' and option_info['type'] == 'call':
            if short_call_quantity <= float(position['quantity']):
                return True

    # Check if there is enough underlying stocks to cover the short call
    print('--See if there are enough underlying stocks to cover the short call...')
    stock_positions = rh.account.get_open_stock_positions()
    for position in stock_positions:
        stock_info = rh.stocks.get_stock_quote_by_id(position['instrument_id'])
        position_symbol = stock_info['symbol']
        if short_call_symbol == position_symbol:
            position_shares = float(position['shares_available_for_exercise'])
            if short_call_quantity*100 <= position_shares:
                return True

    return False


def strat_open_short_call(symbol, quantity=1, risk_level='low', days_till_exp=4, chance_of_profit=0.9):
    print('---- Executing Covered Call Selling Strategy for', symbol, 'with', days_till_exp, 'Days till Expiration ----')
    print('Your selected risk level is:', risk_level)
    
    # Calculate expiration date
    exp = dt.datetime.now().date() + dt.timedelta(days=days_till_exp) 
    exp_str = exp.strftime('%Y-%m-%d')
    
    # Define profit floor and ceiling
    profit_floor = round(chance_of_profit - 0.025, 3)
    profit_ceiling = round(chance_of_profit + 0.050, 3)
    if profit_ceiling > 1:
        profit_ceiling = 0.98
    
    print('Looking for options with profitability between {0} and {1}, expiring'.format(profit_floor, profit_ceiling), exp_str)
    
    # Find potential options
    potentialOptions_rh = rh.options.find_options_by_specific_profitability(
        inputSymbols=symbol,
        expirationDate=exp_str,
        typeProfit='chance_of_profit_short',
        optionType='call',
        profitFloor=profit_floor,
        profitCeiling=profit_ceiling
    )
    
    if len(potentialOptions_rh) == 0:
        print('Found no options matching criteria.')
        return None
    
    # Print potential options
    print('Found these options matching criteria:')
    potentialOptions_rh = sorted(potentialOptions_rh, key=lambda x: x['strike_price'])
    potentialOptions = []
    for index, option_rh in enumerate(potentialOptions_rh):
        option = op.Option(option_rh['chain_symbol'], option_rh['expiration_date'], option_rh['strike_price'], option_rh['type'])
        potentialOptions.append(option)
        print('[{0}]'.format(index + 1), 
              'symbol:', option.symbol,
              'exp:', option.exp,
              'strike price:', option.strike,
              'ask price:', option.get_ask_price(),
              'bid price:', option.get_bid_price(),
              'delta:', option.get_delta(),
              'theta:', option.get_theta())
    
    # Select option based on risk level
    if risk_level == 'low':
        selectedOption = potentialOptions[-1]
    elif risk_level == 'medium':
        mid_index = len(potentialOptions) // 2
        selectedOption = potentialOptions[mid_index]
    elif risk_level == 'high':
        selectedOption = potentialOptions[0]
#    print(selected_option)
    print('Selected option [{0}] to place an order...'.format(potentialOptions.index(selectedOption)+1))

    # Check if the order already exists in currrent open orders
    existingOrders_rh = rh.orders.get_all_open_option_orders()
    for order in existingOrders_rh:
        legs = order['legs']
        leg = legs[0]
        existingOption_rh = rh.helper.request_get(leg['option'])
        if selectedOption.get_id() == existingOption_rh['id']:
            print('This order already exists in current open orders. Order not placed.')
            return

    # Check if there are enough securities to "cover" this call
    print('Checking if there are enough securities to "cover" this short call...')
    if is_call_covered(selectedOption, quantity) == False:
        print('There is not enough securities to cover this call. Order not placed.')
        return 

    # Calculate limit price
    limit_price = round((float(selected_option['ask_price']) + float(selected_option['bid_price'])) / 2, 2)
    print('Opening a limit order to sell at ${0}...'.format(limit_price))

    # Place sell order
    order_info = rh.order_sell_option_limit(
        positionEffect='open',
        creditOrDebit='credit',
        price=limit_price,
        symbol=selected_option['chain_symbol'],
        quantity=quantity,
        expirationDate=selected_option['expiration_date'],
        strike=selected_option['strike_price'],
        optionType=selected_option['type'],
        timeInForce='gfd'
    )
    
    print('Order placed with the following information:')
    print('--Symbol:', selected_option['chain_symbol'])
    print('--Exp date:', selected_option['expiration_date'])
    print('--Strike Price:', selected_option['strike_price'])
    print('--Premium to be collected if filled: ${0}'.format(limit_price*100))
    return order_info

def strat_close_short_call(short_option_id, quantity=1):
    status = None
    short_option_info = rh.options.get_option_instrument_data_by_id(short_option_id)
    short_option_market_info_tmp = rh.get_option_market_data_by_id(short_option_id)
    short_option_market_info = short_option_market_info_tmp[0]
    bid_price = float(short_option_market_info['bid_price'])
    ask_price = float(short_option_market_info['ask_price'])
    limit_price = round((bid_price + ask_price)/2, 2)
    print('---Closing short call with',
        'symbol:', short_option_info['chain_symbol'],
        'exp:', short_option_info['expiration_date'],
        'strike price:', short_option_info['strike_price'])

    # Check if the short call exists in open positions
    option_positions = rh.options.get_open_option_positions()
    is_short_option_open = False
    for position in option_positions:
        if short_option_id == position['option_id'] and position['type'] == 'short':
            is_short_option_open = True
            if quantity > float(position['quantity']):
                print('You are trying to close more number of options than you opened. Option not closed.')
                return status
            current_price_tmp = rh.options.get_option_market_data_by_id(position['option_id'], 'mark_price')
            current_price = -1*round(float(current_price_tmp[0]), 2)
            average_cost = float(position['average_price'])
            break

    if is_short_option_open == False:
        print('The short option to close is not open in your account. Option not closed.')
        return status

    # Check if the short call is in open orders
    existing_orders = rh.orders.get_all_open_option_orders()
    for order in existing_orders:
        legs = order['legs']
        leg = legs[0]
        existing_option = rh.helper.request_get(leg['option'])
        if short_option_id == existing_option['id']:
            print('This order is queuing in current open orders. Wait till it is filled.')
            return

    # Close option if return rate is higher than 0.7 with more than 3 days till expiration.
    return_rate = (current_price * 100 - average_cost)/abs(average_cost)       
    return_pcnt = round(return_rate * 100, 2)
    expiration_date = dt.datetime.strptime(short_option_info['expiration_date'], "%Y-%m-%d").date()

    days_till_exp = expiration_date - dt.datetime.now().date()
    print('Return percentage now is {0}%'.format(return_pcnt))
    if return_rate < 0:
        print('Pay attention to negative return percentage.')
        if days_till_exp.days <= 2:
            print('There is less than 2 days left till expiration. Watch for assignment risk!!!')
            #TODO: Start from here
            status = roll_option_ioc(short_option_id, "new_option_id", "short", quantity)
    elif return_rate > 0.7:
        if days_till_exp.days >= 3:
            print('Return rate is higher than 0.7 with at least 3 days till expiration.')
            print("Closing the short position prematurely to prevent risk.")
            status = close_short_option_by_id_ioc(short_option_id, limit_price, quantity)
    elif return_rate > 0.9:
        if days_till_exp.days <= 2:
            print('Return rate is higher than 0.9 with less than 2 days till expiration.')
            print("Closing the short position prematurely to prevent risk.")
            status = close_short_option_by_id_ioc(short_option_id, limit_price, quantity)

    return status
        

def run_covered_call(symbol_list, quantity=1, risk_level='low', chance_of_profit=0.9):
    # Opening covered call position
    # Determine if today is Monday
    short_call_order_info_list = []
    today_date = dt.datetime.today().date()
    exp_date = today_date + dt.timedelta(-1) # Should be -1 in mission mode
    if True:
#    if today_date.strftime("%A") == 'Monday' and is_market_open():
        if is_us_market_holiday(today_date):
            print("This week's Monday falls on a US holiday. Exiting CC.")
            return 
        days_till_exp = 4; # THis will select Friday as exp date.
        exp_date = today_date + dt.timedelta(days_till_exp)
        if is_us_market_holiday(exp_date):
            days_till_exp -= 1
            exp_date = today_date + dt.timedelta(days_till_exp)

        # Wait for 30 minutes after market opens to place order
        #time.sleep(1800)

        # Place short call order for each symbol in the symbol list
        # Attempt to place limit order based on mid bid-ask price.
        # If order not filled in x minutes, cancel the orders and place again for <trial_count> times.
        trial_count = 0
        while trial_count < 2:
            for symbol in symbol_list:
                short_call_order_info = strat_open_short_call(symbol, quantity, risk_level, days_till_exp, chance_of_profit)
                if short_call_order_info != None:
                    short_call_order_info_list.append(short_call_order_info) 
            time.sleep(3)
            pending_orders = rh.orders.get_all_open_option_orders()
            if len(pending_orders) == 0: break
            for short_call_order_info in short_call_order_info_list:
                for pending_order in pending_orders:
                    if short_call_order_info['id'] == pending_order['id']:
                        rh.orders.cancel_option_order(pending_order['id'])
            trial_count += 1
        

    # Find open short call positions and add it to option_id_list
    option_id_list = []

    # Closing cc based on strategy    
    while dt.datetime.today().date() <= exp_date: 
        # Add any newly open short calls to option_id_list
        open_option_positions = rh.options.get_open_option_positions()
        for position in open_option_positions:
            if position['type'] == 'short' and position['option_id'] not in option_id_list:
                option_id_list.append(position['option_id'])

#        if is_market_open() == True:
        if True:
            for option_id in option_id_list:
                strat_close_short_call(option_id, quantity)
        # Run closing strategy every 30 seconds.
        time.sleep(30)


def is_us_market_holiday(date):
    # List of recognized US market holidays
    us_market_holidays = [
        dt.datetime(date.year, 1, 1).date(),
        # Martin Luther King Jr. Day - Third Monday in January
        dt.datetime(date.year, 1, 15).date() if date.year == 2024 else None,  # Adjust for the current year
        # Presidents' Day - Third Monday in February
        dt.datetime(date.year, 2, 19).date() if date.year == 2024 else None,  # Adjust for the current year
        # Good Friday - Friday before Easter Sunday (not a federal holiday, but many stock exchanges close early)
        dt.datetime(date.year, 3, 29).date() if date.year == 2024 else None,  # Adjust for the current year
        # Memorial Day - Last Monday in May
        dt.datetime(date.year, 5, 27).date() if date.year == 2024 else None,  # Adjust for the current year
        # Independence Day - July 4th
        dt.datetime(date.year, 7, 4).date(),
        # Labor Day - First Monday in September
        dt.datetime(date.year, 9, 2).date() if date.year == 2024 else None,  # Adjust for the current year
        # Thanksgiving Day - Fourth Thursday in November
        dt.datetime(date.year, 11, 28).date() if date.year == 2024 else None,  # Adjust for the current year
        # Christmas Day - December 25th
        dt.datetime(date.year, 12, 25).date()
    ]
    return date in us_market_holidays

#TODO: Add ioc to function, and test this function
def roll_option_ioc(old_id, new_id, position_type, quantity=1):
    old_option_info = rh.options.get_option_instrument_data_by_id(old_id)
    new_option_info = rh.options.get_option_instrument_data_by_id(new_id)
    symbol = old_option_info['chain_symbol']

    if symbol != new_option_info['chain_symbol']:
        print("The two options are not of the same underlying.")
        return

    old_exp_date_str = old_option_info['expiration_date']
    new_exp_date_str = new_option_info['expiration_date']
    old_strike = float(old_option_info['strike_price'])
    new_strike = float(new_option_info['strike_price'])
    old_type = old_option_info['type']
    new_type = new_option_info['type']

    if old_type != new_type:
        print("The two options are not of the same type. Need to be the same type for rolling.")
        return

    old_option_market_info_temp = rh.get_option_market_data_by_id(old_id)
    old_option_market_info = old_option_market_info_temp[0]
    old_bid_price = float(old_option_market_info['bid_price'])
    old_ask_price = float(old_option_market_info['ask_price'])
    old_limit_price = round((old_bid_price + old_ask_price)/2, 2) 

    new_option_market_info_temp = rh.get_option_market_data_by_id(new_id)
    new_option_market_info = new_option_market_info_temp[0]
    new_bid_price = float(new_option_market_info['bid_price'])
    new_ask_price = float(new_option_market_info['ask_price'])
    new_limit_price = round((new_bid_price + new_ask_price)/2, 2) 

#    new_exp_date = dt.datetime.strptime(old_exp_date_str, "%Y-%m-%d")  + dt.timedelta(days=days_to_roll_out) 
#    new_exp_date_str = new_exp_date.strftime('%Y-%m-%d')

    if position_type == "long":
        price = new_limit_price - old_limit_price
        action1 = "sell"
        action2 = "buy"
    elif position_type == "short":
        price = old_limit_price - new_limit_price
        action1 = "buy"
        action2 = "sell"
    else:
        print("Invalid position type. Position type should be either long or short")
        return
    
    debitOrCredit = "debit" if price > 0 else "credit"

    leg1 = {"expirationDate": old_exp_date_str,
            "strike": old_strike,
            "optionType": type,
            "effect":"close",
            "action": action1}

    leg2 = {"expirationDate": new_exp_date_str,
            "strike": new_strike,
            "optionType": type,
            "effect":"open",
            "action": action2}
    
        
    spread = [leg1,leg2]
    order = rh.orders.order_option_spread(debitOrCredit, price, symbol, quantity, spread)
    print(order)

def main():
    # Test roll option_ioc in closing short call strat and add ioc.
    login(days=1)
    option_position = op.OptionPosition()
    option_position.print_all_positions()
#    
#    option_market_info_temp = rh.get_option_market_data_by_id(option_id)
#    option_market_info = option_market_info_temp[0]
#    bid_price = float(option_market_info['bid_price'])
#    ask_price = float(option_market_info['ask_price'])
#    limit_price = round((bid_price + ask_price)/2-0.2, 2) 
#    print(limit_price)
    roll_option_ioc(option_id, "new_id", "long")
    leg1 = {"expirationDate":"2024-09-20",
            "strike":"150.00",
            "optionType":"call",
            "effect":"close",
            "action":"sell"}

    leg2 = {"expirationDate":"2024-09-20",
            "strike":"160.00",
            "optionType":"call",
            "effect":"open",
            "action":"buy"}

    spread = [leg1,leg2]
    #!!!

 #   order_info = close_short_option_by_id(option_id, limit_price, 1)
#    order_id = order_info['id']
 
    cc_symbol_list = ['MSFT']
    run_covered_call(cc_symbol_list, quantity=1, risk_level='low', chance_of_profit=0.9)
#    order_info = strat_open_short_call('AAPL', risk_level='low', days_till_exp=4, quantity=1)
#    if order_info == None:
#        print('No open short call order.')
#        return
#    order_id = order_info['id']
#    legs = order_info['legs']
#    leg = legs[0]
#    option_info = rh.helper.request_get(leg['option'])
#    option_id = option_info['id']
#    option_id = 'bcca7856-aa17-4eee-a3df-45623142624a'
#    strat_close_short_call(option_id, quantity=1)




#    while open_market():
#    while True:
#        prices = rh.stocks.get_latest_price(stocks)
#        print(dt.datetime.now())
#        for i, stock in enumerate(stocks):
#            price = float(prices[i])
#            print('{}=${}'.format(stock,price))
#
#            data = ts.get_historical_prices(stock, span='day')
#        time.sleep(10)



if __name__ == "__main__":
    main()
