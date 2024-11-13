import datetime as dt
import time
import robin_stocks.robinhood as rh
import pandas as pd
import math
from jh_utilities import *
logger = get_logger(__name__)


class Option():
    def __init__(self, symbol, exp, strike, type):
        self.symbol = symbol 
        self.exp = exp
        self.strike = strike
        self.type = type
        self.quantity = 0
        self.cost = 0
        self.cum_cost = 0 # Cumulative cost considering option rolls.
        self._bid_price = 0
        self._ask_price = 0
        self._mark_price = 0
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
        logger.debug("updating option...")
        try:
            options_rh = self.get_option_rh()
            
        except EmptyListError as e:
            logger.error(f"No option found: {e}")
            return
        else:
            option_rh = options_rh[0]

        self._ask_price = round(float(option_rh['ask_price']), 2)
        self._bid_price = round(float(option_rh['bid_price']), 2)
        self._mark_price = round(float(option_rh['adjusted_mark_price']), 2)
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

    def get_ask_price(self, update=False):
        if update:
            self.update()
        return self._ask_price

    def get_bid_price(self, update=False):
        if update:
            self.update()
        return self._bid_price
    
    def get_limit_price(self, price_ratio=0.5, update=False):
        if update:
            self.update()
        return round(self._bid_price + price_ratio * (self._ask_price - self._bid_price), 2)

    def get_mark_price(self, update=False):
        if update:
            self.update()
        return self._mark_price

    def get_delta(self, update=False):
        if update:
            self.update()
        return self._delta

    def get_theta(self, update=False):
        if update:
            self.update()
        return self._theta

    def find_option_to_roll_by_delta(self, dte_delta, risk_level, delta):
        """ Given the underlying option, find an option to roll to with given constraints.
            Returns the option with at least dte_delta more days till expiration and with the given delta and risk level.

        Args:
            dte_delta (int): exp of new minus exp of old
            risk_level (str): low, medium, or high.
            delta (float): delta of the new option
        """
