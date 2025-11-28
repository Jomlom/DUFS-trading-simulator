from datamodel import *

class Trader:

    HIGH_SPREAD_PRODUCTS = ["CASTLE_STOCKS"]

    SHORT_PRODUCTS = ["JOHNS_STOCKS", "CHADS_STOCKS"]

    LONG_PRODUCTS = ["HATFIELD_STOCKS", "COLLINGWOOD_STOCKS"]

    def run(self, state):

        orders = []

        for product in self.HIGH_SPREAD_PRODUCTS:
            if product not in state.orderbook:
                continue

            listings = Listing(state.orderbook[product], product)
            if not listings.buy_orders or not listings.sell_orders:
                continue

            highest_bid, lowest_ask = list(listings.buy_orders.keys())[0], list(listings.sell_orders.keys())[0]
            bid_qty, ask_qty = listings.buy_orders[highest_bid], listings.sell_orders[lowest_ask]
            spread = lowest_ask - highest_bid
            if spread < 3:
                continue

            # determine base quantity and boost based on spread
            base_qty, boost = (3, 1) if spread <= 5 else (4, 2) if spread <= 6 else (6, 3)
            our_bid = min(highest_bid + boost, lowest_ask - 1)
            our_ask = max(lowest_ask - boost, highest_bid + 1)

            if bid_qty > 0:
                orders.append(Order(product, our_bid, base_qty))
            if ask_qty > 0:
                orders.append(Order(product, our_ask, -base_qty))

        for product in self.SHORT_PRODUCTS:
            if product not in state.orderbook:
                continue
            orders.append(Order(product, list(Listing(state.orderbook[product], product).buy_orders.keys())[0], -1))

        for product in self.LONG_PRODUCTS:
            if product not in state.orderbook:
                continue
            orders.append(Order(product, list(Listing(state.orderbook[product], product).sell_orders.keys())[0], 1))


        return orders