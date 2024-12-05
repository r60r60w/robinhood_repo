import datetime as dt       
import robin_stocks.robinhood as rh
from jh_utilities import *
from jh_options import *
from technical_indicator import *
import yfinance as yf
import random
#import threading
#logger = get_logger(__name__)
logger = get_logger(__name__, log_to_file=False, file_name="my_log_file.log")

'''
class TradingSignal:
    """Encapsulates trading signals and synchronization."""
    def __init__(self):
        self.signal_event = threading.Event()  # Event to notify the main thread
        self.signal = 0 # Current trading signal wiith -3/-2/-1/0/1/2/3 corresponding to
                        # strong sell/medium sell/weak sell/hold/weak buy/medium buy/strong buy)
        self.signal_lock = threading.Lock()  # Lock to protect signal access

    def set_signal(self, signal):
        """Set a new trading signal and notify."""
        with self.signal_lock:
            self.signal = signal
            logger.info(f"WorkerThread: Generated signal = {signal}. Notifying main thread.")
            self.signal_event.set()  # Notify the main thread

    def get_signal(self):
        """Retrieve the current signal."""
        with self.signal_lock:
            return self.signal

    def reset_event(self):
        """Reset the event after the signal is processed."""
        self.signal_event.clear()
        
class StockAlgorithmThread(threading.Thread):
    def __init__(self, symbol, trading_signal, generate_plot=False):
        super().__init__()
        self.symbol = symbol
        self.generate_plot = generate_plot
        self.trading_signal = trading_signal  # Shared TradingSignal object
        self.running = True  # Control thread execution

    def stop(self):
        """Stop the thread gracefully."""
        self.running = False

    def run(self):
        logger.info(f"[{self.symbol}] WorkerThread: Starting stock price analysis...")
        while self.running:
            stock = yf.Ticker(self.symbol)
            #df = yf.download(symbol, period='5d', interval='5m')
            df = stock.history(period='5d', interval='5m')

            # Apply the MACD calculation and Wilder's RSI indicator
            df = calculate_macd(df, short_window=12, long_window=26, signal_window=9)
            df = calculate_wilders_rsi(df, window=14)
            df = generate_signals(df)
            
            if self.generate_plot:
                plot_signals(df, self.symbol)
                
            live_price = df.iloc[-1]['Close']
            print(f"[{self.symbol}] WorkerThread: Live price = {live_price}")

            # Generate a buy/sell/hold signal based on some conditions
            if df.iloc[-1]['buy_signal'] == 1 or self.mode == 'test':
                logger.info(f"[{self.symbol}] Weak buy signal detected.")
                self.trading_signal.set_signal(1)
            elif df.iloc[-1]['buy_signal'] == 2:
                logger.info(f"[{self.symbol}] Medium buy signal detected.")
                self.trading_signal.set_signal(2)
            elif df.iloc[-1]['buy_signal'] == 3:
                logger.info(f"[{self.symbol}] Strong buy signal detected.")
                self.trading_signal.set_signal(3)
            else:
                logger.info(f"[{self.symbol}] No buy signal detected.")
                
            if df.iloc[-1]['sell_signal'] == 1 or self.mode == 'test':
                logger.info(f"[{self.symbol}] Weak sell signal detected.")
                self.trading_signal.set_signal(-1)
            elif df.iloc[-1]['sell_signal'] == 2:
                logger.info(f"[{self.symbol}] Medium sell signal detected.")
                self.trading_signal.set_signal(-2)
            elif df.iloc[-1]['sell_signal'] == 3:
                logger.info(f"[{self.symbol}] Strong sell signal detected.")
                self.trading_signal.set_signal(-3)
            else:
                logger.info(f"[{self.symbol}] No sell signal detected.")
            
            time.sleep(300) if self.mode != 'test' else time.sleep(0)
'''

