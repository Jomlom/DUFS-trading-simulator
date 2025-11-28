from datamodel import *
from collections import deque
import numpy as np

'''
Pairs mean reversion strategy:

    monitor pairs of products

    calculate the spread: price difference between the two products

    track historical mean and std of the spread

    trade the spread when it deviates from its mean expecting reversion

    scale trades based on deviation size and unwind gradually
'''

PAIRS = [
    ("CHADS_STOCKS", "JOHNS_STOCKS"),
    ("HATFIELD_STOCKS", "COLLINGWOOD_STOCKS")
]

class Trader:

    def __init__(
            self,
            position_limit: int = 60,
            window: int = 100,
            entry_z: float = 1.5,
            exit_z: float = 0.1,
            max_units_per_tick: int = 6,
            cooldown: int = 8,
    ):

        self.position_limit = position_limit
        self.window = window
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.max_units_per_tick = max_units_per_tick
        self.cooldown = cooldown

        # bids/asks for all products
        self.bids = {}
        self.asks = {}
        # spread history for each pair
        self.spread_hist = {pair: deque(maxlen=self.window) for pair in PAIRS}
        # positions per product
        self.positions = {}
        # last trade tick per product
        self.last_trade = {}
        self.tick = 0

    def run(self, state):
        orders = []
        self.tick += 1

        # update bids and asks, and positions
        for p in state.orderbook.keys():
            listings = state.orderbook.get(p)
            if not listings:
                continue
            L = Listing(listings, p)
            if not L.buy_orders or not L.sell_orders:
                continue
            bid, ask = list(L.buy_orders.keys())[0], list(L.sell_orders.keys())[0]
            self.bids.setdefault(p, deque(maxlen=self.window)).append(bid)
            self.asks.setdefault(p, deque(maxlen=self.window)).append(ask)
            self.positions.setdefault(p, 0)
            self.last_trade.setdefault(p, -999)

        # iterate over pairs
        for A, B in PAIRS:
            mid_A = self._mid(A)
            mid_B = self._mid(B)
            if mid_A is None or mid_B is None:
                continue

            spread = (mid_A - mid_B)
            self.spread_hist[(A, B)].append(spread)
            hist = np.array(list(self.spread_hist[(A, B)]))
            if len(hist) < int(self.window / 3):
                continue

            mu, sigma = hist.mean(), hist.std() + 1e-8
            z = (spread - mu) / sigma

            # check cooldowns
            if (self.tick - self.last_trade[A] < self.cooldown) or (self.tick - self.last_trade[B] < self.cooldown):
                continue

            pos_A = self.positions[A]
            pos_B = self.positions[B]

            def qty_from_z(z_val):
                scaled = min(int((abs(z_val) / self.entry_z) ** 2.1 * self.max_units_per_tick), self.position_limit)
                return min(scaled, self.position_limit)

            target_qty_A = 0
            target_qty_B = 0

            # mean reversion: if spread > threshold, short A, long B
            if z > self.entry_z and pos_A > -self.position_limit and pos_B < self.position_limit:
                qty = qty_from_z(z)
                target_qty_A = -min(qty, self.position_limit + pos_A)
                target_qty_B = min(qty, self.position_limit - pos_B)
            elif z < -self.entry_z and pos_A < self.position_limit and pos_B > -self.position_limit:
                qty = qty_from_z(-z)
                target_qty_A = min(qty, self.position_limit - pos_A)
                target_qty_B = -min(qty, self.position_limit + pos_B)
            elif abs(z) < self.exit_z:
                # unwind gradually
                if pos_A != 0:
                    target_qty_A = -np.sign(pos_A) * min(self.max_units_per_tick, abs(pos_A))
                if pos_B != 0:
                    target_qty_B = -np.sign(pos_B) * min(self.max_units_per_tick, abs(pos_B))

            # place orders if non-zero
            if target_qty_A != 0:
                price = self.bids[A][-1] if target_qty_A < 0 else self.asks[A][-1]
                orders.append(Order(A, price, target_qty_A))
                self.positions[A] += target_qty_A
                self.last_trade[A] = self.tick

            if target_qty_B != 0:
                price = self.bids[B][-1] if target_qty_B < 0 else self.asks[B][-1]
                orders.append(Order(B, price, target_qty_B))
                self.positions[B] += target_qty_B
                self.last_trade[B] = self.tick

        return orders

    def _mid(self, p):
        bids = self.bids.get(p)
        asks = self.asks.get(p)
        if not bids or not asks:
            return None
        return (bids[-1] + asks[-1]) / 2
