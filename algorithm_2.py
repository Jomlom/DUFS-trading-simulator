from datamodel import *
import seaborn as sn
from matplotlib.pyplot import figure

class Trader:
    def run(self, state):

        # # store mid-prices for heatmap at end
        # if not hasattr(self, "mid_history"):
        #     self.mid_history = {}
        #
        # for product in state.products:
        #     listings = Listing(state.orderbook[product], product)
        #
        #     if listings.buy_orders and listings.sell_orders:
        #         best_bid = next(iter(listings.buy_orders))
        #         best_ask = next(iter(listings.sell_orders))
        #         mid = (best_bid + best_ask)/2
        #
        #         self.mid_history.setdefault(product, []).append(mid)

        orders = []
        for product in state.products:
            listings = Listing(state.orderbook[product], product)
            if not listings.buy_orders or not listings.sell_orders:
                continue

            highest_bid = list(listings.buy_orders.keys())[0]
            lowest_ask = list(listings.sell_orders.keys())[0]
            bid_qty = listings.buy_orders[highest_bid]
            ask_qty = listings.sell_orders[lowest_ask]

            spread = lowest_ask - highest_bid
            if spread < 2:
                continue

            base_qty, boost = (2,1) if spread<=3 else (3,2) if spread<=5 else (5,3)
            our_bid = min(highest_bid + boost, lowest_ask - 1)
            our_ask = max(lowest_ask - boost, highest_bid + 1)

            if bid_qty > 0:
                orders.append(Order(product, our_bid, base_qty))
            if ask_qty > 0:
                orders.append(Order(product, our_ask, -base_qty))

        return orders