class OptionTrader():
    def __init__(self, symbol_list=[], mode='test', risk_level='low', delta=0.2, MAX_ATTEMPT=5) -> None:
        self.positions = OptionPosition()
        
        if len(symbol_list) == 0:
            logger.info('No stock symbol is provided. Looking for all available symbols for covered call.')
            self.symbol_list = self.positions.get_all_symbols_for_cc()
            logger.info(f'All available stocks for covered call: {self.symbol_list}')
        else:
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
        
    def run_cc(self, risk_level='low', delta=0.2, MAX_ATTEMPT=5, only_manage_existing=False):
        # Opening covered call position
        # Determine if today is Monday
        logger.info('******** Running covered call strategy ********')
        logger.info('Place covered calls as position allows and manage cover calls')

        self.risk_level = risk_level
        self.delta = delta
        self.MAX_ATTEMPT = MAX_ATTEMPT

        # Create and start the worker thread
        # stock_threads = {key: None for key in self.symbol_list}
        # trading_signals = {key: TradingSignal() for key in self.symbol_list}  # Shared trading signal objects
        # for symbol in self.symbol_list:
        #     stock_threads[symbol] = StockAlgorithmThread(symbol, trading_signals[symbol], generate_plot=False)
        #     stock_threads[symbol].start()
        try: 
            while True:
                if is_market_open_now() or self.mode == 'test':
                    logger.info('******** New iteration started ********')
                    logger.info(f'Important parameters: mode = {self.mode}, delta = {delta}, risk level = {risk_level}.')
                    logger.info(f'All current option positions:')
                    self.positions.df.reset_index(drop=True, inplace=True)
                    self.positions.print_all_positions()
                    if not only_manage_existing:
                        self.place_short_calls_logic()      
                    self.manage_short_calls_logic()
                    minutes = random.randint(3, 8)
                else:
                    logger.info('Market is closed now.')       
                    minutes = random.randint(20, 30)      
                    
                logger.info(f'Wait for {minutes} min before starting new iteration.')
                custom_sleep_with_progress(minutes*60) if self.mode != 'test' else tracked_sleep(0)
                
        except KeyboardInterrupt:
           logger.info("Keyboard Interrupt Received: Stopping the program...")
            

        
            
    def place_short_calls_logic(self):
        """Place short calls as allowed by current position.
        """  
        logger.info('**** Entering short call placing logic ****')
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
        else:
            logger.info('Market is closed now.')

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
        
        shortCalls_df = self.positions.df.loc[self.positions.df['side'] == 'short'].copy()
        shortCalls_df.reset_index(drop=True, inplace=True)
        shortCalls_df.rename(columns={'cost': 'premium earned'}, inplace=True)
        shortCalls_df.rename(columns={'current value': 'residual value'}, inplace=True)
        shortCalls_df['premium earned'] = shortCalls_df['premium earned'] * -1
        shortCalls_df['current price'] = shortCalls_df['current price'] * -1
        shortCalls_df['residual value'] = shortCalls_df['residual value'] * -1
        shortCalls_df['cum. cost'] = shortCalls_df['cum. cost'] * -1
        print(shortCalls_df)
        
        if is_market_open_now() or self.mode == 'test':
            for option in shortCalls:
                if option.symbol in self.symbol_list:
                    self.manage_short_call(option) 
        else:
            logger.info('Market is closed now.')
        

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
        if  quantity <= 0 and self.mode != 'test':
            logger.info(f'[{symbol}] Max covered call limit reached. No order placed.')
            return None
    
        # Calculate expiration date
        exp_dt = dt.datetime.now().date() + dt.timedelta(days=dte) 
        exp = exp_dt.strftime('%Y-%m-%d')

        # Define profit floor and ceiling
        delta_min = 0.05
        delta_max = self.delta if self.delta > delta_min+0.05 else delta_min+0.05
        logger.info(f'[{symbol}] Looking for calls with delta between {delta_min} and {delta_max}, expiring on {exp}')

        # Find potential options
        try: 
            matchingOptions = find_options_by_delta(symbol, exp, 'call', delta_min, delta_max)
        except EmptyListError as e:
            logger.error(f"[{symbol}] No option found matching the given delta range: {e}")
            return None

        # Print potential options
        matchingOptions_df = create_dataframe_from_option_list(matchingOptions)

        # Add a column to show potential credit earned if filled.
        for index, row in matchingOptions_df.iterrows():
            matchingOptions_df.at[index, 'credit estimate'] = 100*row['current price']
            
        # Print potential options
        logger.info(f'[{symbol}] Found these options candidates to sell:')
        print(matchingOptions_df)  

        # Select option based on risk level
        if self.risk_level == 'low':
            selectedOption = matchingOptions[0]
        elif self.risk_level == 'medium':
            mid_index = len(matchingOptions) // 2
            selectedOption = matchingOptions[mid_index]
        elif self.risk_level == 'high':
            selectedOption = matchingOptions[-1]

        logger.info(f'[{symbol}] Selected option [{matchingOptions.index(selectedOption)}].')

        # Check if the order already exists in currrent open orders
        logger.info(f'[{symbol}] Checking if this option is already in open orders')
        if is_option_in_open_orders(selectedOption):
            logger.info(f'[{symbol}] This order already exists in current open orders. Order not placed.')
            return None


        # Calculate limit price
        limit_price = selectedOption.get_limit_price(price_ratio, update=True)
        logger.info(f'[{symbol}] Attempt to place a STO order:')
        logger.info(f'[{symbol}] exp: {selectedOption.exp}, strike: {selectedOption.strike}')
        logger.info(f'[{symbol}] credit: ${round(limit_price*100, 2)}.')
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
        
        if self.mode != 'test' and order_rh.status_code >= 300 or order_rh.status_code < 200:
             logger.info(f'[{symbol}] Failed to place order with status code {order_rh.status_code}.')
