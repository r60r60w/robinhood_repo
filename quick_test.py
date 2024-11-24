#%%
import datetime as dt
import time
import robin_stocks.robinhood as rh
from jh_options import *
from jh_utilities import *
from jh_optionTrader import *
from technical_indicator import *
import yfinance as yf
import yagmail

import pandas as pd

login(1)
positions = OptionPosition()
#%%
symbol = 'TSLA'
stock = yf.Ticker(symbol)

df = stock.history(period='5d', interval='5m')
stock.history()

# Apply the MACD calculation
df = calculate_macd(df, short_window=12, long_window=26, signal_window=9)
df = calculate_wilders_rsi(df, window=14)
df = generate_signals(df, thresholds=[15,20,30])
plot_signals(df, symbol)
#exit()

#%%
#optionPositions = OptionPosition()
#positions = optionPositions.get_all_positions()
#cost = optionPositions.calculate_option_cost(positions[6])
#%%
import threading
import time
import random  # Simulate live price feed

class TradingSignal:
    """Encapsulates trading signals and synchronization."""
    def __init__(self):
        self.signal_event = threading.Event()  # Event to notify the main thread
        self.signal = None  # Current trading signal (buy/sell/hold)
        self.signal_lock = threading.Lock()  # Lock to protect signal access

    def set_signal(self, signal):
        """Set a new trading signal and notify."""
        with self.signal_lock:
            self.signal = signal
            print(f"WorkerThread: Generated signal = {signal}. Notifying main thread.")
            self.signal_event.set()  # Notify the main thread

    def get_signal(self):
        """Retrieve the current signal."""
        with self.signal_lock:
            return self.signal

    def reset_event(self):
        """Reset the event after the signal is processed."""
        self.signal_event.clear()

# Worker thread that processes stock prices
class StockAlgorithmThread(threading.Thread):
    def __init__(self, trading_signal):
        super().__init__()
        self.trading_signal = trading_signal  # Shared TradingSignal object
        self.running = True  # Control thread execution

    def stop(self):
        """Stop the thread gracefully."""
        self.running = False

    def run(self):
        print("WorkerThread: Starting stock price analysis...")
        while self.running:
            time.sleep(1)  # Simulate live price feed delay
            live_price = random.uniform(100, 200)  # Simulate live stock price
            print(f"WorkerThread: Live price = {live_price}")

            # Generate a buy/sell/hold signal based on some conditions
            if live_price < 120:
                self.trading_signal.set_signal("buy")
            elif live_price > 180:
                self.trading_signal.set_signal("sell")
            else:
                self.trading_signal.set_signal("hold")

# Main trading logic
def main():
    trading_signal = TradingSignal()  # Shared trading signal object

    # Create and start the worker thread
    stock_thread = StockAlgorithmThread(trading_signal)
    stock_thread.start()

    try:
        while True:
            # Check if a signal is set, without blocking
            if trading_signal.signal_event.is_set():
                signal = trading_signal.get_signal()

                # Act on the received signal
                if signal == "buy":
                    print("MainThread: Placing a BUY order.")
                elif signal == "sell":
                    print("MainThread: Placing a SELL order.")
                elif signal == "hold":
                    print("MainThread: Holding position.")

                # Reset the event after processing
                trading_signal.reset_event()

            # Perform other tasks in the meantime
            print("MainThread: Performing background tasks...")
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("MainThread: Stopping the program...")
        stock_thread.stop()
        stock_thread.join()
        print("MainThread: Program stopped.")

if __name__ == "__main__":
    main()



#%%
def send_email_notification(to_address, subject, body, attachment_path=None):
    # Email settings
    email_address = 'r60r60w@gmail.com'
    app_password = 'sffl xnzq nekx jvio'
    # Initialize yagmail
    yag = yagmail.SMTP(email_address, app_password)
    # Prepare email contents
    contents = [body]
    if attachment_path:
        contents.append(attachment_path)

    # Send the email
    try:
        yag.send(to=to_address, subject=subject, contents=contents)
        print_with_time('Email sent successfully', file="log.txt")
    except Exception as e:
        print_with_time(f'Failed to send email: {e}', file="log.txt")



def monitor_signals(watch_list = ['NVDA', 'AAPL', 'META', 'TSLA'], test_mode = False):
    email_list = ['jhuang1869@gmail.com'] if test_mode else ['jhuang1869@gmail.com', 'junnie.qiu@gmail.com']

    for symbol in watch_list:
        stock = yf.Ticker(symbol)
