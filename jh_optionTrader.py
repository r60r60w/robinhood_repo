import datetime as dt
import logging
import time
import robin_stocks.robinhood as rh
from jh_utilities import *
from jh_options import *
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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
    


    
        
        