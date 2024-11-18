import matplotlib.pyplot as plt

# Calculate the MACD
def calculate_macd(data, short_window=12, long_window=26, signal_window=9):
    data['short_ema'] = data['Close'].ewm(span=short_window, adjust=False).mean()
    data['long_ema'] = data['Close'].ewm(span=long_window, adjust=False).mean()
    data['macd'] = data['short_ema'] - data['long_ema']
    data['signal_line'] = data['macd'].ewm(span=signal_window, adjust=False).mean()
    return data

def calculate_wilders_rsi(data, window=14):
    delta = data['Close'].diff()
    
    # Get initial values for average gain and loss
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=window, min_periods=window).mean()[:window+1]
    avg_loss = loss.rolling(window=window, min_periods=window).mean()[:window+1]
    
    # Use the first window values to initialize
    avg_gain = avg_gain.iloc[-1]
    avg_loss = avg_loss.iloc[-1]
    
    # Apply Wilder's smoothing method
    for i in range(window, len(data)):
        avg_gain = (avg_gain * (window - 1) + gain.iloc[i]) / window
        avg_loss = (avg_loss * (window - 1) + loss.iloc[i]) / window
        
        rs = avg_gain / avg_loss
        data.at[data.index[i], 'rsi'] = 100 - (100 / (1 + rs))
    
    # Fill initial NaN values with 50
    data['rsi'] = data['rsi'].fillna(50)
    return data


# Function to plot closing prices, MACD, RSI, signals, and portfolio value with time ticks on x-axis
def plot_signals(df, symbol):
    plt.figure(figsize=(14, 12))

    x_axis = range(len(df))

    # Plot closing price and buy/sell signals
    plt.subplot(3, 1, 1)
    plt.plot(x_axis, df['Close'], label='Close Price')

    def plot_with_dashed_lines(signal_df, signal_type, color, marker, label):
        """Helper function to plot markers with dashed vertical lines."""
        first_marker = True  # Track if this is the first marker for the label
        for idx, row in signal_df.iterrows():
            x = df.index.get_loc(idx)  # Convert DataFrame index to x-axis position
            y = row['Close']  # Get the y-value (price)

            # Add a vertical dashed line
            plt.axvline(x=x, linestyle='--', color=color, alpha=0.6)

            # Add the marker with the label only for the first instance
            if first_marker:
                plt.scatter(x, y, marker=marker, color=color, label=label, alpha=1)
                first_marker = False
            else:
                plt.scatter(x, y, marker=marker, color=color, alpha=1)

    # Plot weak buy signals
    weak_buy_signals = df[df['buy_signal'] == 1]
    plot_with_dashed_lines(weak_buy_signals, "buy", "lightgreen", '^', "Weak Buy Signal")

    # Plot medium buy signals
    medium_buy_signals = df[df['buy_signal'] == 2]
    plot_with_dashed_lines(medium_buy_signals, "buy", "g", '^', "Medium Buy Signal")

    # Plot strong buy signals
    strong_buy_signals = df[df['buy_signal'] == 3]
    plot_with_dashed_lines(strong_buy_signals, "buy", "blue", '^', "Strong Buy Signal")

    # Plot weak sell signals
    weak_sell_signals = df[df['sell_signal'] == 1]
    plot_with_dashed_lines(weak_sell_signals, "sell", "r", 'v', "Weak Sell Signal")

    # Plot medium sell signals
    medium_sell_signals = df[df['sell_signal'] == 2]
    plot_with_dashed_lines(medium_sell_signals, "sell", "orange", 'v', "Medium Sell Signal")

    # Plot strong sell signals
    strong_sell_signals = df[df['sell_signal'] == 3]
    plot_with_dashed_lines(strong_sell_signals, "sell", "darkred", 'v', "Strong Sell Signal")

    plt.title(f'{symbol} Closing Price, MACD, RSI, Buy and Sell Signals')
    plt.legend()
    plt.grid(True)  # Add grid lines

    # Plot MACD and signal line
    plt.subplot(3, 1, 2)
    plt.plot(x_axis, df['macd'], label='MACD', color='blue')
    plt.plot(x_axis, df['signal_line'], label='Signal Line', color='red')
    plt.bar(x_axis, df['macd'] - df['signal_line'], label='MACD Histogram', color='gray')
    plt.legend()
    plt.grid(True)  # Add grid lines

    # Plot RSI
    plt.subplot(3, 1, 3)
    plt.plot(x_axis, df['rsi'], label='RSI', color='purple')
    plt.axhline(70, linestyle='--', alpha=0.5, color='red')
    plt.axhline(30, linestyle='--', alpha=0.5, color='green')
    plt.legend()
    plt.grid(True)  # Add grid lines

    # Set the x-axis ticks to correspond to certain dates
    tick_step = len(df) // 10  # Choose tick locations
    ticks = range(0, len(df), tick_step)
    tick_labels = [df.index[i].strftime('%Y-%m-%d') for i in ticks]
    plt.xticks(ticks, tick_labels, rotation=45)

    # Save the plot to a file
    plt.savefig(f'{symbol}.png')
    plt.show()

