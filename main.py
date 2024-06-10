from datamodel import *
from dataimport import *
from Runscript import *

"""
we only trade one good in each round
initialise portfolio with 100k
    quantity = 0
    value = 100,000
    

for each timestamp,

    for each product at that time stamp,
        set the listing price, quantity, symbol

    run the trader class
    for each order:
        check that the price and direction exists:
            check that order is not greater than quantity avaliable
        
                update portfolio with outcome
"""
class Portfolio:
    def __init__(self) -> None:
        self.cash = 100000
        self.quantity = 0

portfolio = Portfolio()

filepath = "trading comp\prices_round_1_day_-1.csv"
product = "AMETHYSTS"
pos_limit = 20
df = read_file(filepath, product)
ticks = len(df)
# for each trader id in list
#from trader_id import Trader

from examplealgo import Trader

for tick in range(0, ticks):
    market_listings = extract_orders(df, tick)
    sell_orders = market_listings[0]
    buy_orders = market_listings[1]
    print(sell_orders.keys())

    algo = Trader()
    orders = algo.run(market_listings)
    # order matching
    for order in orders:
        if order.quantity < 0: # sell orders
            #match order with a buy order
            quantity = order.quantity ###################### order is not an object, figure out how to get the order's price and quantity
            for listing in buy_orders:
                print("---")
                print(listing)
                print("---")
                if listing.price > order.price:
                    fulfilled_amount = min(pos_limit - abs(portfolio.quantity), order.quantity, listing.quantity)
                    portfolio.quantity -= fulfilled_amount
                    portfolio.cash += fulfilled_amount * order.price
                    quantity += fulfilled_amount
                if listing.quantity == 0 or listing.price < order.price:
                    break
        elif order.quantity > 0: # buy orders
            pass
    # portfolio tracking
    break

print(portfolio.quantity)
    