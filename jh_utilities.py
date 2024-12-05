import robin_stocks.robinhood as rh
import datetime as dt
import config
import logging
import yagmail
import time
import json

from tqdm import tqdm

with open('settings.json', 'r') as f:
    settings = json.load(f)

# Configure logging settings for console output
logging.basicConfig(
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
    level=logging.INFO
)

# Define a function to get a logger
def get_logger(name: str, log_to_file: bool = False, file_name: str = "app.log") -> logging.Logger:
    """Get a logger with the specified name. Optionally log to a file."""
    logger = logging.getLogger(name)
    
    # Ensuring that logger only has handlers set once to prevent duplicate logs
    if not logger.handlers:
        # Add a file handler if log_to_file is True
        if log_to_file:
            file_handler = logging.FileHandler(file_name)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(logging.Formatter(
                '[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s'
            ))
            logger.addHandler(file_handler)
    
    return logger

logger = get_logger(__name__, log_to_file=True, file_name="my_log_file.log")

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
                            store_session=False)
    profile = rh.profiles.load_user_profile()
    logger.info(f'******** Successfully logged in to Robinhood account for {profile['first_name']} {profile['last_name']} ********')

def logout():
    rh.authentication.logout()

def is_market_open_on_date(date_dt):
    date = date_dt.strftime('%Y-%m-%d')
    marketHour_rh = rh.markets.get_market_hours('XNYS', date)
    if not marketHour_rh:
        return False 
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

def print_with_time(*args, file=None, **kwargs):
    # Get the current time
    current_time = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Join all positional arguments into a single string
    message = ' '.join(map(str, args))
    
    # Construct the final message with the current time
    final_message = f"{current_time} - {message}"
    
    # Print the message with the current time, passing all keyword arguments to print
    print(final_message, **kwargs)
    
    # If a file name is provided, append the message to the file
    if file:
        with open(file, 'a') as f:
            f.write(final_message + '\n')

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

def send_email_notification(subject, body, to_address=settings['email_address'], attachment_path=None):
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

def tracked_sleep(seconds):
    start = time.time()
    while time.time() - start < seconds:
        print(f"{int(time.time() - start)} seconds elapsed", end="\r", flush=True)
        time.sleep(min(1, seconds - (time.time() - start)))
        

def precise_sleep(sleep_time):
    """
    Sleeps for the specified amount of time with higher precision.
    
    Args:
        sleep_time (float): The time to sleep, in seconds.
    """
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < sleep_time:
        pass  # Busy wait for the duration


def custom_sleep_with_progress(seconds):
    print(f"Sleeping for {seconds} seconds...")
    for _ in tqdm(range(seconds), desc="Sleeping", unit="s", ncols=80):
        time.sleep(1)