#        logger.info(f'[{self.symbol}] Looking for options to roll out by {dte_delta} days and delta < {delta} with risk level = {risk_level}...')
        new_exp_dt = self.get_exp_dt() + dt.timedelta(days=dte_delta)
        new_exp = new_exp_dt.strftime('%Y-%m-%d') 
        
        delta_min = 0.05
        delta_max = delta if delta > delta_min + 0.05 else delta_min+0.05
        logger.info(f'[{self.symbol}] Looking for calls to roll with delta between {delta_min} and {delta_max}, expiring on {new_exp}')

        # Loop until potentialOptions is non-empty
        matchingOptions = []
        while not matchingOptions:
            try:
                matchingOptions = find_options_by_delta(self.symbol, new_exp, self.type, delta_min, delta_max)
            except EmptyListError as e: # If no options found, increment days and reformat new expiration date
                logger.info(f'[{self.symbol}] No option found on {new_exp}.')
                logger.info(f'[{self.symbol}] Push out exp by 1 day.')
                dte_delta += 1
                new_exp_dt = self.get_exp_dt() + dt.timedelta(days=dte_delta)
                new_exp = new_exp_dt.strftime('%Y-%m-%d')
        
        if len(matchingOptions) == 0:
            logger.info(f'[{self.symbol}] No mathcing option found for rolling matching the delta range.')
            return None        
        
        # Print potential options
        matchingOptions_df = create_dataframe_from_option_list(matchingOptions)
        
        # Add a column to show potential credit earned if rolled.
        for index, row in matchingOptions_df.iterrows():
            matchingOptions_df.at[index, 'credit estimate'] = 100*(row['current price'] - self.get_mark_price())
            
        logger.info(f'[{self.symbol}] Found these options candidates to roll to:')
        print(matchingOptions_df)

        # Select option based on risk level
        if risk_level == 'low':
            selectedOption = matchingOptions[0]
        elif risk_level == 'medium':
            mid_index = len(matchingOptions) // 2
            selectedOption = matchingOptions[mid_index]
        elif risk_level == 'high':
            selectedOption = matchingOptions[-1]
        logger.info(f'Selected option [{matchingOptions.index(selectedOption)}] to roll to.')
        return selectedOption


    def find_option_to_rollup_with_credit(self, dte_delta, risk_level):
        """ Given the underlying option, find an option to roll UP to with given constraints.
            Returns the option with at least dte_delta more days till expiration and with
            price nearest to price_ratio times old price. 

        Args:
            dte_delta (int): exp of new minus exp of old
            price_ratio (float): market price of new divided by market price of old
        """
        logger.info(f'Looking for options to roll out by {dte_delta} days and roll up with credit...')
        options_rh = []
        while True:  # Continue until options_rh is non-empty
            new_exp_dt = self.get_exp_dt() + dt.timedelta(days=dte_delta)
            new_exp = new_exp_dt.strftime('%Y-%m-%d')
            options_rh = rh.options.find_options_by_expiration(self.symbol, new_exp, self.type)
            if options_rh: break
            logger.info(f'[{self.symbol}] No option found on {new_exp}.')
            logger.info(f'[{self.symbol}] Push out exp by 1 day.')
            dte_delta += 1
            
        # find options whose strike is greater than existing strike and price is greater than exisitng price.
        matchingOptions = []
        for option_rh in options_rh:
            mark_price = float(option_rh.get('adjusted_mark_price', 0))
            strike = float(option_rh.get('strike_price', 0))
            if mark_price > self.get_mark_price() and strike >= self.strike:
                option = Option(self.symbol, option_rh['expiration_date'], float(option_rh['strike_price']), option_rh['type'])
                matchingOptions.append(option)    
        
        if len(matchingOptions) == 0:
            logger.info('No mathcing option found for rolling.')
            return None
        
        matchingOptions = sorted(matchingOptions, key=lambda x: x.strike, reverse=True)
        
        matchingOptions_df = create_dataframe_from_option_list(matchingOptions)
        
        # Add a column to show potential credit earned if rolled.
        for index, row in matchingOptions_df.iterrows():
            matchingOptions_df.at[index, 'credit estimate'] = 100*(row['current price'] - self.get_mark_price())
    
        
        logger.info('Found these option candidates to roll to:')
        print(matchingOptions_df)
        
        # Select option based on risk level
        if risk_level == 'low':
            selectedOption = matchingOptions[0]
        elif risk_level == 'medium':
            mid_index = len(matchingOptions) // 2
            selectedOption = matchingOptions[mid_index]
        elif risk_level == 'high':
            selectedOption = matchingOptions[-1]

        logger.info(f'Selected option [{matchingOptions.index(selectedOption)}] to roll to.')
    
        return selectedOption

    def roll_option_ioc(self, new_option, position_type, quantity=1, mode='normal'):
        """Place an order to roll the underlying option to a new option .
        The order will be canceled if not filled in 2 minuntes.
        :param new_option: The option to roll to
        :type new_option: Option 
        :param position_type: long or short.
        :type position_type: str
        :param quantity: the number of options to roll.
        :type quantity: int
        :param mode: Normal mode or test mode
        :type mode: Optional[str]
        
        :returns: order_rh if order successful filled. Otherwise, returns None.
        """ 
        # Check if this option (self) is in position
        optionPositions = OptionPosition()
        old_option = optionPositions.find_and_update_option(self)
        if old_option == None:
            logger.info('Option to roll is not in position.')
            return None

        # Check if the underlying stock is the same
        if old_option.symbol != new_option.symbol:
            logger.info("The two options are not of the same underlying.")
            return None

        # Check if the option type is the same
        if old_option.type != new_option.type:
            logger.info("The two options are not of the same type. Need to be the same type for rolling.")
            return None

        old_limit_price = old_option.get_limit_price(update=True)
        new_limit_price = new_option.get_limit_price(update=True)

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
            return None

        debitOrCredit = "debit" if price > 0 else "credit"

        leg1 = {"expirationDate": old_option.exp,
                "strike": old_option.strike,
                "optionType": old_option.type,
                "effect":"close",
                "action": action1,
                "ratio_quantity": 1}

        leg2 = {"expirationDate": new_option.exp,
                "strike": new_option.strike,
                "optionType": new_option.type,
                "effect":"open",
                "action": action2,
                "ratio_quantity": 1}

        logger.info(f'[{self.symbol}] Attempt to place an order to roll:')
        logger.info(f'[{self.symbol}] from exp: {old_option.exp}, strike: {old_option.strike}')
        logger.info(f'[{self.symbol}] to   exp: {new_option.exp}, strike: {new_option.strike}')
        logger.info(f'[{self.symbol}] with credit: ${round(-1*price*100,2)}.')
        spread = [leg1,leg2]
        order_rh = rh.orders.order_option_spread(debitOrCredit, round(abs(price),2), new_option.symbol, quantity, spread, jsonify=False)
        if order_rh.status_code >= 300 or order_rh.status_code < 200:
            logger.info(f'[{self.symbol}] Failed to place order.')
            logger.info(f'[{self.symbol}] Reason: {order_rh.json()['detail']}')
            return None
        else:
            logger.info(f'[{self.symbol}] Succesfully placed order with status code {order_rh.status_code}. Waiting for order to be filled...')
            
        # Cancel order after waiting for 2 min 
        time.sleep(120) if mode != 'test' else time.sleep(0)
        pendingOrders = rh.orders.get_all_open_option_orders()
        for pendingOrder in pendingOrders:
            if order_rh.json()['id'] == pendingOrder['id']:
                rh.orders.cancel_option_order(pendingOrder['id'])
                logger.info(f"[{self.symbol}] Order cancelled since it is not filled after 2 min.")
                order_rh = None
        return order_rh


