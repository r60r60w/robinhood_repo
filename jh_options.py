import datetime as dt
import time
import robin_stocks.robinhood as rh
import pandas as pd
import math
import matplotlib.pyplot as plt
import yfinance as yf
from jh_utilities import *
#logger = get_logger(__name__)
logger = get_logger(__name__, log_to_file=False, file_name="my_log_file.log")

class Option():
    def __init__(self, symbol, exp, strike, type):
        self.symbol = symbol 
        self.exp = exp
        self.strike = strike
        self.type = type
        self.quantity = 0
        self.cost = 0
        self.cum_cost = 0 # Cumulative cost considering option rolls.
        self._volume = 0
        self._OI = 0
        self._bid_price = 0
        self._ask_price = 0
        self._mark_price = 0
        self._delta = 0
        self._theta = 0
        self.id = 0 # To be updated by the below method
        self.valid = self.update()

    def get_option_rh(self): 
        options_rh = rh.options.find_options_by_expiration_and_strike(self.symbol, self.exp, self.strike, self.type)
        if not options_rh:
            logger.debug("Returned None type. No option found.")
            raise EmptyListError()

        return options_rh

    def update(self):
        logger.debug("updating option...")
        try:
            options_rh = self.get_option_rh()
            
        except EmptyListError as e:
            body = f"No option found: {e} for {self.symbol}, {self.exp}, {self.strike}."
            logger.error(body)
            send_email_notification(subject=f"Error Received", body=body)
            return False
        else:
            option_rh = options_rh[0]

        def keys_exist(dictionary, keys):
            return all(key in dictionary for key in keys)

        keys_to_check = ['ask_price', 'bid_price', 'adjusted_mark_price', 'delta', 'theta', 'volume', 'open_interest', 'id']

        if keys_exist(option_rh, keys_to_check):
            pass
        else:
            logger.error(f"KeyError: {option_rh}")
            body = f"KeyError: {option_rh}"
            send_email_notification(subject=f"Error Received", body=body)
            return False

        self._ask_price = round(float(option_rh['ask_price']), 2)
        self._bid_price = round(float(option_rh['bid_price']), 2)
        self._mark_price = round(float(option_rh['adjusted_mark_price']), 2)
        self._delta = round(float(option_rh['delta']), 4)
        self._theta = round(float(option_rh['theta']), 4)
        self._volume = option_rh['volume']
        self._OI = option_rh['open_interest']
        self.id = option_rh['id']
        return True

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
    
    def get_volume(self, update=False):
        if update:
            self.update()
        return self._volume
    
    def get_OI(self, update=False):
        if update:
            self.update()
        return self._OI
    
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
        
        if not matchingOptions:
            logger.info(f'[{self.symbol}] No mathcing option found for rolling matching the delta range.')
            return None        
        
        # Filter options with positive credit
        matchingOptionsWithCredit = []
        for option in matchingOptions:
            if option.get_mark_price()-self.get_mark_price() > 0:
                    matchingOptionsWithCredit.append(option)
        
        if not matchingOptionsWithCredit:
            logger.info(f'[{self.symbol}] No mathcing option found for rolling that yields positive credit.')
            return None        
        
        # Print potential options
        matchingOptions_df = create_dataframe_from_option_list(matchingOptionsWithCredit)
        
        # Add a column to show potential credit earned if rolled.
        for index, row in matchingOptions_df.iterrows():
            matchingOptions_df.at[index, 'credit estimate'] = 100*(row['current price'] - self.get_mark_price())
            
        logger.info(f'[{self.symbol}] Found these options candidates to roll to:')
        print(matchingOptions_df)

        # Select option based on risk level
        if risk_level == 'low':
            selectedOption = matchingOptionsWithCredit[0]
        elif risk_level == 'medium':
            mid_index = len(matchingOptionsWithCredit) // 2
            selectedOption = matchingOptionsWithCredit[mid_index]
        elif risk_level == 'high':
            selectedOption = matchingOptionsWithCredit[-1]
        logger.info(f'Selected option [{matchingOptionsWithCredit.index(selectedOption)}] to roll to.')
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



