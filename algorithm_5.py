from datamodel import *
from collections import deque
import numpy as np

# pair configuration different thresholds
PAIR_CONFIG = {
    ("CHADS_STOCKS", "JOHNS_STOCKS"): {
        "entry_z": 1.2,
        "exit_z": 0.20,
    },
    ("HATFIELD_STOCKS", "COLLINGWOOD_STOCKS"): {
        "entry_z": 1.5,
        "exit_z": 0.15,
    },
}

HIGH_SPREAD_PRODUCTS = [
    "CASTLE_STOCKS"
]

class Trader:

    def __init__(
            self,
            position_limit: int = 60,
            window: int = 70,
            max_units_per_tick: int = 5,
            cooldown: int = 1,
    ):
        self.position_limit = position_limit
        self.window = window
        self.max_units_per_tick = max_units_per_tick
        self.cooldown = cooldown

        # orderbook data
        self.bids = {}
        self.asks = {}

        # spread history for each pair
        self.spread_hist = {pair: deque(maxlen=self.window) for pair in PAIR_CONFIG.keys()}

        # positions and trade state
        self.positions = {}
        self.last_trade = {}
        self.tick = 0


    def run(self, state):
        orders = []
        self.tick += 1

        # update midprice history + positions
        for p in state.orderbook.keys():
            listings = state.orderbook.get(p)
            if not listings:
                continue

            L = Listing(listings, p)
            if not L.buy_orders or not L.sell_orders:
                continue

            bid = list(L.buy_orders.keys())[0]
            ask = list(L.sell_orders.keys())[0]

            self.bids.setdefault(p, deque(maxlen=self.window)).append(bid)
            self.asks.setdefault(p, deque(maxlen=self.window)).append(ask)
            self.positions.setdefault(p, 0)
            self.last_trade.setdefault(p, -999)

        # trade each pair independently
        for pair, cfg in PAIR_CONFIG.items():
            A, B = pair
            entry_z = cfg["entry_z"]
            exit_z = cfg["exit_z"]

            mid_A = self._mid(A)
            mid_B = self._mid(B)
            if mid_A is None or mid_B is None:
                continue

            spread = mid_A - mid_B
            self.spread_hist[pair].append(spread)

            hist = np.array(self.spread_hist[pair])
            if len(hist) < self.window // 3:
                continue

            mu = hist.mean()
            sigma = hist.std() + 1e-8
            z = (spread - mu) / sigma

            # cooldown check
            if (self.tick - self.last_trade[A] < self.cooldown) or \
               (self.tick - self.last_trade[B] < self.cooldown):
                continue

            pos_A = self.positions[A]
            pos_B = self.positions[B]

            def qty_from_z(z_val):
                scaled = min(int((abs(z_val) / entry_z) ** 1.5 * self.max_units_per_tick),
                             self.position_limit)
                return scaled

            target_A = 0
            target_B = 0

            # enter trades
            if z > entry_z:  # A expensive, B cheap → short A, long B
                qty = qty_from_z(z)
                target_A = -min(qty, self.position_limit + pos_A)
                target_B =  min(qty, self.position_limit - pos_B)

            elif z < -entry_z:  # A cheap, B expensive → long A, short B
                qty = qty_from_z(-z)
                target_A =  min(qty, self.position_limit - pos_A)
                target_B = -min(qty, self.position_limit + pos_B)

            # exit trades
            elif abs(z) < exit_z:
                if pos_A != 0:
                    target_A = -np.sign(pos_A) * min(self.max_units_per_tick, abs(pos_A))
                if pos_B != 0:
                    target_B = -np.sign(pos_B) * min(self.max_units_per_tick, abs(pos_B))

            # place orders
            if target_A != 0:
                price = self.bids[A][-1] if target_A < 0 else self.asks[A][-1]
                orders.append(Order(A, price, target_A))
                self.positions[A] += target_A
                self.last_trade[A] = self.tick

            if target_B != 0:
                price = self.bids[B][-1] if target_B < 0 else self.asks[B][-1]
                orders.append(Order(B, price, target_B))
                self.positions[B] += target_B
                self.last_trade[B] = self.tick

        for product in HIGH_SPREAD_PRODUCTS:
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
