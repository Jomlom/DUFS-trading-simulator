from datamodel import *
from collections import deque
import numpy as np

class Trader:

    POSITION_LIMIT = 40
    WINDOW = 50
    ENTRY_STD_MULTIPLIER = 1.5
    MAX_UNITS_PER_TICK = 3
    COOLDOWN_TICKS = 3

    PAIRS = [
        ("ETF1", "bond2"),
    ]

    def __init__(self):
        self.highest_bids = {}
        self.lowest_asks = {}
        self.spread_history = {}
        self.positions = {}
        self.last_trade_tick = {}
        self.current_tick = 0

    def run(self, state):
        orders = []
        self.current_tick += 1

        products = {p for pair in self.PAIRS for p in pair}
        for product in products:
            listings = state.orderbook.get(product)
            if not listings:
                continue
            listings = Listing(listings, product)
            if not listings.buy_orders or not listings.sell_orders:
                continue
            bid = list(listings.buy_orders.keys())[0]
            ask = list(listings.sell_orders.keys())[0]

            self.highest_bids.setdefault(product, deque(maxlen=self.WINDOW)).append(bid)
            self.lowest_asks.setdefault(product, deque(maxlen=self.WINDOW)).append(ask)

        for prodA, prodB in self.PAIRS:
            midA = self.mid(prodA)
            midB = self.mid(prodB)
            if midA is None or midB is None:
                continue

            spread = midA - midB
            self.spread_history.setdefault((prodA, prodB), deque(maxlen=self.WINDOW)).append(spread)
            history = self.spread_history[(prodA, prodB)]

            if len(history) < self.WINDOW:
                continue

            mean = np.mean(history)
            std = np.std(history) + 1e-8
            divergence = spread - mean

            if self.current_tick - self.last_trade_tick.get((prodA, prodB), -self.COOLDOWN_TICKS) < self.COOLDOWN_TICKS:
                continue

            posA = self.positions.get(prodA, 0)
            posB = self.positions.get(prodB, 0)

            bidA = self.highest_bids[prodA][-1]
            askA = self.lowest_asks[prodA][-1]
            bidB = self.highest_bids[prodB][-1]
            askB = self.lowest_asks[prodB][-1]

            units = min(self.MAX_UNITS_PER_TICK, self.POSITION_LIMIT)

            if divergence > self.ENTRY_STD_MULTIPLIER * std:
                if posA > -self.POSITION_LIMIT and posB < self.POSITION_LIMIT:
                    orders.append(Order(prodA, bidA, -units))
                    orders.append(Order(prodB, askB, units))
                    self.positions[prodA] = posA - units
                    self.positions[prodB] = posB + units
                    self.last_trade_tick[(prodA, prodB)] = self.current_tick

            elif divergence < -self.ENTRY_STD_MULTIPLIER * std:
                if posA < self.POSITION_LIMIT and posB > -self.POSITION_LIMIT:
                    orders.append(Order(prodA, askA, units))
                    orders.append(Order(prodB, bidB, -units))
                    self.positions[prodA] = posA + units
                    self.positions[prodB] = posB - units
                    self.last_trade_tick[(prodA, prodB)] = self.current_tick

        return orders

    def mid(self, product):
        bids = self.highest_bids.get(product)
        asks = self.lowest_asks.get(product)
        if not bids or not asks:
            return None
        return (bids[-1] + asks[-1]) / 2
