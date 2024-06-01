import datetime as dt
import logging
import time
import robin_stocks.robinhood as rh
from jh_utilities import *
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class Option():
    def __init__(self, symbol, exp, strike, type):
        self.symbol = symbol 
        self.exp = exp
        self.strike = strike
        self.type = type
        self.quantity = 0
        self.cost = 0
        self._bid_price = 0
        self._ask_price = 0
        self._markprice = 0
        self._delta = None
        self._theta = None
        self.id = None # To be updated by the below method
        self.update()

    def get_option_rh(self): 
        options_rh = rh.options.find_options_by_expiration_and_strike(self.symbol, self.exp, self.strike, self.type)
        if not options_rh:
            raise EmptyListError()

        return options_rh

    def update(self):
        try:
            options_rh = self.get_option_rh()
            
        except EmptyListError as e:
            logging.error(f"No option found: {e}")
            return
        else:
            option_rh = options_rh[0]

        self._ask_price = round(float(option_rh['ask_price']), 2)
        self._bid_price = round(float(option_rh['bid_price']), 2)
        self._mark_price = round(float(option_rh['mark_price']), 2)
        self._delta = round(float(option_rh['delta']), 4)
        self._theta = round(float(option_rh['theta']), 4)
        self.id = option_rh['id']

    def print(self):
        self.update()
        print('symbol:', self.symbol,
              ' type:', self.type,
              ' exp:', self.exp,
              ' strike price:', self.strike,
              ' quantity:', self.quantity,
              ' current price:', self.get_mark_price(),
              ' delta:', self.get_delta(),
              ' theta:', self.get_theta())
       
    
    def get_position_type(self):
        """Return the position type in 1 or -1, where 1 is for long and -1 for short

        Returns:
            integer: 1 or -1
        """
        if self.quantity > 0:
            return 1
        elif self.quantity < 0:
            return -1
        else:
            return 0

    def get_position_type_str(self):
        if self.quantity > 0:
            return 'long'
        elif self.quantity < 0:
            return 'short'
        else:
            return ''


    def get_exp_dt(self):
        return dt.datetime.strptime(self.exp, "%Y-%m-%d") 

    # Robin-stock specific methods
    def get_id(self):
        return self.id

    def get_ask_price(self):
        self.update()
        return self._ask_price

    def get_bid_price(self):
        self.update()
        return self._bid_price

    def get_mark_price(self):
        self.update()
        return self._mark_price

    def get_delta(self):
        self.update()
        return self._delta

    def get_theta(self):
        self.update()
        return self._theta

    def find_option_to_roll(self, dte_delta, price_ratio):
        """ Given the underlying option, find an option to roll to with given constraints.
            Returns the option with at least dte_delta more days till expiration and with
            price nearest to price_ratio times old price. 

        Args:
            dte_delta (int): exp of new minus exp of old
            price_ratio (float): market price of new divided by market price of old
        """
        new_exp_dt = self.get_exp_dt() + dt.timedelta(days=dte_delta)
        new_exp = new_exp_dt.strftime('%Y-%m-%d') 
        new_price = self.get_mark_price() * price_ratio
        
        while True:
            options_rh = rh.options.find_options_by_expiration(self.symbol, new_exp, self.type)
            if len(options_rh) != 0:
                break
            dte_delta += 1
            new_exp_dt = self.get_exp_dt() + dt.timedelta(days=dte_delta)
            new_exp = new_exp_dt.strftime('%Y-%m-%d') 
        

        # Find the option with the closest market price to the new_price 
        new_option_rh = min(options_rh, key=lambda x: abs(float(x['mark_price']) - new_price))
        return Option(self.symbol, new_exp, float(new_option_rh['strike_price']), self.type)

    def roll_option_ioc(self, new_option, position_type, quantity=1):
        # Check if this option (self) is in position
        optionPositions = OptionPosition()
        old_option = optionPositions.find_and_update_option(self)
        if old_option == None:
            print_with_time('Option to roll is not in position.')
            return None

        # Check if the underlying stock is the same
        if old_option.symbol != new_option.symbol:
            print("The two options are not of the same underlying.")
            return None

        # Check if the option type is the same
        if old_option.type != new_option.type:
            print("The two options are not of the same type. Need to be the same type for rolling.")
            return None

        old_bid_price = old_option.get_bid_price()
        old_ask_price = old_option.get_ask_price()
        old_limit_price = round((old_bid_price + old_ask_price)/2, 2) 

        new_bid_price = new_option.get_bid_price()
        new_ask_price = new_option.get_ask_price()
        new_limit_price = round((new_bid_price + new_ask_price)/2, 2) 


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

        leg1 = {"expirationDate": old_option.exp,
                "strike": old_option.strike,
                "optionType": old_option.type,
                "effect":"close",
                "action": action1}

        leg2 = {"expirationDate": new_option.exp,
                "strike": new_option.strike,
                "optionType": new_option.type,
                "effect":"open",
                "action": action2}


        spread = [leg1,leg2]
        order_rh = rh.orders.order_option_spread(debitOrCredit, price, new_option.symbol, quantity, spread)
        print(order_rh)
        if len(order_rh) != 35:
             print_with_time('Failed to place order.')
             return order_rh
        
        # Cancel order after waiting for 2 min 
        time.sleep(120)
        pendingOrders = rh.orders.get_all_open_option_orders()
        for pendingOrder in pendingOrders:
            if order_rh['id'] == pendingOrder['id']:
                rh.orders.cancel_option_order(pendingOrder['id'])
                print_with_time("Order cancelled since it is not filled after 2 min.")
                order_rh = None
        return order_rh


