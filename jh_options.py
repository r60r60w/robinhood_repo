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
    
    def get_limit_price(self, price_ratio=0.5):
        self.update()
        return round(self._bid_price + price_ratio * (self._ask_price - self._bid_price), 2)

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

    def roll_option_ioc(self, new_option, position_type, quantity=1, mode='normal'):
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

        old_limit_price = old_option.get_limit_price()
        new_limit_price = new_option.get_limit_price()

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
        order_rh = rh.orders.order_option_spread(debitOrCredit, abs(price), new_option.symbol, quantity, spread)
        print(order_rh)
        if len(order_rh) != 35:
             print_with_time('Failed to place order.')
             return order_rh
        
        # Cancel order after waiting for 2 min 
        time.sleep(120) if mode != 'test' else time.sleep(0)
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
            if position['type'] == 'short':
                option.quantity = -1*quantity
            elif position['type'] == 'long':
                option.quantity = quantity
            option.cost = self.calculate_option_cost(option)
            self.optionPositions.append(option)

    def get_all_positions(self):
        return self.optionPositions
    
    def print_all_positions(self):
        # Print header
        print('---- Current Option Positions ----')

        # Iterate over each option position
        for position in self.optionPositions:
            # Retrieve current market price
            current_price = position.get_mark_price() * position.get_position_type()
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
        for position in self.optionPositions:
            if position.get_id() == option.get_id():
                return position
        
        return None

    # Check if there are short call option of the given symbol in current postions
    def is_short_call_in_position(self, symbol):
        for position in self.optionPositions:
            type = position.type
            positionType = position.get_position_type_str()
            if  position.symbol == symbol and type == 'call' and positionType == 'short':
                return True
        
        return False

    # Check if there are long call option of the given symbol in current postions
    def is_long_call_in_position(self, symbol):
        for position in self.optionPositions:
            type = position.type
            positionType = position.get_position_type_str()
            if  position.symbol == symbol and type == 'call' and positionType == 'long':
                return True
        
        return False
   
    # Count how many long call positions of given symbol 
    def long_call_quantity(self, symbol):
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

def close_short_option_ioc(option_to_close, price, quantity=1, mode='normal'):
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
    time.sleep(120) if mode !='test' else time.sleep(0)
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
    optionPositions.update()
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

