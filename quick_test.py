#%%
import datetime as dt
import time
import robin_stocks.robinhood as rh
from jh_options import *
from jh_utilities import *
from jh_optionTrader import *
from technical_indicator import *
import yfinance as yf
#import yagmail

import pandas as pd
#%%
login(days=1)

#%%
optionPositions = OptionPosition()
positions = optionPositions.get_all_positions()
cost = optionPositions.calculate_option_cost(positions[6])
#%%

def process_option_orders_by_symbol(symbol):
    """Process past option orders by symbol

        Args:
            symbol (_type_): string

        Returns:
            _type_: Pandas dataframe
                    returns an dataframe with legs expanded 
        """
    all_orders_rh = rh.orders.get_all_option_orders()
    filtered_orders_rh = [item for item in all_orders_rh if item['chain_symbol'] == symbol and item['state']== 'filled']
    df = pd.DataFrame(filtered_orders_rh)
    selected_columns = ['created_at', 'direction', 'legs', 'opening_strategy', 'closing_strategy', 'form_source', 'average_net_premium_paid', 'processed_premium', 'quantity']
    df_selected = df[selected_columns]
    expand_columns = ['time', 'strategy', 'effect', 'side', 'type', 'exp', 'strike', 'quantity', 'price', 'premium']
    df_expand = pd.DataFrame(columns=expand_columns)
    for index, row in df_selected.iterrows():
        time = row['created_at']
        time_dt = datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.%fZ')
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

            new_row = {'time': time, 
                    'strategy': strategy,
                        'effect': effect, 
                        'side': side, 
                        'type': option_type, 
                        'exp': exp,
                        'strike': strike,
                        'quantity': quantity,
                        'price': option_price,
                        'premium': premium
                        }
            df_expand = pd.concat([df_expand, pd.DataFrame([new_row])], ignore_index=True)
    df_expand['running_premium'] = df_expand.iloc[::-1]['premium'].cumsum()[::-1]
    
    # Process net cost for rolls
    for index, row in df_expand.iterrows():
        if row['strategy'][:4] == 'roll' and row['strategy'][-2:] == '#0':
            next_row = df_expand.iloc[index+1]   
            df_expand.at[index, 'premium'] += next_row['premium']
            df_expand.at[index+1, 'premium'] = 0

    # Filter short calls (covered calls)
    mask = df_expand['strategy'].str.contains('short call')
    df_sc = df_expand.loc[mask]
    df_sc['running_premium']=df_sc.iloc[::-1]['premium'].cumsum()[::-1]
    
    # Filter long calls (leaps)
    mask = df_expand['strategy'].str.contains('long call')
    df_lc = df_expand.loc[mask]
    df_lc['running_premium']=df_lc.iloc[::-1]['premium'].cumsum()[::-1]
    
    return df_expand, df_sc, df_lc

#%% Export to Excel
symbol = 'META'
[df_expand, df_sc, df_lc] = process_option_orders_by_symbol(symbol)
df_expand.to_excel(f'PnL_expanded_{symbol}.xlsx', index=False)
df_sc.to_excel(f'PnL_cc_{symbol}.xlsx', index=False)
df_lc.to_excel(f'PnL_lc_{symbol}.xlsx', index=False)
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