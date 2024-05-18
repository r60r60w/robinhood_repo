import datetime as dt
import robin_stocks.robinhood as rh

class Option():
    def __init__(self, symbol, exp, strike, type):
        self.symbol = symbol 
        self.exp = exp
        self.strike = strike
        self.type = type
        self.quantity = 0
        self.cost = 0
        options_rh = rh.options.find_options_by_expiration_and_strike(self.symbol, self.exp, self.strike, self.type)
        if len(options_rh) == 0:
            self.option_rh = None
        else:
            self.option_rh = options_rh[0]

    def get_position_type(self):
        if self.quantity > 0:
            return 'long'
        elif self.quantity < 0:
            return 'short'
        else:
            return 'None'

    def get_symbol(self):
        return self.symbol

    def get_exp(self):
        return self.exp

    def get_exp_dt(self):
        return dt.datetime.strptime(self.exp, "%Y-%m-%d") 

    def get_strike(self):
        return self.strike
    
    def get_type(self):
        return self.type
    
    def get_quantity(self):
        return self.quantity

    def set_quantity(self, quantity):
        self.quantity = quantity

    def get_cost(self):
        return self.cost

    def set_cost(self, cost):
        self.cost = cost 
    
    # Robin-stock specific methods
    def get_id(self):
        return self.option_rh['id']

    def get_ask_price(self):
        return round(float(self.option_rh['ask_price']), 2)

    def get_bid_price(self):
        return round(float(self.option_rh['bid_price']), 2)

    def get_mark_price(self):
        return round(float(self.option_rh['mark_price']), 2)

    def get_delta(self):
        return round(float(self.option_rh['delta']), 4)

    def get_theta(self):
        return round(float(self.option_rh['theta']), 4)