class OptionPosition():
    def __init__(self):
        # option positions in a list of Option object
        self.list = []
        
        # option positions in Dataframe format
        self.df = pd.DataFrame(columns=[])
        
        self.all_orders_rh = []
        
        # Update to latest
        self.update()
        
    def update(self):
        self.list = []
        optionPositions_rh = rh.options.get_open_option_positions()
        self.all_orders_rh = rh.orders.get_all_option_orders()
        
        optionTable = []
        for position in optionPositions_rh:
            option_rh = rh.options.get_option_instrument_data_by_id(position['option_id'])
            option = Option(option_rh['chain_symbol'], option_rh['expiration_date'], float(option_rh['strike_price']), option_rh['type'])
            quantity = float(position['quantity'])
            if position['type'] == 'short':
                option.quantity = -1*quantity
            elif position['type'] == 'long':
                option.quantity = quantity
            option.cum_cost = self.calculate_option_cumulative_cost(option)
            option.cost = self.calculate_option_cost(option)
            self.list.append(option)
            
            current_price = option.get_mark_price() * option.get_position_type()
            total_return = current_price * 100 * quantity - option.cum_cost

            row = {'symbol': option.symbol,
                   'type': option.type,
                   'side': option.get_position_type_str(),
                   'exp': option.exp,
                   'strike': option.strike,
                   'delta': option.get_delta(),
                   'theta': option.get_theta(),
                   'quantity': quantity,
                   'current price': round(current_price, 2),
                   'total value': round(current_price * 100 * quantity, 2),
                   'total cost': round(option.cum_cost, 2),
                   'total return': round(total_return, 2)
                   }
            
            optionTable.append(row)
        
        self.df = pd.DataFrame(optionTable)
        self.df.sort_values(by='total value', inplace=True, ascending=False)   
        columns_to_sum = ['total value', 'total cost', 'total return']
        self.df.loc['sum', columns_to_sum] = self.df[columns_to_sum].sum()

    def get_all_positions(self):
        return self.list
    
    def print_all_positions(self):
        # Print header
        print_with_time('---- Current Option Positions ----')
        print(self.df)
     
    def calculate_option_cost(self, option):  
        symbol = option.symbol
        exp = option.exp
        strike = option.strike
        type = option.type
        side = 'sell' if option.get_position_type() == -1 else 'buy'
        cost = 0

        [df_all, df_sc, df_lc] = self.tabulate_option_positions_by_symbol(symbol)
        
        if side == 'sell':
            df = df_sc
        else:
            df = df_lc
        
        # Reset the index of dataframe
        df.reset_index(drop=True, inplace=True)
        
        for index, row in df.iterrows():
            if row['effect'] == 'open' and exp == row['exp'] and strike == row['strike'] and type == row['type']:
                cost = abs(row['price']) * 100
                if side == 'sell': cost = -1 * cost
                break
                   
        return cost                
     
        
    def calculate_option_cumulative_cost(self, option):  
        symbol = option.symbol
        exp = option.exp
        strike = option.strike
        type = option.type
        side = 'sell' if option.get_position_type() == -1 else 'buy'
        cost = 0

        [df_all, df_sc, df_lc] = self.tabulate_option_positions_by_symbol(symbol)
        
        if side == 'sell':
            df = df_sc
        else:
            df = df_lc
        
        # Reset the index of dataframe
        df.reset_index(drop=True, inplace=True)
        
        for index, row in df.iterrows():
            if row['effect'] == 'open' and exp == row['exp'] and strike == row['strike'] and type == row['type']:
                if row['strategy'].startswith('open'):
                    cost += -1 * row['premium']
                    break
                elif row['strategy'].startswith('roll'):
                    if row['strategy'].endswith('#0'):
                        cost += -1 * row['premium']
                        exp = df.iloc[index+1]['exp']
                        strike = df.iloc[index+1]['strike']
                    else:
                        cost += -1 * df.iloc[index-1]['premium']
                        exp = df.iloc[index-1]['exp']
                        strike = df.iloc[index-1]['strike']
                   
        return cost                



    def find_and_update_option(self, option):
        """Find and update an option with position-related data such as cost and quantity. 

        Args:
            option (_type_): Option object type

        Returns:
            _type_: returns None if no option found in position.
                    returns an Option object with cost and quantity updated accroding to position.
        """
        for position in self.list:
            if position.get_id() == option.get_id():
                return position
        
        return None

    # Check if there are short call option of the given symbol in current postions
    def count_short_call_by_symbol(self, symbol):
        count = 0
        for position in self.list:
            type = position.type
            positionType = position.get_position_type_str()
            if  position.symbol == symbol and type == 'call' and positionType == 'short':
                count += abs(position.quantity)
        
        return count
   
    # Count how many long call positions of given symbol 
    def count_long_call_by_symbol(self, symbol):
        count = 0
        for position in self.list:
            type = position.type
            positionType = position.get_position_type_str()
            if  position.symbol == symbol and type == 'call' and positionType == 'long':
                count += abs(position.quantity)
        
        return count


    def tabulate_option_positions_by_symbol(self, symbol):
        """Process past option positions by symbol

            Args:
                symbol (_type_): string

            Returns:
                _type_: Pandas dataframe
                        returns 3 dataframes:
                        1) All options with legs expanded
                        2) All covered calls
                        3) All long calls 
            """
        filtered_orders_rh = [item for item in self.all_orders_rh if item['chain_symbol'] == symbol and item['state']== 'filled']
        df = pd.DataFrame(filtered_orders_rh)
        selected_columns = ['created_at', 'direction', 'legs', 'opening_strategy', 'closing_strategy', 'form_source', 'average_net_premium_paid', 'processed_premium', 'quantity']
        df_selected = df[selected_columns]
        expand_columns = ['time', 'strategy', 'effect', 'side', 'type', 'exp', 'strike', 'quantity', 'price', 'premium']
        df_all = pd.DataFrame(columns=expand_columns)
        for index, row in df_selected.iterrows():
            time = row['created_at'] 
            time_dt = dt.datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.%fZ')
            time_dt -= dt.timedelta(hours=7)
            time = time_dt.strftime('%Y-%m-%d %H:%M')
            quantity = float(row['quantity'])
            for legIndex, leg in enumerate(row['legs']):
                option_price = float(leg['executions'][0]['price'])
                effect = leg['position_effect']
                side = leg['side']
                option_type = leg['option_type']
                exp = leg['expiration_date']
                strike = float(leg['strike_price'])
                premium = option_price * quantity * 100
                premium = -1 * premium if side == 'buy' else premium
                if effect == 'open':
                    short_or_long = 'short' if side == 'sell' else 'long'
                else:
                    short_or_long = 'short' if side == 'buy' else 'long'  
                    
                if row['form_source'] == 'strategy_roll':
                    strategy = 'roll: ' + short_or_long+ ' ' + option_type + ' leg #' + str(legIndex)
                else:
                    strategy = effect + ': ' + short_or_long + ' ' + option_type

                df_all.loc[len(df_all)] = [time, strategy, effect, side, option_type, exp, strike, quantity, option_price, premium]
                
        df_all['running_premium'] = df_all.iloc[::-1]['premium'].cumsum()[::-1]
        
        
        # Pair orders occured at the same time a roll pair if certain conditions are met
        for index, row in df_all.iterrows():
            next_index = index + 1
            # Check if next index is within bounds and conditions match
            
            if next_index in df_all.index:
                if df_all.at[index, 'time'] == df_all.at[next_index, 'time']:
                    current_effect, next_effect = df_all.at[index, 'effect'], df_all.at[next_index, 'effect']
                    current_side = row['side']

                    # Handle "open-close" sequence
                    if current_effect == 'open' and next_effect == 'close':
                        leg_type = 'short' if current_side == 'sell' else 'long'
                        df_all.at[index, 'strategy'] = f'roll: {leg_type} {row["type"]} leg #0'
                        df_all.at[next_index, 'strategy'] = f'roll: {leg_type} {row["type"]} leg #1'

                    # Handle "close-open" sequence
                    elif current_effect == 'close' and next_effect == 'open':
                        leg_type = 'short' if current_side == 'buy' else 'long'
                        df_all.at[index, 'strategy'] = f'roll: {leg_type} {row["type"]} leg #0'
                        df_all.at[next_index, 'strategy'] = f'roll: {leg_type} {row["type"]} leg #1'
        
        # Calculate the net premium of roll pairs. 
        for index, row in df_all.iterrows():
            if row['strategy'][:4] == 'roll' and row['strategy'][-2:] == '#0':
                next_row = df_all.iloc[index+1]   
                df_all.at[index, 'premium'] += next_row['premium']
                df_all.at[index+1, 'premium'] = 0

        # Filter short calls (covered calls)
        mask = df_all['strategy'].str.contains('short call')
        df_sc = df_all.loc[mask].copy()
        df_sc['running_premium']=df_sc.iloc[::-1]['premium'].cumsum()[::-1]
        
        # Filter long calls (leaps)
        mask = df_all['strategy'].str.contains('long call')
        df_lc = df_all.loc[mask].copy()
        df_lc['running_premium']=df_lc.iloc[::-1]['premium'].cumsum()[::-1]
        
        return df_all, df_sc, df_lc

    def get_covered_call_limit(self, symbol):
        """Calculate the maximal amount of covered calls that can be written based on current positions

        Args:
            symbol (string): stock symbol of the call

        Returns:
            cc_limit (int): maximal number of covered call that can be written.  
        """    
        # Check how many existing short calls for the underlying stock
        logger.debug('Check how many existing short calls are in positions...')
        short_call_num = self.count_short_call_by_symbol(symbol)
        logger.debug(f'Total short calls: {short_call_num} for {symbol}.')
        
        # Check if there is long call positions to cover the short call
        logger.debug('Check how many existing long calls are in positions to cover short call....')
        long_call_num = self.count_long_call_by_symbol(symbol)
        logger.debug(f'Total long calls: {long_call_num} for {symbol}.')

        #TODO: Make the below code a method in optionPosition
        # Check if there is enough underlying stocks to cover the short call
        logger.debug('Check how many stocks in units of 100 to cover the short call...')
        stock_positions = rh.account.get_open_stock_positions()
        stock_lots = 0
        for position in stock_positions:
            stock_info = rh.stocks.get_stock_quote_by_id(position['instrument_id'])
            position_symbol = stock_info['symbol']
            if symbol == position_symbol:
                position_shares = float(position['quantity'])
                stock_lots = math.floor(position_shares/100)
                break
        logger.debug(f'Total stocks in units of 100: {stock_lots} for {symbol}.')
        
        cc_limit = long_call_num + stock_lots - short_call_num
        logger.debug(f'Covered call limit is: {cc_limit} for {symbol}.')
        return cc_limit


