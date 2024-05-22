import robin_stocks.robinhood as rh
import robin_stocks.robinhood as rh
import datetime as dt
import config

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

def is_market_open():
    today_date = dt.datetime.today().date()
    if today_date.weekday() >=5 or is_us_market_holiday(today_date): # See if today is weekend or US holiday
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
