import robin_stocks.robinhood as rh
import datetime as dt
import config


class EmptyListError(Exception):
    """Exception raised for errors in the input list being empty."""
    def __init__(self, message="List is empty"):
        self.message = message
        super().__init__(self.message)

def login(days):
    time_logged_in = 60*60*24*days
    rh.authentication.login(username=config.USERNAME,
                            password=config.PASSWORD,
                            expiresIn=time_logged_in,
                            scope='internal',
                            by_sms=True,
                            store_session=True)
    profile = rh.profiles.load_user_profile()
    print('-----Logged in to account belong to:', profile['first_name'], profile['last_name'], '-----')

def logout():
    rh.authentication.logout()

def is_market_open_on_date(date_dt):
    date = date_dt.strftime('%Y-%m-%d')
    marketHour_rh = rh.markets.get_market_hours('XNYS', date)
    return marketHour_rh['is_open']

def is_market_open_now():
    today_date_dt = dt.datetime.today().date()
    if not is_market_open_on_date(today_date_dt):
        return False
    
    time_now = dt.datetime.now().time()
    market_open = dt.time(6,30,0) # 6:30AM PST
    market_close = dt.time(12,55,0) # 12:55PM PST

    return time_now > market_open and time_now < market_close

def is_us_market_holiday(date):
    # List of recognized US market holidays
    us_market_holidays = [
        dt.datetime(date.year, 1, 1).date(),
        # Martin Luther King Jr. Day - Third Monday in January
        dt.datetime(date.year, 1, 15).date() if date.year == 2024 else None,  # Adjust for the current year
        # Presidents' Day - Third Monday in February
        dt.datetime(date.year, 2, 19).date() if date.year == 2024 else None,  # Adjust for the current year
        # Good Friday - Friday before Easter Sunday (not a federal holiday, but many stock exchanges close early)
        dt.datetime(date.year, 3, 29).date() if date.year == 2024 else None,  # Adjust for the current year
        # Memorial Day - Last Monday in May
        dt.datetime(date.year, 5, 27).date() if date.year == 2024 else None,  # Adjust for the current year
        # Independence Day - July 4th
        dt.datetime(date.year, 7, 4).date(),
        # Labor Day - First Monday in September
        dt.datetime(date.year, 9, 2).date() if date.year == 2024 else None,  # Adjust for the current year
        # Thanksgiving Day - Fourth Thursday in November
        dt.datetime(date.year, 11, 28).date() if date.year == 2024 else None,  # Adjust for the current year
        # Christmas Day - December 25th
        dt.datetime(date.year, 12, 25).date()
    ]
    return date in us_market_holidays

def print_with_time(*args, **kwargs):
    # Get the current time
    current_time = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Join all positional arguments into a single string
    message = ' '.join(map(str, args))
    
    # Print the message with the current time, passing all keyword arguments to print
    print(f"{current_time} - {message}", **kwargs)

def get_2nd_next_friday():
    # Get today's date
    today = dt.datetime.today().date()

    # Find the next Friday
    days_ahead = 4 - today.weekday()  # weekday() returns 0 for Monday, ..., 6 for Sunday
    if days_ahead <= 0:  # Target day already passed this week
        days_ahead += 7
    next_friday = today + dt.timedelta(days=days_ahead)

    # Find the 2nd next Friday (which is 2 weeks after the next Friday)
    second_next_friday = next_friday + dt.timedelta(weeks=1)

    return second_next_friday

