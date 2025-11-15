from datamodel import *


class Trader:
    def run(self, state):
        orders = []
        for product in state.products:
            listings = Listing(state.orderbook[product], product)
            highest_bid = list(listings.buy_orders.keys())[0]
            bid_quantities = list(listings.buy_orders.values())

            lowest_ask = list(listings.sell_orders.keys())[0]
            ask_quantities = list(listings.sell_orders.values())
            if best_bid > 10000:
                orders.append(Order(product, 100, -5))
            if best_ask < 10000:
                orders.append(Order(product, best_ask, 5))
        return orders
