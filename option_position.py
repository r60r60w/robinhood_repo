import datetime as dt
import robin_stocks.robinhood as rh
import option as op

class OptionPosition():
    def __init__(self):
        self.optionPositions = []
        optionPositions_rh = rh.options.get_open_option_positions()
        for position in optionPositions_rh:
            option_rh = rh.options.get_option_instrument_data_by_id(position['option_id'])
            current_price_tmp = rh.options.get_option_market_data_by_id(position['option_id'], 'mark_price')
            option = op.Option(option_rh['chain_symbol'], option_rh['expiration_date'], float(option_rh['strike_price']), option_rh['type'])
            quantity = float(position['quantity'])
            cost = float(position['average_price'])
            option.set_cost(cost)
            if position['type'] == 'short':
                option.set_quantity(-1*quantity)
            elif position['type'] == 'long':
                option.set_quantity(quantity)
            self.optionPositions.append(option)

    def print(self):
        # Print header
        print('---- Current Option Positions ----')

        # Iterate over each option position
        for position in self.optionPositions:
            # Retrieve current market price
            current_price = position.get_mark_price()
            current_price = -1*current_price if position.get_position_type() == "short" else current_price
            # Calculate total return
            cost = position.get_cost() 
            total_return = current_price * 100 - cost

            # Print option position details
            print(position.get_id())
            print('symbol:', position.get_symbol(),
                  ' type:', position.get_position_type(), position.get_type(),
                  ' exp:', position.get_exp(),
                  ' strike price:', position.get_strike(),
                  ' quantity:', position.get_quantity(),
                  ' current price:', round(current_price, 2),
                  ' current value:', round(current_price * 100, 2),
                  ' delta:', position.get_delta(),
                  ' theta:', position.get_theta(),
                  ' average cost:', round(cost, 2),
                  ' total return:', round(total_return, 2))