def find_options_by_delta(symbol, exp, type, delta_min, delta_max):
    """
    Find options for a given symbol within a specific delta range, expiration date, and type (call or put).

    :param symbol: The stock symbol ticker.
    :param exp: Expiration date of the options in 'YYYY-MM-DD' format.
    :param type: 'call' or 'put'.
    :param delta_min: Minimum delta value.
    :param delta_max: Maximum delta value.
    :return: A list of options in Option object that match the criteria. Otherwise, returns None.
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
    
    if len(matchingOptions) == 0: return None
    
    matchingOptions_sorted = sorted(matchingOptions, key=lambda x: x.get_delta())
        
    return matchingOptions_sorted

def create_dataframe_from_option_list(option_list):
    optionTable = []
    for option in option_list:
        row = { 'symbol': option.symbol,
                'type': option.type,
                'exp': option.exp,
                'strike': option.strike,
                'delta': option.get_delta(),
                'theta': option.get_theta(),
                'current price': round(option.get_mark_price(), 2)
                }
        optionTable.append(row)
        
    return pd.DataFrame(optionTable)


def is_option_in_open_orders(option):
    existingOrders_rh = rh.orders.get_all_open_option_orders()
    for order in existingOrders_rh:
        legs = order['legs']
        for leg in legs:
            existingOption_rh = rh.helper.request_get(leg['option'])
            if option.get_id() == existingOption_rh['id']:
                return True 
    return False


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
    logger.info('--See if there are short call positions already...')
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

