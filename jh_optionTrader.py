import datetime as dt
import time
import robin_stocks.robinhood as rh
from jh_utilities import *
from jh_options import *
logger = get_logger(__name__)



class OptionTrader():
    def __init__(self, symbol_list, mode, risk_level='low', delta=0.2, MAX_ATTEMPT=5) -> None:
        self.positions = OptionPosition()
        self.symbol_list = symbol_list
        self.mode = mode
        self.risk_level = risk_level
        self.delta = delta
        self.MAX_ATTEMPT = MAX_ATTEMPT

    def print_all_positions(self):
        self.positions.print_all_positions()
    
    def print_all_orders(self):
        orders_rh = rh.orders.get_all_open_option_orders()
        print(orders_rh)
        
    def run_cc(self, risk_level='low', delta=0.2, MAX_ATTEMPT=5):
        # Opening covered call position
        # Determine if today is Monday
        logger.info('******** Running covered call strategy ********')
        logger.info('Place covered calls as position allows and manage cover calls')
        logger.info('Your selected mode is ' + self.mode)

        self.risk_level = risk_level
        self.delta = delta
        self.MAX_ATTEMPT = MAX_ATTEMPT
        
        while True:
            self.place_short_calls_logic()      
            self.manage_short_calls_logic()
            time.sleep(300) if self.mode != 'test' else time.sleep(0)
            
    def place_short_calls_logic(self):
        """Place short calls as allowed by current position.
        """  
        shortCallOrder_rh_list = []
        todayDate_dt = dt.datetime.today().date()
        exp_dt = get_2nd_next_friday()
        if is_market_open_now() or self.mode == 'test':
            if not is_market_open_on_date(exp_dt):
                # If expiration date is a holiday, push to next week's Friday
                exp_dt = todayDate_dt + dt.timedelta(weeks=1)

            dte = (exp_dt - todayDate_dt).days
           
            # Attempt to place limit order based on mid bid-ask price.
            # If order not filled in x minutes, cancel the orders and place again for MAX_ATTEMPT times.
            # Each attempt slightly increase the bit price.
            attempt = 0
            logger.info('**** Entering short call placing logic ****')
            logger.info(f'In total {self.MAX_ATTEMPT} attempts to place orders.')
            while attempt < self.MAX_ATTEMPT:
                # Attempt to place short calls for all the symbols
                for symbol in self.symbol_list:
                    shortCallOrder_rh = self.open_short_call(symbol, dte, 0.5+0.05*attempt)
                    if shortCallOrder_rh != None:
                        shortCallOrder_rh_list.append(shortCallOrder_rh) 
                
                # Break the loop if no short call order is placed
                if len(shortCallOrder_rh_list) == 0: 
                    logger.info(f'No short call order placed due to cc limit reached.')
                    break 
                
                # Wait for 5 min for the orders to be filled.        
                time.sleep(300) if self.mode != 'test' else time.sleep(0)
                
                pendingOrders_rh = rh.orders.get_all_open_option_orders()
                # Break the loop once all orders are filled
                if len(pendingOrders_rh) == 0: break
                
                # Cancel unfilled orders
                logger.info(f'Cancelling orders not filled in 5 min. Starting attempt #{attempt+2}')
                for shortCallOrder_rh in shortCallOrder_rh_list:
                    for pendingOrder_rh in pendingOrders_rh:
                        if shortCallOrder_rh['id'] == pendingOrder_rh['id']:
                            rh.orders.cancel_option_order(pendingOrder_rh['id'])
            
                attempt += 1

    def manage_short_calls_logic(self):
        """Manage all existing short calls by considering moneyness, return rate, etc.
        """    
        # Manage opened covered call positions
        # Gather all covered calls in positions
        # Run loop until no covered calls left in position.
        logger.info('**** Entering short call managing logic ****')
        logger.info('Gathering all covered calls in current positions...')
        shortCalls = []
        self.positions.update() 
        for position in self.positions.list:
            if position.type == 'call' and position.get_position_type_str() == 'short' and position not in shortCalls:
                shortCalls.append(position)
        
        shortCalls_df = self.positions.df.loc[self.positions.df['side'] == 'short']
        shortCalls_df.reset_index(drop=True, inplace=True)
        print(shortCalls_df)
        
        if is_market_open_now() or self.mode == 'test':
            for option in shortCalls:
                self.manage_short_call(option) 
        

    def open_short_call(self, symbol, dte, price_ratio=0.5):
        """Open short call positions with the specified stock symbol, dte, risk level, and delta range.
            The number of short calls opened is determined by the maximal short call limit in current position.

            Args:
                symbol (_type_): string

            Returns:
                _type_: Returns None if no position is opened. Otherwise, returns order_rh
        """
        logger.info(f'Openning short call for {symbol} with {dte} days till expiration')
        # Check if there are enough securities to "cover" this call
        quantity = self.positions.get_covered_call_limit(symbol)
        if  quantity <= 0:
            logger.info('Max covered call limit reached. No order placed.')
            return None
    
        # Calculate expiration date
        exp_dt = dt.datetime.now().date() + dt.timedelta(days=dte) 
        exp = exp_dt.strftime('%Y-%m-%d')

        # Define profit floor and ceiling
        delta_min = 0.05
        delta_max = self.delta if self.delta > delta_min+0.05 else delta_min+0.05
        logger.info(f'Looking for calls to sell with delta between {delta_min} and {delta_max}, expiring on {exp}')

        # Find potential options
        try: 
            [potentialOptions, potentialOptions_df] = find_options_by_delta(symbol, exp, 'call', delta_min, delta_max)
        except EmptyListError as e:
            logger.error(f"No option found matching the given delta range: {e}")
            return None

        # Print potential options
        logger.info('Found these options matching criteria:')
        print(potentialOptions_df)

        # Select option based on risk level
        if self.risk_level == 'low':
            selectedOption = potentialOptions[0]
        elif self.risk_level == 'medium':
            mid_index = len(potentialOptions) // 2
            selectedOption = potentialOptions[mid_index]
        elif self.risk_level == 'high':
            selectedOption = potentialOptions[-1]

        logger.info(f'Selected option [{potentialOptions.index(selectedOption)}].')

        # Check if the order already exists in currrent open orders
        logger.info('Checking if this option is already in open orders')
        if is_option_in_open_orders(selectedOption):
            logger.info('This order already exists in current open orders. Order not placed.')
            return None


        # Calculate limit price
        limit_price = selectedOption.get_limit_price(price_ratio, update=True)
        logger.info(f'Opening a limit order to sell at ${limit_price}...')

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
            timeInForce='gfd',
            jsonify=False
        )
        
        if order_rh.status_code >= 300 or order_rh.status_code < 200:
             logger.info('Failed to place order.')
             logger.info(f'Reason: {order_rh.json()['detail']}')
             return None
        else:
            logger.info(f'Succesfully placed order with status code {order_rh.status_code}.')
             
        logger.info('Order placed with the following information:')
        logger.info(f'Symbol: {selectedOption.symbol}')
        logger.info(f'Exp date: {selectedOption.exp}')
        logger.info(f'Strike Price: {selectedOption.strike}')
        logger.info(f'Premium to be collected if filled: ${round(limit_price*100, 2)}')
        logger.info(f'Premium to be collected if filled (should match above): ${order_rh['premium']}')
        return order_rh

    def manage_short_call(self, option):
        status = None
        logger.info(f'** Managing short call with symbol: {option.symbol}, exp: {option.exp}, strike: {option.strike} **')

        # Check if the short call exists in open positions
        option = self.positions.find_and_update_option(option)
        if option == None:
            logger.critical(f'[{option.symbol}] The short option to close is not open in your account. Option not closed.')
            return None
            
        # Check if the short call is in open orders
        if is_option_in_open_orders(option):
            logger.info(f'[{option.symbol}] The order for this short call is queuing in current open orders. Wait till it is filled.')
            return None
        
        cost = option.cost
        price = option.get_mark_price() * option.get_position_type()
        total_return = price * 100 - cost
        quantity = abs(option.quantity)
        return_rate = total_return/abs(cost)       
        return_pcnt = round(return_rate * 100, 2)
        dte = (option.get_exp_dt().date() - dt.datetime.now().date()).days
        strike = option.strike
        stockPrice = float(rh.stocks.get_latest_price(option.symbol)[0])
        logger.info(f'[{option.symbol}] The short call has {dte} days till expiration')
        logger.info(f'[{option.symbol}] Stock price: {stockPrice} vs strike price: {strike}.')
        logger.info(f'[{option.symbol}] Return percentage now is {return_pcnt}%')

        # Managing logic
        if strike < stockPrice or self.mode == 'test':
            logger.info(f'[{option.symbol}] This call is currently in the money!')
            if dte <= 1 and strike < 0.95*stockPrice or self.mode == 'test':
                logger.info(f'[Action] Rolling this call to prevent assignment since call deep ITM and dte = {dte}.')
                option_to_roll = option.find_option_to_rollup_with_credit(dte_delta=5, risk_level=self.risk_level)
                status = None if option_to_roll == None else option.roll_option_ioc(option_to_roll, 'short', quantity, mode=self.mode)
            elif dte == 0 and strike >= 0.95*stockPrice:
                logger.info(f'[Action] Rolling this call to prevent assignment since call ITM and it expires today.')
                option_to_roll = option.find_option_to_rollup_with_credit(dte_delta=7, risk_level=self.risk_level)
                status = None if option_to_roll == None else option.roll_option_ioc(option_to_roll, 'short', quantity, mode=self.mode)
            else:
                logger.info(f'[Action] Too early for action. Do nothing.\n')
        else :
            if return_rate > 0.95:
                logger.info(f'[Action] Rolling this call to start a new cc cycle since call gained >95% return. ')
                option_to_roll = option.find_option_to_roll_by_delta(dte_delta=7, risk_level=self.risk_level, delta=self.delta)
                status = None if option_to_roll == None else option.roll_option_ioc(option_to_roll, 'short', quantity, mode=self.mode)
            else:
                logger.info(f'[Action] Too early for action. Do nothing.\n')
        return status

    
        
        