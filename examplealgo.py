from datamodel import *

class Trader:
    def run(self, market_listings):
        orders = []
        product = Listing(market_listings, "Amethysts")
        bids, bid_quantities = list(product.buy_orders.items())
        asks, ask_quantities = list(product.sell_orders.items())

        print(product.buy_orders.items())
        #error with getting the asks
        price = 100
        if bids[0] > price:
            highest_bid = asks[0]
            orders.append(Order("Amethysts", highest_bid, -5))
        elif asks[0] < price:
            lowest_ask = bids[0]
            orders.append(Order("Amethysts", lowest_ask, 5))
        return orders