class OptionPosition():
    def __init__(self):
        self.optionPositions = []
        self.update()
        
    def update(self):
        self.optionPositions = []
        optionPositions_rh = rh.options.get_open_option_positions()
        for position in optionPositions_rh:
            option_rh = rh.options.get_option_instrument_data_by_id(position['option_id'])
            option = Option(option_rh['chain_symbol'], option_rh['expiration_date'], float(option_rh['strike_price']), option_rh['type'])
            quantity = float(position['quantity'])
            option.cost = self.calculate_option_cost(option)
            if position['type'] == 'short':
                option.quantity = -1*quantity
            elif position['type'] == 'long':
                option.quantity = quantity
            self.optionPositions.append(option)

    def get_all_positions(self):
        self.update()
        return self.optionPositions
    
    def print_all_positions(self):
        self.update()
        # Print header
        print('---- Current Option Positions ----')

        # Iterate over each option position
        for position in self.optionPositions:
            # Retrieve current market price
            current_price = position.get_mark_price()
            current_price = current_price * position.get_position_type()
            # Calculate total return
            cost = position.cost 
            total_return = current_price * 100 - cost

            # Print option position details
            print('symbol:', position.symbol,
                  ' type:', position.get_position_type_str(), position.type,
                  ' exp:', position.exp,
                  ' strike price:', position.strike,
                  ' quantity:', position.quantity,
                  ' current price:', round(current_price, 2),
                  ' current value:', round(current_price * 100, 2),
                  ' delta:', position.get_delta(),
                  ' theta:', position.get_theta(),
                  ' average cost:', round(cost, 2),
                  ' total return:', round(total_return, 2))

    def calculate_option_cost(self, option, verbose=False):  
        self.update()
        option = self.find_and_update_option(option)
        if option is None:
            print_with_time('The option is not in current open positions.')
            return None
        
        symbol = option.symbol
        exp = option.exp
        strike = option.strike
        type = option.type
        side = 'sell' if option.get_position_type() == -1 else 'buy'
        cost = 0

        all_orders_rh = rh.orders.get_all_option_orders()
        filtered_orders_rh = [item for item in all_orders_rh if item['chain_symbol'] == symbol and item['state']== 'filled']
        tail = False
        for index, order in enumerate(filtered_orders_rh):
            if order['form_source'] == 'strategy_roll':
                legs = order['legs']
                for i, leg in enumerate(legs):
                    conditions = [
                        leg['position_effect'] == 'open', 
                        leg['expiration_date'] == exp,
                        float(leg['strike_price']) == strike,
                        leg['option_type'] == type,
                        leg['side']== side
                    ]
                    if all(conditions):
                        premium = float(order['average_net_premium_paid'])
                        cost = cost + premium
                        exp = legs[1-i]['expiration_date']
                        strike = float(legs[1-i]['strike_price'])
                        if verbose:
                            print('---option rolling info---')
                            print('Row # {0}'.format(index))
                            print('Rolled on:', order['updated_at'])
                            print('Rolled from:')
                            print('Expiration date:', exp)
                            print('Strike price: {0}'.format(strike))
                            print('Premium paid: {0}'.format(premium))
                            print('Running cost: {0}'.format(cost))
                        break
            else:
                legs = order['legs']
                for leg in legs: 
                    conditions = [
                        leg['position_effect'] == 'open', 
                        leg['expiration_date'] == exp,
                        float(leg['strike_price']) == strike,
                        leg['option_type'] == type,
                        leg['side']== side
                    ]
                    if all(conditions):
                        premium = float(order['average_net_premium_paid'])
                        cost = cost + premium
                        if verbose:
                            print('---Original Option Info---')
                            print('Row # {0}'.format(index))
                            print('Opened on:', order['updated_at'])
                            print('Expiration date:', exp)
                            print('Strike price: {0}'.format(strike))
                            print('Premium paid: {0}'.format(premium))
                            print('Running cost: {0}'.format(cost))
                        tail = True
                        break
                if tail:
                    break
            
        return cost                


    def find_and_update_option(self, option):
        """Find and update an option with position-related data such as cost and quantity. 

        Args:
            option (_type_): Option object type

        Returns:
            _type_: returns None if no option found in position.
                    returns an Option object with cost and quantity updated accroding to position.
        """
        self.update()
        for position in self.optionPositions:
            if position.get_id() == option.get_id():
                return position
        
        return None

    # Check if there are short call option of the given symbol in current postions
    def is_short_call_in_position(self, symbol):
        self.update()
        for position in self.optionPositions:
            type = position.type
            positionType = position.get_position_type_str()
            if  position.symbol == symbol and type == 'call' and positionType == 'short':
                return True
        
        return False

    # Check if there are long call option of the given symbol in current postions
    def is_long_call_in_position(self, symbol):
        self.update()
        for position in self.optionPositions:
            type = position.type
            positionType = position.get_position_type_str()
            if  position.symbol == symbol and type == 'call' and positionType == 'long':
                return True
        
        return False
   
    # Count how many long call positions of given symbol 
    def long_call_quantity(self, symbol):
        self.update()
        count = 0
        for position in self.optionPositions:
            type = position.type
            positionType = position.get_position_type_str()
            if  position.symbol == symbol and type == 'call' and positionType == 'long':
                count += abs(position.quantity)
        
        return count



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

    if not options_rh:
        raise EmptyListError()
    
    matchingOptions = []
    
    for option_rh in options_rh:
        # Fetch the greeks for the option
        optionData_tmp = rh.get_option_market_data_by_id(option_rh['id'])
        optionData = optionData_tmp[0]
        
        # Extract the delta value
        delta = float(optionData['delta'])
        
        # Check if the delta is within the specified range
        if delta_min <= delta <= delta_max:
            option = Option(symbol, option_rh['expiration_date'], float(option_rh['strike_price']), option_rh['type'])
            matchingOptions.append(option)
    
    matchingOptions_sorted = sorted(matchingOptions, key=lambda x: x.get_delta())
    
    return matchingOptions_sorted

