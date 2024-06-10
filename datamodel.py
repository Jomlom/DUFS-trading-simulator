#position limit needs adding

class Listing: # potentially separate buyprice and sell price
    def __init__(self, market_listings, product) -> None:
        self.buy_orders = market_listings[0] #dict of {price: quantity} [0] is lowest price
        self.sell_orders = market_listings[1] #dict of {price: quantity} [0] is highest price
        self.product = product
        
class Order:
    def __init__(self, symbol, price, quantity) -> None:
        self.symbol = symbol
        self.quantity = quantity
        self.price = price

class Market:
    def __init__(self, traderData, tick, listings, order_depths, own_trades, market_trades, position, observations):
        self.tick = tick
        self.listings = listings
