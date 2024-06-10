from datamodel import *
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
        self.value = 100000
        self.quantity = 0

portfolio = Portfolio()
ticks = []



for tick in ticks:
    listing = Listing()
    listing.price = tick[0] # example
    listing.quantity = tick[1]