#             logger.info(f'{symbol}] Reason: {order_rh.json()['detail']}')
             return None
        else:
            logger.info(f'[{symbol}] Succesfully placed order with status code {order_rh.status_code}. Waiting for order to be filled...')
            logger.info('Sending email notification.')
            body = f"Succesfully placed STO for {symbol} with \
                exp: {selectedOption.exp}, strike: {selectedOption.strike}, credit: ${round(limit_price*100, 2)}"
            send_email_notification(subject=f"[{symbol}] STO Order Placed", body=body)
             
        return order_rh

    def manage_short_call(self, option):
        status = None
        logger.info(f'** Managing short call of symbol: {option.symbol}, exp: {option.exp}, strike: {option.strike} **')

        # Check if the short call exists in open positions
        option = self.positions.find_and_update_option(option)
        if option == None:
            body = f'[{option.symbol}] The short option to close is not open in your account. Option not closed.'
            logger.critical(body)
            send_email_notification(subject=f"Error Received", body=body)
            return None
            
        # Check if the short call is in open orders
        if is_option_in_open_orders(option):
            logger.info(f'[{option.symbol}] The order for this short call is queuing in current open orders. Wait till it is filled.')
            return None
        
        cost = option.cost
        price = option.get_mark_price() * option.get_position_type()
        quantity = abs(option.quantity)
        total_return = price * 100 * quantity - cost
        return_rate = total_return/abs(cost)       
        return_pcnt = round(return_rate * 100, 2)
        dte = (option.get_exp_dt().date() - dt.datetime.now().date()).days
        strike = option.strike
        stockPrice = float(rh.stocks.get_latest_price(option.symbol)[0])
        logger.info(f'[{option.symbol}] The short call has {dte} days till expiration')
        logger.info(f'[{option.symbol}] Stock price: {stockPrice} vs strike price: {strike}.')
        logger.info(f'[{option.symbol}] Return percentage now is {return_pcnt}%')

        # Managing logic
        if strike < stockPrice:
            logger.info(f'[{option.symbol}] This call is currently in the money!')
            if dte <= 1 and strike < 0.95*stockPrice:
                logger.info(f'[Action] Rolling this call to prevent assignment since call deep ITM and dte = {dte}.')
                option_to_roll = option.find_option_to_rollup_with_credit(dte_delta=7, risk_level=self.risk_level)
                status = None if option_to_roll == None else self.roll_option_ioc(option, option_to_roll, 'short', quantity)
            elif dte == 0 and strike >= 0.95*stockPrice:
                logger.info(f'[Action] Rolling this call to prevent assignment since call ITM and it expires today.')
                option_to_roll = option.find_option_to_rollup_with_credit(dte_delta=7, risk_level=self.risk_level)
                status = None if option_to_roll == None else self.roll_option_ioc(option, option_to_roll, 'short', quantity)
            else:
                logger.info(f'[Action] Too early for action. Do nothing.\n')
        else :
            if return_rate > 0.95 or abs(price) <= 0.015 or self.mode == 'test':
                logger.info(f'[Action] Rolling this call to start a new cc cycle since call gained >95% return. ')
                option_to_roll = option.find_option_to_roll_by_delta(dte_delta=7, risk_level=self.risk_level, delta=self.delta)
                status = None if option_to_roll == None else self.roll_option_ioc(option, option_to_roll, 'short', quantity)
            else:
                logger.info(f'[Action] Too early for action. Do nothing.\n')
        return status

    def roll_option_ioc(self, old_option, new_option, position_type, quantity=1):
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
        # Check if the old option is in position
        optionPositions = OptionPosition()
        old_option = optionPositions.find_and_update_option(old_option)
        if old_option == None:
            logger.info(f'[{old_option.symbol}] Option to roll is not in position.')
            return None

        # Check if the underlying stock is the same
        if old_option.symbol != new_option.symbol:
            logger.info(f"[{old_option.symbol}] The two options are not of the same underlying.")
            return None

        # Check if the option type is the same
        if old_option.type != new_option.type:
            logger.info(f"[{old_option.symbol}] The two options are not of the same type. Need to be the same type for rolling.")
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
            print(f"[{old_option.symbol}] Invalid position type. Position type should be either long or short")
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

        adjusted_price = round(abs(price)-0.01,2)  # Lower price by 1 cent to increase chances of fill.
        logger.info(f'[{old_option.symbol}] Attempt to place an order to roll:')
        logger.info(f'[{old_option.symbol}] from exp: {old_option.exp}, strike: {old_option.strike}')
        logger.info(f'[{old_option.symbol}] to   exp: {new_option.exp}, strike: {new_option.strike}')
        logger.info(f'[{old_option.symbol}] quantity: {quantity}')
        logger.info(f'[{old_option.symbol}] with credit: ${round(adjusted_price*100,2)}*{quantity}=${round(adjusted_price*100,2)*quantity}.')
        spread = [leg1,leg2]
        order_rh = rh.orders.order_option_spread(debitOrCredit, adjusted_price, new_option.symbol, quantity, spread, jsonify=False)
        if order_rh.status_code >= 300 or order_rh.status_code < 200:
            logger.info(f'[{old_option.symbol}] Failed to place order with status code {order_rh.status_code}.')
            #logger.info(f'[{self.symbol}] Reason: {order_rh.json()['detail']}')
            return None
        else:
            logger.info(f'[{old_option.symbol}] Succesfully placed order with status code {order_rh.status_code}. Waiting for order to be filled...')
            logger.info('Sending email notification.')
            body = f"Succesfully placed roll order for {old_option.symbol}:\n \
                from exp: {old_option.exp}, strike: {old_option.strike} \n\
                to   exp: {new_option.exp}, strike: {new_option.strike} \n \
                with credit: ${round(adjusted_price*100,2)}*{quantity}=${round(adjusted_price*100,2)*quantity}"
            send_email_notification(subject=f"[{old_option.symbol}] Roll Order Placed", body= body)
            
        # Cancel order after waiting for 2 min 
        minutes = 2
        logger.info(f'[{old_option.symbol}] Wait for {minutes} min for the order to be filled.')
        custom_sleep_with_progress(minutes*60) if self.mode != 'test' else time.sleep(0)
        pendingOrders = rh.orders.get_all_open_option_orders()
        for pendingOrder in pendingOrders:
            if order_rh.json()['id'] == pendingOrder['id']:
                rh.orders.cancel_option_order(pendingOrder['id'])
                logger.info(f"[{old_option.symbol}] Order cancelled since it is not filled after 2 min.")
                order_rh = None
        
        if order_rh:
            logger.info(f'[{old_option.symbol}] Order filled!')
            
        return order_rh