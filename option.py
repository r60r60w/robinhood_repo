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
        self._bid_price = 0
        self._ask_price = 0
        self._markprice = 0
        self._delta = None
        self._theta = None
        self.id = None # To be updated by the below method
        self.update()

    def update(self):
        options_rh = rh.options.find_options_by_expiration_and_strike(self.symbol, self.exp, self.strike, self.type)
        if len(options_rh) == 0:
            option_rh = None
            return
        else:
            option_rh = options_rh[0]
        self._ask_price = round(float(option_rh['ask_price']), 2)
        self._bid_price = round(float(option_rh['bid_price']), 2)
        self._mark_price = round(float(option_rh['bid_price']), 2)
        self._delta = round(float(option_rh['delta']), 4)
        self._theta = round(float(option_rh['theta']), 4)
        self.id = option_rh['id']

    def get_position_type(self):
        if self.quantity > 0:
            return 'long'
        elif self.quantity < 0:
            return 'short'
        else:
            return 'None'

    def get_exp_dt(self):
        return dt.datetime.strptime(self.exp, "%Y-%m-%d") 

    # Robin-stock specific methods
    def get_id(self):
        return self.id

    def get_ask_price(self):
        self.update()
        return self._ask_price

    def get_bid_price(self):
        self.update()
        return self._bid_price

    def get_mark_price(self):
        self.update()
        return self._mark_price

    def get_delta(self):
        self.update()
        return self._delta

    def get_theta(self):
        self.update()
        return self._theta


class OptionPosition():
    def __init__(self):
        self.optionPositions = []
        optionPositions_rh = rh.options.get_open_option_positions()
        for position in optionPositions_rh:
            option_rh = rh.options.get_option_instrument_data_by_id(position['option_id'])
            option = Option(option_rh['chain_symbol'], option_rh['expiration_date'], float(option_rh['strike_price']), option_rh['type'])
            quantity = float(position['quantity'])
            cost = float(position['average_price'])
            option.cost = cost
            if position['type'] == 'short':
                option.quantity = -1*quantity
            elif position['type'] == 'long':
                option.quantity = quantity
            self.optionPositions.append(option)

    def print_all_positions(self):
        # Print header
        print('---- Current Option Positions ----')

        # Iterate over each option position
        for position in self.optionPositions:
            # Retrieve current market price
            current_price = position.get_mark_price()
            current_price = -1*current_price if position.get_position_type() == "short" else current_price
            # Calculate total return
            cost = position.cost 
            total_return = current_price * 100 - cost

            # Print option position details
            print(position.get_id())
            print('symbol:', position.symbol,
                  ' type:', position.get_position_type(), position.type,
                  ' exp:', position.exp,
                  ' strike price:', position.strike,
                  ' quantity:', position.quantity,
                  ' current price:', round(current_price, 2),
                  ' current value:', round(current_price * 100, 2),
                  ' delta:', position.get_delta(),
                  ' theta:', position.get_theta(),
                  ' average cost:', round(cost, 2),
                  ' total return:', round(total_return, 2))

    # Check if there are short call option of the given symbol in current postions
    def is_short_call_in_position(self, symbol):
        for position in self.optionPositions:
            type = position.type
            positionType = position.get_position_type()
            if  position.symbol == symbol and type == 'call' and positionType == 'short':
                return True
        
        return False

    # Check if there are long call option of the given symbol in current postions
    def is_long_call_in_position(self, symbol):
        for position in self.optionPositions:
            type = position.type
            positionType = position.get_position_type()
            if  position.symbol == symbol and type == 'call' and positionType == 'long':
                return True
        
        return False
   
    # Count how many long call positions 
    def long_call_quantity(self, symbol):
        for position in self.optionPositions:
            count = 0
            type = position.type
            positionType = position.get_position_type()
            if  position.symbol == symbol and type == 'call' and positionType == 'long':
                count += abs(position.quantity)
        
        return count

        