def is_option_in_open_orders(option):
    existingOrders_rh = rh.orders.get_all_open_option_orders()
    for order in existingOrders_rh:
        legs = order['legs']
        for leg in legs:
            existingOption_rh = rh.helper.request_get(leg['option'])
            if option.get_id() == existingOption_rh['id']:
                return True 
    return False
#options = find_options_by_delta('AAPL', '2024-05-24', 'call', 0.2, 0.8)
#
#options_sorted = sorted(options, key=lambda x: x.get_delta())
#for option in options_sorted:
#    option.print()

def close_short_option_ioc(option_to_close, price, quantity=1):
    symbol = option_to_close.symbol
    exp_date = option_to_close.exp
    strike_price = option_to_close.strike 
    type = option_to_close.type
    order_rh = rh.order_buy_option_limit('close', 'debit', price, symbol, quantity, exp_date, strike_price, type, timeInForce='gfd')
    print(order_rh)
    if len(order_rh) != 35:
        print_with_time('Failed to place order.')
        return order_rh

    # Cancel order after waiting for 2 min 
    time.sleep(120)
    pendingOrders = rh.orders.get_all_open_option_orders()
    for pendingOrder in pendingOrders:
        if order_rh['id'] == pendingOrder['id']:
            rh.orders.cancel_option_order(pendingOrder['id'])
            print_with_time("Order cancelled since it is not filled after 2 min.")
            order_rh = None
    return order_rh

