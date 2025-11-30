from datamodel import *
from collections import deque
import numpy as np

PAIRS = [
    ("CHADS_STOCKS", "JOHNS_STOCKS"),
    ("HATFIELD_STOCKS", "COLLINGWOOD_STOCKS")
]

HIGH_SPREAD_PRODUCTS = [
    # "CASTLE_STOCKS"
]

class Trader:
    def __init__(
        self,
        position_limit: int = 60,
        window: int = 70,
        entry_z: float = 1.2,
        exit_z: float = 0.2,
        max_units_per_tick: int = 5,
        cooldown: int = 1,
        pairs: list = None,
    ):
        self.position_limit = position_limit
        self.window = window
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.max_units_per_tick = max_units_per_tick
        self.cooldown = cooldown

        # pairs this trader will use (can be overridden by optimizer)
        self.pairs = pairs if pairs is not None else list(PAIRS)

        self.bids = {}
        self.asks = {}
        # build spread history for initial pairs
        self.spread_hist = {pair: deque(maxlen=self.window) for pair in self.pairs}
        self.positions = {}
        self.last_trade = {}
        self.tick = 0

    def run(self, state):
        orders = []
        self.tick += 1

        # update bids/asks and position containers
        for p, listings in state.orderbook.items():
            if not listings:
                continue
            L = Listing(listings, p)
            if not L.buy_orders or not L.sell_orders:
                continue
            bid = next(iter(L.buy_orders))
            ask = next(iter(L.sell_orders))
            self.bids.setdefault(p, deque(maxlen=self.window)).append(bid)
            self.asks.setdefault(p, deque(maxlen=self.window)).append(ask)
            self.positions.setdefault(p, 0)
            self.last_trade.setdefault(p, -999)

        # ensure spread history exists for any pairs (supports optimiser setting algo.pairs later)
        for pair in list(self.pairs):
            if pair not in self.spread_hist:
                self.spread_hist[pair] = deque(maxlen=self.window)

        # iterate over pairs
        for A, B in self.pairs:
            mid_A = self._mid(A)
            mid_B = self._mid(B)
            if mid_A is None or mid_B is None:
                continue

            spread = mid_A - mid_B
            self.spread_hist[(A, B)].append(spread)
            hist = np.array(list(self.spread_hist[(A, B)]))
            if len(hist) < int(self.window / 3):
                continue

            mu, sigma = hist.mean(), hist.std() + 1e-8
            z = (spread - mu) / sigma

            # cooldown check
            if (self.tick - self.last_trade.get(A, -999) < self.cooldown) or (
                self.tick - self.last_trade.get(B, -999) < self.cooldown
            ):
                continue

            pos_A = self.positions.get(A, 0)
            pos_B = self.positions.get(B, 0)

            def qty_from_z(z_val):
                scaled = int((abs(z_val) / self.entry_z) ** 1.5 * self.max_units_per_tick)
                if scaled < 1:
                    return 0
                return min(scaled, self.position_limit)

            target_qty_A = 0
            target_qty_B = 0

            if z > self.entry_z and pos_A > -self.position_limit and pos_B < self.position_limit:
                qty = qty_from_z(z)
                target_qty_A = -min(qty, self.position_limit + pos_A)
                target_qty_B = min(qty, self.position_limit - pos_B)

            elif z < -self.entry_z and pos_A < self.position_limit and pos_B > -self.position_limit:
                qty = qty_from_z(-z)
                target_qty_A = min(qty, self.position_limit - pos_A)
                target_qty_B = -min(qty, self.position_limit + pos_B)

            elif abs(z) < self.exit_z:
                if pos_A != 0:
                    target_qty_A = -np.sign(pos_A) * min(self.max_units_per_tick, abs(pos_A))
                if pos_B != 0:
                    target_qty_B = -np.sign(pos_B) * min(self.max_units_per_tick, abs(pos_B))

            # place orders
            if target_qty_A != 0:
                price = self.bids[A][-1] if target_qty_A < 0 else self.asks[A][-1]
                orders.append(Order(A, price, target_qty_A))
                self.positions[A] = self.positions.get(A, 0) + target_qty_A
                self.last_trade[A] = self.tick

            if target_qty_B != 0:
                price = self.bids[B][-1] if target_qty_B < 0 else self.asks[B][-1]
                orders.append(Order(B, price, target_qty_B))
                self.positions[B] = self.positions.get(B, 0) + target_qty_B
                self.last_trade[B] = self.tick

        # simple high-spread opportunistic market making
        for product in HIGH_SPREAD_PRODUCTS:
            listings = state.orderbook.get(product)
            if not listings:
                continue
            L = Listing(listings, product)
            if not L.buy_orders or not L.sell_orders:
                continue
            highest_bid = next(iter(L.buy_orders))
            lowest_ask = next(iter(L.sell_orders))
            bid_qty = L.buy_orders[highest_bid]
            ask_qty = L.sell_orders[lowest_ask]
            spread = lowest_ask - highest_bid
            if spread < 3:
                continue
            our_bid = min(highest_bid + 1, lowest_ask - 1)
            our_ask = max(lowest_ask - 1, highest_bid + 1)
            if bid_qty > 0:
                orders.append(Order(product, our_bid, 60))
            if ask_qty > 0:
                orders.append(Order(product, our_ask, -60))

        return orders

    def _mid(self, p):
        bids = self.bids.get(p)
        asks = self.asks.get(p)
        if not bids or not asks:
            return None
        return (bids[-1] + asks[-1]) / 2
