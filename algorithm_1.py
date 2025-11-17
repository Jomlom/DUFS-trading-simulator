from datamodel import *

class Trader:
    def run(self, state):
        orders = []
        for product in state.products:
            listings = Listing(state.orderbook[product], product)
            highest_bid, lowest_ask = list(listings.buy_orders.keys())[0], list(listings.sell_orders.keys())[0]
            bid_qty, ask_qty = listings.buy_orders[highest_bid], listings.sell_orders[lowest_ask]
            spread = lowest_ask - highest_bid
            if spread < 2:
                continue
            # spread table as tuple list
            base_qty, boost = (2,1) if spread <= 3 else (3,2) if spread <= 5 else (5,3)
            our_bid, our_ask = min(highest_bid + boost, lowest_ask - 1), max(lowest_ask - boost, highest_bid + 1)
            if bid_qty > 0:
                orders.append(Order(product, our_bid, base_qty))
            if ask_qty > 0:
                orders.append(Order(product, our_ask, -base_qty))
        return orders