def is_call_covered(short_call, short_call_quantity):
    # Check if there is short call position already
    print('--See if there are short call positions already...')
    optionPositions = OptionPosition()
    if optionPositions.is_short_call_in_position(short_call.symbol):
        return False
       
    # Check if there is long call positions to cover the short call
    print('--See if there are long call positions to cover the short call...')
    if short_call_quantity <= optionPositions.long_call_quantity(short_call.symbol):
        return True

    #TODO: Make the below code a method in optionPosition
    # Check if there is enough underlying stocks to cover the short call
    print('--See if there are enough underlying stocks to cover the short call...')
    stock_positions = rh.account.get_open_stock_positions()
    for position in stock_positions:
        stock_info = rh.stocks.get_stock_quote_by_id(position['instrument_id'])
        position_symbol = stock_info['symbol']
        if short_call.symbol == position_symbol:
            position_shares = float(position['shares_available_for_exercise'])
            if short_call_quantity*100 <= position_shares:
                return True

    return False

class OptionTrader():
    def __init__(self, symbol_list, mode) -> None:
        self.positions = OptionPosition()
        self.symbol_list = symbol_list
        self.mode = mode

    def print_all_positions(self):
        self.positions.print_all_positions()
    
    def print_all_orders(self):
        orders_rh = rh.orders.get_all_open_option_orders()
        print(orders_rh)
        
    def run_cc(self, risk_level='low', delta=0.2):
        # Opening covered call position
        # Determine if today is Monday
        print_with_time('-----Running covered call strategy:-----')
        print('--You selected mode is', self.mode)
        print('--Placing covered call order every Monday with exp set to the 2nd next Friday.')

        shortCallOrder_rh_list = []
        todayDate_dt = dt.datetime.today().date()
        exp_dt = get_2nd_next_friday()
        if todayDate_dt.strftime("%A") == 'Monday' and is_market_open() or self.mode == 'test':
            if is_us_market_holiday(todayDate_dt):
                print("This week's Monday falls on a US holiday. Exiting CC.")
                return 
            if is_us_market_holiday(exp_dt):
                # If expiration date is a holiday, push to next week's Friday
                exp_dt = todayDate_dt + dt.timedelta(weeks=1)

            dte = exp_dt - todayDate_dt
            # Wait for 30 minutes after market opens to place order
            if self.mode != 'test':
                time.sleep(1800)

            # Place short call order for each symbol in the symbol list
            # Attempt to place limit order based on mid bid-ask price.
            # If order not filled in x minutes, cancel the orders and place again for <trial_count> times.
            MAX_ATTEMPT = 3
            attempt = 0
            print_with_time('Placing short call orders in {0} attempts'.format(MAX_ATTEMPT))
            while attempt < MAX_ATTEMPT:
                print_with_time('Attempt # {0}'.format(attempt+1))
                for symbol in self.symbol_list:
                    shortCallOrder_rh = self.open_short_call(symbol, dte, risk_level, delta, quantity=1)
                    if shortCallOrder_rh != None:
                        shortCallOrder_rh_list.append(shortCallOrder_rh) 
                time.sleep(3)
                pendingOrders = rh.orders.get_all_open_option_orders()
                if len(pendingOrders) == 0: break
                for shortCallOrder_rh in shortCallOrder_rh_list:
                    for pendingOrder in pendingOrders:
                        if shortCallOrder_rh['id'] == pendingOrder['id']:
                            rh.orders.cancel_option_order(pendingOrder['id'])
                attempt += 1

        # Closing cc based on strategy    
        # Filter open short call positions in current open option positions 
        shortCalls = []
        while dt.datetime.today().date() <= exp_dt: 
            # Add any newly open short calls to option_id_list
            positions = OptionPosition()
            for position in positions.optionPositions:
                if position.type == 'short' and position not in shortCalls:
                    shortCalls.append(position)

            if is_market_open() == True and self.mode != 'test':
                for option in shortCalls:
                    self.close_short_call(option, quantity=1)
            # Run closing strategy every 30 seconds.
            if self.mode != 'test':
                time.sleep(30)
            else:
                time.sleep(3)

    def open_short_call(self, symbol, dte, risk_level="low", delta=0.2, quantity=1):
        print_with_time('---- Openning short call for', symbol, 'with', dte, 'Days till Expiration ----')

        # Calculate expiration date
        exp_dt = dt.datetime.now().date() + dt.timedelta(days=dte) 
        exp = exp_dt.strftime('%Y-%m-%d')

        # Define profit floor and ceiling
        delta_min = 0.025
        delta_max = delta if delta > delta_min else delta_min+0.005
        print_with_time('Looking for options with delta between {0} and {1}, expiring'.format(delta_min, delta_max), exp)

        # Find potential options
        try: 
            potentialOptions = find_options_by_delta(symbol, exp, 'call', delta_min, delta_max)
        except EmptyListError as e:
            logging.error(f"No option found matching the given delta range: {e}")
            return None

        # Print potential options
        print_with_time('Found these options matching criteria:')
        for index, option in enumerate(potentialOptions):
            print('[{0}]'.format(index+1), end='')
            option.print()

        # Select option based on risk level
        if risk_level == 'low':
            selectedOption = potentialOptions[0]
        elif risk_level == 'medium':
            mid_index = len(potentialOptions) // 2
            selectedOption = potentialOptions[mid_index]
        elif risk_level == 'high':
            selectedOption = potentialOptions[-1]

        print_with_time('Selected option [{0}].'.format(potentialOptions.index(selectedOption)+1))

        # Check if the order already exists in currrent open orders
        print_with_time('Checking if this option is already in open orders')
        if is_option_in_open_orders(selectedOption):
            print_with_time('This order already exists in current open orders. Order not placed.')
            return None

        # Check if there are enough securities to "cover" this call
        print_with_time('Checking if there are enough securities to "cover" this short call...')
        if is_call_covered(selectedOption, quantity) == False:
            print_with_time('There is not enough securities to cover this call. Order not placed.')
            return None

        # Calculate limit price
        limit_price = round((selectedOption.get_bid_price() + selectedOption.get_ask_price())/2, 2)
        print_with_time('Opening a limit order to sell at ${0}...'.format(limit_price))

        #TODO: Contunue from here, think about how to wrap sell_option
        # Place sell order
        order_rh = rh.order_sell_option_limit(
            positionEffect='open',
            creditOrDebit='credit',
            price=limit_price,
            symbol=selectedOption.symbol,
            quantity=quantity,
            expirationDate=selectedOption.exp,
            strike=selectedOption.strike,
            optionType=selectedOption.type,
            timeInForce='gfd'
        )

        print_with_time('Order placed with the following information:')
        print('--Symbol:', selectedOption.symbol)
        print('--Exp date:', selectedOption.exp)
        print('--Strike Price:', selectedOption.strike)
        print('--Premium to be collected if filled: ${0}'.format(round(limit_price*100, 2)))
        print('--Premium to be collected if filled (should match above): $', order_rh['premium'])
        return order_rh

    def close_short_call(self, option_to_close, quantity=1):
        status = None
        bid_price = option_to_close.get_bid_price()
        ask_price = option_to_close.get_ask_price()
        limit_price = round((bid_price + ask_price)/2, 2)
        print_with_time('---Closing short call with',
            'symbol:', option_to_close.symbol,
            'exp:', option_to_close.exp,
            'strike price:', option_to_close.exp)

        # Check if the short call exists in open positions
        optionPositions = OptionPosition()
        option_to_close = optionPositions.find_and_update_option(option_to_close)
        if option_to_close == None:
            print_with_time('The short option to close is not open in your account. Option not closed.')
            return status
        
        # Check if closing more positions than owned
        if quantity > abs(option_to_close.quantity):
            print_with_time('You are trying to close more number of options than you opened. Option not closed.')
            return status
            
        # Check if the short cal is in open orders
        if is_option_in_open_orders(option_to_close):
            print_with_time('This order is queuing in current open orders. Wait till it is filled.')
            return status
        
        cost = option_to_close.cost
        price = option_to_close.get_mark_price()
        total_return = price * 100 - cost
        return_rate = total_return/abs(cost)       
        return_pcnt = round(return_rate * 100, 2)
        dte = (option_to_close.get_exp_dt().date() - dt.datetime.now().date()).days
        print_with_time('Return percentage now is {0}%'.format(return_pcnt))

        # Closing logic
        if return_rate < 0:
            print('Pay attention to negative return percentage.')
            if dte < 2 and return_rate < -0.025:
                print_with_time('There is less than 2 days left till expiration. ')
                option_to_roll = option_to_close.find_option_to_roll(dte_delta=7, price_ratio=1.1)
                status = option_to_close.roll_option_ioc(option_to_roll, 'short', quantity)
        elif return_rate > 0.7:
            if dte >= 3:
                print('Return rate is higher than 0.7 with at least 3 days till expiration.')
                print("Closing the short position prematurely to prevent risk.")
                status = close_short_option_ioc(option_to_close, limit_price, quantity)
        elif return_rate > 0.9:
            if dte <= 2:
                print('Return rate is higher than 0.9 with less than 2 days till expiration.')
                print("Closing the short position prematurely to prevent risk.")
                status = close_short_option_ioc(option_to_close, limit_price, quantity)
        return status
    


    
        
        