def generate_signals(data, thresholds = [15, 20, 25]):
    data['buy_signal'] = 0
    data['sell_signal'] = 0

    for i in range(1, len(data)):
        # Check for Strong Buy signal: RSI < 15
        if data['rsi'].iloc[i] < thresholds[0]:
            for j in range(i + 1, len(data)):
                if (data['macd'].iloc[j] > data['signal_line'].iloc[j] and 
                    data['macd'].iloc[j-1] <= data['signal_line'].iloc[j-1] and 
                    data['rsi'].iloc[j] < 50):
                    if data['buy_signal'].iloc[j] < 3:  # Only set if current signal is weaker
                        data.at[data.index[j], 'buy_signal'] = 3
                    break  # Break after setting the signal
        
        # Check for Medium Buy signal: RSI < 20
        elif data['rsi'].iloc[i] < thresholds[1]:
            for j in range(i + 1, len(data)):
                if (data['macd'].iloc[j] > data['signal_line'].iloc[j] and 
                    data['macd'].iloc[j-1] <= data['signal_line'].iloc[j-1] and 
                    data['rsi'].iloc[j] < 50):
                    if data['buy_signal'].iloc[j] < 2:  # Only set if current signal is weaker
                        data.at[data.index[j], 'buy_signal'] = 2
                    break  # Break after setting the signal

        # Check for Weak Buy signal: RSI < 25
        elif data['rsi'].iloc[i] < thresholds[2]:
            for j in range(i + 1, len(data)):
                if (data['macd'].iloc[j] > data['signal_line'].iloc[j] and 
                    data['macd'].iloc[j-1] <= data['signal_line'].iloc[j-1] and 
                    data['rsi'].iloc[j] < 50):
                    if data['buy_signal'].iloc[j] < 1:  # Only set if no current signal
                        data.at[data.index[j], 'buy_signal'] = 1
                    break  # Break after setting the signal

        # Check for Strong Sell signal: RSI > 85
        if data['rsi'].iloc[i] > 100-thresholds[0]:
            for j in range(i + 1, len(data)):
                if (data['macd'].iloc[j] < data['signal_line'].iloc[j] and 
                    data['macd'].iloc[j-1] >= data['signal_line'].iloc[j-1] and 
                    data['rsi'].iloc[j] > 50):
                    if data['sell_signal'].iloc[j] < 3:  # Only set if current signal is weaker
                        data.at[data.index[j], 'sell_signal'] = 3
                    break  # Break after setting the signal
        
        # Check for Medium Sell signal: RSI > 80
        elif data['rsi'].iloc[i] > 100-thresholds[1]:
            for j in range(i + 1, len(data)):
                if (data['macd'].iloc[j] < data['signal_line'].iloc[j] and 
                    data['macd'].iloc[j-1] >= data['signal_line'].iloc[j-1] and 
                    data['rsi'].iloc[j] > 50):
                    if data['sell_signal'].iloc[j] < 2:  # Only set if current signal is weaker
                        data.at[data.index[j], 'sell_signal'] = 2
                    break  # Break after setting the signal
        
        # Check for Weak Sell signal: RSI > 75
        elif data['rsi'].iloc[i] > 100-thresholds[2]:
            for j in range(i + 1, len(data)):
                if (data['macd'].iloc[j] < data['signal_line'].iloc[j] and 
                    data['macd'].iloc[j-1] >= data['signal_line'].iloc[j-1] and 
                    data['rsi'].iloc[j] > 50):
                    if data['sell_signal'].iloc[j] < 1:  # Only set if no current signal
                        data.at[data.index[j], 'sell_signal'] = 1
                    break  # Break after setting the signal

    return data

def backtest(data, initial_funds=1000):
    funds = initial_funds
    holdings = 0  # Number of shares currently held
    portfolio_value = []

    for i in range(len(data)):
        # Buy signals
        if data['buy_signal'].iloc[i] == 1:  # Weak Buy signal
            amount_to_invest = funds * 0.3  # Invest 30% of current funds
        elif data['buy_signal'].iloc[i] == 2:  # Medium Buy signal
            amount_to_invest = funds * 0.7  # Invest 70% of current funds
        elif data['buy_signal'].iloc[i] == 3:  # Strong Buy signal
            amount_to_invest = funds  # Invest 100% of current funds
        else:
            amount_to_invest = 0

        if amount_to_invest > 0:
            shares_bought = amount_to_invest / data['Close'].iloc[i]
            funds -= shares_bought * data['Close'].iloc[i]
            holdings += shares_bought

        # Sell signals
        if data['sell_signal'].iloc[i] == 1:  # Weak Sell signal
            shares_to_sell = holdings * 0.3  # Sell 30% of holdings
        elif data['sell_signal'].iloc[i] == 2:  # Medium Sell signal
            shares_to_sell = holdings * 0.7  # Sell 70% of holdings
        elif data['sell_signal'].iloc[i] == 3:  # Strong Sell signal
            shares_to_sell = holdings  # Sell 100% of holdings
        else:
            shares_to_sell = 0

        if shares_to_sell > 0:
            funds += shares_to_sell * data['Close'].iloc[i]
            holdings -= shares_to_sell

        # Calculate the current portfolio value
        current_value = funds + holdings * data['Close'].iloc[i]
        portfolio_value.append(current_value)

    data['portfolio_value'] = portfolio_value
    return data