#        df = yf.download(symbol, period='5d', interval='5m')
        df = stock.history(period='5d', interval='5m')

        # Apply the MACD calculation
        df = calculate_macd(df, short_window=12, long_window=26, signal_window=9)
        df = calculate_wilders_rsi(df, window=14)
        df = generate_signals(df)
        plot_signals(df, symbol)
        price_now = df.iloc[-1]['Close']
        
        if df.iloc[-1]['buy_signal'] == 1 or test_mode:
            print_with_time(f"Weak buy signal detected for {symbol}, sending notification emails.", file="log.txt")
            for address in email_list:
                subject = f"{symbol} Weak Buy Signal"
                send_email_notification(to_address=address, 
                                        subject=f"{symbol}: Weak Buy Signal", 
                                        body=f"Weak buy signal detected for {symbol} at ${price_now}", 
                                        attachment_path=f'/mnt/c/Users/Jason/robinhood_repo/{symbol}.png')
        elif df.iloc[-1]['buy_signal'] == 2:
            print_with_time(f"Medium buy signal detected for {symbol}, sending notification emails.", file="log.txt")
            for address in email_list:
                send_email_notification(to_address=address, 
                                        subject=f"{symbol}: Medium Buy Signal", 
                                        body=f"Medium buy signal detected for {symbol} at ${price_now}", 
                                        attachment_path=f'/mnt/c/Users/Jason/robinhood_repo/{symbol}.png')   
        elif df.iloc[-1]['buy_signal'] == 3:
            print_with_time(f"Strong buy signal detected for {symbol}, sending notification emails.", file="log.txt")
            for address in email_list:
                send_email_notification(to_address=address, 
                                        subject=f"{symbol}: Strong Buy Signal", 
                                        body=f"Strong buy signal detected for {symbol} at ${price_now}", 
                                        attachment_path=f'/mnt/c/Users/Jason/robinhood_repo/{symbol}.png')
        else:
            print_with_time(f"No buy signal detected for {symbol}.", file="log.txt")
            pass
        
        if df.iloc[-1]['sell_signal'] == 1:
            print_with_time(f"Weak sell signal detected for {symbol}, sending notification emails.", file="log.txt")
            for address in email_list:
                send_email_notification(to_address=address, 
                                        subject=f"{symbol}: Weak Sell Signal", 
                                        body=f"Weak sell signal detected for {symbol} at ${price_now}", 
                                        attachment_path=f'/mnt/c/Users/Jason/robinhood_repo/{symbol}.png')
        elif df.iloc[-1]['sell_signal'] == 2:
            print_with_time(f"Medium sell signal detected for {symbol}, sending notification emails.", file="log.txt")
            for address in email_list:
                send_email_notification(to_address=address, 
                                        subject=f"{symbol}: Medium Sell Signal", 
                                        body=f"Medium sell signal detected for {symbol} at ${price_now}",
                                        attachment_path=f'/mnt/c/Users/Jason/robinhood_repo/{symbol}.png')   
        elif df.iloc[-1]['sell_signal'] == 3:
            print_with_time(f"Strong sell signal detected for {symbol}, sending notification emails.", file="log.txt")
            for address in email_list:
                send_email_notification(to_address=address, 
                                        subject=f"{symbol}: Strong Sell Signal", 
                                        body=f"Strong sell signal detected for {symbol} at ${price_now}", 
                                        attachment_path=f'/mnt/c/Users/Jason/robinhood_repo/{symbol}.png')
        else:
            print_with_time(f"No sell signal detected for {symbol}.", file="log.txt")
            pass

i=0
test_mode = False
while False:
    if is_market_open_now() or test_mode:
        monitor_signals(test_mode=test_mode)
    else:
        print_with_time("Market closed now.", file="log.txt")
    
    if test_mode: 
        exit()
    time.sleep(60)
    
symbol = 'NVDA'
stock = yf.Ticker(symbol)
#        df = yf.download(symbol, period='5d', interval='5m')
df = stock.history(period='5d', interval='5m')

# Apply the MACD calculation
df = calculate_macd(df, short_window=12, long_window=26, signal_window=9)
df = calculate_wilders_rsi(df, window=14)
df = generate_signals(df)
plot_signals(df, symbol)

'''
            period : str
                Valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
                Either Use period parameter or use start and end
            interval : str
                Valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo
                Intraday data cannot extend last 60 days
'''