class OptionPosition():
    def __init__(self):
        self.list = [] # option positions in a list of Option object
        self.df = pd.DataFrame(columns=[]) # option positions in Dataframe format
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
            if option_rh is None:
                logger.error(f'Option {position["option_id"]} is not found. Skip this option.')
                continue
            option = Option(option_rh['chain_symbol'], option_rh['expiration_date'], float(option_rh['strike_price']), option_rh['type'])
            if not option.valid:
                logger.error(f'Option {option.symbol} is not valid. Skip this option.')
                continue
            quantity = float(position['quantity'])
            if position['type'] == 'short':
                option.quantity = -1*quantity
            elif position['type'] == 'long':
                option.quantity = quantity
            option.cum_cost = self.calculate_option_cumulative_cost(option)
            option.cost = self.calculate_option_cost(option)
            self.list.append(option)
            
            stock_price = float(rh.stocks.get_latest_price(option.symbol)[0])
            current_price = option.get_mark_price() * option.get_position_type()
            total_return = current_price * 100 * quantity - option.cum_cost
            return_percentage = (current_price * 100 * quantity - option.cost)/abs(option.cost)*100

            row = {'symbol': option.symbol,
                   'type': option.type,
                   'side': option.get_position_type_str(),
                   'exp': option.exp,
                   'strike': option.strike,
                   'stock price': round(stock_price, 2),
                   'delta': option.get_delta(),
                   'theta': option.get_theta(),
                   'quantity': quantity,
                   'current price': round(current_price, 2),
                   'cost': round(option.cost, 2),
                   'current value': round(current_price * 100 * quantity, 2),
                   'cum. cost': round(option.cum_cost, 2),
                   'cum. return': round(total_return, 2),
                   'return %': f'{round(return_percentage, 2)}%'
                   }
            
            optionTable.append(row)
        
        self.df = pd.DataFrame(optionTable)
        self.df.sort_values(by='current value', inplace=True, ascending=False)   
        columns_to_sum = ['cost', 'current value', 'cum. cost', 'cum. return']
        self.df.loc['sum', columns_to_sum] = self.df[columns_to_sum].sum()

    def get_all_positions(self):
        return self.list
    
    def print_all_positions(self):
        print(self.df)
     
    def calculate_option_cost(self, option):  
        symbol = option.symbol
        exp = option.exp
        strike = option.strike
        type = option.type
        side = 'sell' if option.get_position_type() == -1 else 'buy'
        cost = 0

        [_, df_sc, df_lc] = self.tabulate_option_positions_by_symbol(symbol)
        
        if side == 'sell':
            df = df_sc
        else:
            df = df_lc
        
        # Reset the index of dataframe
        df.reset_index(drop=True, inplace=True)
        
        cost = 0
        for _, row in df.iterrows():
            if row['effect'] == 'open' and exp == row['exp'] and strike == row['strike'] and type == row['type']:
                cost_change = abs(row['price']) * row['quantity'] * 100
                if side == 'sell': 
                    cost_change = -1 * cost_change
                cost = cost + cost_change
                   
        return cost                
     
        
    def calculate_option_cumulative_cost(self, option):  
        symbol = option.symbol
        exp = option.exp
        strike = option.strike
        type = option.type
        quantity = abs(option.quantity)
        side = 'sell' if option.get_position_type() == -1 else 'buy'
        cost = 0

        [_, df_sc, df_lc] = self.tabulate_option_positions_by_symbol(symbol)
        
        if side == 'sell':
            df = df_sc
        else:
            df = df_lc
        
        # Reset the index of dataframe
        df.reset_index(drop=True, inplace=True)
        
        for index, row in df.iterrows():
            if row['effect'] == 'open' and exp == row['exp'] and strike == row['strike'] and type == row['type']:
                if row['strategy'].startswith('open'):
                    cost += -1 * row['premium'] * (quantity/row['quantity'])
                elif row['strategy'].startswith('roll'):
                    if row['strategy'].endswith('#0'):
                        cost += -1 * row['premium'] * (quantity/row['quantity'])
                        exp = df.iloc[index+1]['exp']
                        strike = df.iloc[index+1]['strike']
                    else:
                        cost += -1 * df.iloc[index-1]['premium'] * (quantity/row['quantity'])
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
        rows = []
        for index, row in df_selected.iterrows():
            time = row['created_at'] 
            time_dt = dt.datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.%fZ')
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

                rows.append([time, strategy, effect, side, option_type, exp, strike, quantity, option_price, premium])
        
        df_all = pd.DataFrame(rows, columns=expand_columns)
                
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
            strategy_prefix = row['strategy'][:4]
            strategy_suffix = row['strategy'][-2:]
            if strategy_prefix == 'roll' and strategy_suffix == '#0':
                next_row = df_all.iloc[index + 1]
                df_all.at[index, 'premium'] += next_row['premium']
                df_all.at[index + 1, 'premium'] = 0

        # Filter short calls (covered calls)
        mask = df_all['strategy'].str.contains('short call')
        df_sc = df_all.loc[mask].copy()
        df_sc['running_premium']=df_sc.iloc[::-1]['premium'].cumsum()[::-1]
        
        # Filter long calls (leaps)
        mask = df_all['strategy'].str.contains('long call')
        df_lc = df_all.loc[mask].copy()
        df_lc['running_premium']=df_lc.iloc[::-1]['premium'].cumsum()[::-1]
        
        return df_all, df_sc, df_lc
    
    def tabulate_short_call_PnL_by_symbol(self, symbol):
        """
        Tabulate PnL (Profit and Loss) of short call positions by symbol.
        Args:
            symbol (str): The symbol for which to tabulate the PnL.
        Returns:
            pandas.DataFrame: A dataframe containing the PnL of short call positions.
                            The dataframe includes the following columns:
                            - 'time': The time of the position.
                            - 'premium': The premium of the position.
                            - 'running_premium': The running premium of the position.
        """
        [_, df_sc, _] = self.tabulate_option_positions_by_symbol(symbol)
        df = df_sc
        df.reset_index(drop=True, inplace=True)
        # Remove rows whose strategy column ends with "#1"
        df = df[~df['strategy'].str.endswith('#1')]
        columns_to_keep = ['time', 'premium', 'running_premium']
        df = df[columns_to_keep]
        return df
    
    
    def plot_short_call_PnL_by_symbol(self, symbol, week_range):
        """
        Plots the Profit and Loss (PnL) for short call options by symbol over a specified range of weeks.
        Args:
            symbol (str): The stock symbol for which to plot the short call PnL.
            week_range (int): The number of weeks to include in the plot.
        Returns:
            None: This function displays a plot and does not return any value.
        """
        df = self.tabulate_short_call_PnL_by_symbol(symbol)
        end_date = dt.datetime.now()
        start_date = end_date - dt.timedelta(weeks=week_range)
        df['time'] = pd.to_datetime(df['time'])
        df_filtered = df[(df['time'] >= start_date) & (df['time'] <= end_date)]
        
        df_filtered = df_filtered.sort_values(by='time', ascending=True)
        
        fig, ax = plt.subplots(2, 1, figsize=(10, 10), sharex=True)
        
        ax[0].plot(df_filtered['time'], df_filtered['running_premium'], marker='o', linestyle='-', color='b')
        ax[0].set_ylabel('Running Premium')
        ax[0].set_title(f'Short Call Running Premium for {symbol} (Last {week_range} weeks)')
        ax[0].grid(True)
        
        ax[1].plot(df_filtered['time'], df_filtered['premium'], marker='o', linestyle='-', color='r')
        ax[1].set_xlabel('Time')
        ax[1].set_ylabel('Premium')
        ax[1].set_title(f'Short Call Premium for {symbol} (Last {week_range} weeks)')
        ax[1].grid(True)
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
        
    def plot_short_call_PnL_for_multiple_symbols(self, symbol_list, week_range):
        """Plot the premium for multiple symbols overlaying the results in one plot.

        Args:
            symbols (list): List of stock symbols.
            week_range (int): Number of weeks to look back for the plot.
        """
        end_date = dt.datetime.now()
        start_date = end_date - dt.timedelta(weeks=week_range)
        
        plt.figure(figsize=(12, 8))
        
        for symbol in symbol_list:
            df = self.tabulate_short_call_PnL_by_symbol(symbol)
            df['time'] = pd.to_datetime(df['time'])
            df_filtered = df[(df['time'] >= start_date) & (df['time'] <= end_date)]
            df_filtered = df_filtered.sort_values(by='time', ascending=True)
            
            plt.plot(df_filtered['time'], df_filtered['premium'], marker='o', linestyle='-', label=symbol)
        
        plt.xlabel('Time')
        plt.ylabel('Premium')
        plt.title(f'Short Call Premium for Multiple Symbols (Last {week_range} weeks)')
        plt.legend()
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()

    def plot_covered_call_vs_stock(self, symbol, week_range):
        """
        Plot the stock price and the covered call premium for a given symbol over a given range of weeks.
        This function retrieves historical stock prices and covered call option data for a specified symbol and plots the stock price along with the covered call premium over a specified range of weeks. The plot includes markers and lines indicating the opening and expiration of covered call options, with color coding to show whether the stock price at expiration was above or below the strike price.
        Args:
            symbol (str): The stock symbol to retrieve data for.
            week_range (int): The range of weeks to plot data for. Must be no greater than 12 weeks.
        Returns:
            bool: True if the plot was successfully generated, False otherwise.
        """
        _, df_sc, _ = self.tabulate_option_positions_by_symbol(symbol)
        df_sc = df_sc[df_sc['effect']!='close']
        df_sc['time'] = pd.to_datetime(df_sc['time'])
        df_sc['date'] = df_sc['time'].dt.date
        
        end_date = dt.datetime.now()
        start_date = end_date - dt.timedelta(weeks=week_range)
        
        df_filtered = df_sc[(df_sc['date'] >= start_date.date()) & (df_sc['date'] <= end_date.date())]
        
        if week_range <=1:
            interval = '2m'
            period = '1mo'
        elif week_range <=2:
            interval = '5m'
            period = '1mo'
        elif week_range <=4:
            interval = '15m'
            period = '1mo'
        elif week_range <=12:
            interval = '1h'
            period = '3mo'  
        else:
            logger.info('The range is too long. Please select a range no greater than 12 weeks.')
            return False
        
        # stock_prices = rh.stocks.get_stock_historicals(symbol, interval='10minute', span=f'3month')
        # stock_prices_df = pd.DataFrame(stock_prices)
        # stock_prices_df['begins_at'] = pd.to_datetime(stock_prices_df['begins_at'])
        # stock_prices_df['begins_at'] = stock_prices_df['begins_at'].dt.strftime('%Y-%m-%d %H:%M')
        # stock_prices_df['close_price'] = stock_prices_df['close_price'].astype(float)
        # stock_prices_df['begins_at'] = pd.to_datetime(stock_prices_df['begins_at'])
        # stock_prices_df = stock_prices_df[(stock_prices_df['begins_at'] >= start_date) & (stock_prices_df['begins_at'] <= end_date)]

        ticker = yf.Ticker(symbol)
        stock_data = ticker.history(period=period, interval=interval)
        stock_prices_df = stock_data.reset_index()
        stock_prices_df.rename(columns={'Datetime': 'begins_at', 'Close': 'close_price'}, inplace=True)
        stock_prices_df['begins_at'] = stock_prices_df['begins_at'].dt.strftime('%Y-%m-%d %H:%M')
        stock_prices_df['begins_at'] = pd.to_datetime(stock_prices_df['begins_at'])
        stock_prices_df['date'] = stock_prices_df['begins_at'].dt.date
        stock_prices_df = stock_prices_df[(stock_prices_df['date'] >= start_date.date()) & (stock_prices_df['date'] <= end_date.date())]
        stock_prices_df = stock_prices_df.reset_index()
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        ax.plot(range(len(stock_prices_df['begins_at'])), stock_prices_df['close_price'], label='Stock Price', color='blue')
        ax.set_xticks([i for i in range(len(stock_prices_df['begins_at'])) if stock_prices_df['begins_at'].iloc[i].hour == 9 and stock_prices_df['begins_at'].iloc[i].minute == 30])  # Assuming market opens at 9:30 AM
        ax.set_xticklabels(stock_prices_df['begins_at'].dt.strftime('%Y-%m-%d %H:%M')[ax.get_xticks()], rotation=45, ha='right')

        for index, row in df_filtered.iterrows():
            open_time = row['time']
            strike_price = row['strike']
            exp_time = dt.datetime.strptime(row['exp'], '%Y-%m-%d')
            
            # Find stock price when the option was opened.
            if stock_prices_df[stock_prices_df['begins_at'] == open_time].empty:
                nearest_time = stock_prices_df.iloc[(stock_prices_df['begins_at'] - open_time).abs().argsort()[:1]]['begins_at'].values[0]
                stock_price_at_open = stock_prices_df[stock_prices_df['begins_at'] == nearest_time]['close_price'].values[0]
                open_index = stock_prices_df[stock_prices_df['begins_at'] == nearest_time].index[0]
            else:
                stock_price_at_open = stock_prices_df[stock_prices_df['begins_at'] == open_time]['close_price'].values[0]
                open_index = stock_prices_df[stock_prices_df['begins_at'] == open_time].index[0]
                
            # Find stock price when the option expires.
            if stock_prices_df[stock_prices_df['begins_at'] == exp_time].empty:
                nearest_time = stock_prices_df.iloc[(stock_prices_df['begins_at'] - exp_time).abs().argsort()[:1]]['begins_at'].values[0]
                stock_price_at_exp = stock_prices_df[stock_prices_df['begins_at'] == nearest_time]['close_price'].values[0]
                exp_index = stock_prices_df[stock_prices_df['begins_at'] == nearest_time].index[0]
            else:
                stock_price_at_exp = stock_prices_df[stock_prices_df['begins_at'] == exp_time]['close_price'].values[0]
                exp_index = stock_prices_df[stock_prices_df['begins_at'] == exp_time].index[0]
                
            if stock_price_at_exp > strike_price:
                color = 'red'
            else:
                color = 'green'
                
            ax.plot([open_index, exp_index], [stock_price_at_open, strike_price], color=color, linestyle='--', marker='o')
            ax.fill_betweenx([stock_price_at_open, strike_price], open_index, exp_index, color=color, alpha=0.3)
            
        ax.set_xlabel('Time')
        ax.set_ylabel('Price')
        ax.set_title(f'Covered Call Overlay vs Stock Price for {symbol} (Last {week_range} weeks)')
        ax.legend()
        ax.grid(True)
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
        return True

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
        logger.debug('Check how many stocks in units of 100 shares to cover the short call...')
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
    
    def get_all_symbols_for_cc(self):
        symbols = []
        
        # Gather symbols that have greater than 100 shares of stocks
        stock_positions = rh.account.get_open_stock_positions()
        for position in stock_positions:
            stock_info = rh.stocks.get_stock_quote_by_id(position['instrument_id'])
            symbol = stock_info['symbol']
            position_shares = float(position['quantity'])
            if position_shares >= 100:
                if symbol not in symbols:
                    symbols.append(symbol)
        
        # Gather symbols that have long call positions
        for position in self.list:
            symbol = position.symbol
            if position.type == 'call' and position.get_position_type_str() == 'long':
                if symbol not in symbols:
                    symbols.append(symbol) 
        
        return symbols

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
        if not optionData_tmp: continue # Skip this option if no market data can be found due to off-market hours.
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
                'current price': round(option.get_mark_price(), 2),
                'volume': option.get_volume(),
                'open interest': option.get_OI()
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

