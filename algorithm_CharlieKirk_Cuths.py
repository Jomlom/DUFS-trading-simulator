from datamodel import *
from collections import deque
import numpy as np

class Trader:
    """
    CUTHS mean-reversion trader (maker-first, adaptive sizing).
    """

    def __init__(
        self,
        product: str = "CUTHS_STOCKS",
        position_limit: int = 60,
        window: int = 50,                 # rolling window for z-score
        entry_z: float = 0.78,             # entry threshold
        exit_z: float = 0.27,             # exit threshold (close when |z| < exit_z)
        max_units_per_tick: int = 5,     # base per-tick size (scaled by z)
        max_per_tick_cap: int = 60,       # absolute cap per tick for safety
        skew_inventory_factor: float = 0.5,  # how aggressively inventory skews quotes
        maker_inside: int = 1,            # ticks inside spread for maker quoting (1 tick)
        aggressive_when_far: bool = True, # move closer when |z| >> entry_z
    ):
        self.product = product
        self.position_limit = position_limit

        self.window = window
        self.entry_z = entry_z
        self.exit_z = exit_z

        self.max_units_per_tick = max_units_per_tick
        self.max_per_tick_cap = max_per_tick_cap
        self.skew_inventory_factor = skew_inventory_factor

        self.maker_inside = maker_inside
        self.aggressive_when_far = aggressive_when_far

        # short history for mid and z
        self.mid_hist = deque(maxlen=self.window)
        self.tick = 0

    # helper to get best bid/ask robustly
    def _best_bid_ask(self, listings, p):
        L = Listing(listings, p)
        if not L.buy_orders or not L.sell_orders:
            return None, None, None, None
        best_bid = max(L.buy_orders.keys())
        bid_qty = L.buy_orders[best_bid]
        best_ask = min(L.sell_orders.keys())
        ask_qty = L.sell_orders[best_ask]
        return best_bid, bid_qty, best_ask, ask_qty

    # cap a proposed qty so we never violate per-product limits
    def _cap_qty(self, proposed_qty, pos):
        if proposed_qty == 0:
            return 0
        # if proposed is buy (>0)
        if proposed_qty > 0:
            allowed = self.position_limit - pos
            q = min(proposed_qty, allowed)
        else:
            # sell (negative)
            allowed = -self.position_limit - pos
            q = max(proposed_qty, allowed)
        # enforce per-tick absolute cap
        q = int(np.sign(q) * min(abs(q), self.max_per_tick_cap))
        return q

    def run(self, state):
        orders = []
        self.tick += 1

        # fetch orderbook for CUTHS
        if self.product not in state.orderbook:
            return orders
        listings = state.orderbook[self.product]

        best_bid, bid_qty, best_ask, ask_qty = self._best_bid_ask(listings, self.product)
        if best_bid is None or best_ask is None:
            return orders

        # compute mid and update history
        mid = (best_bid + best_ask) / 2.0
        self.mid_hist.append(mid)

        # need enough history
        if len(self.mid_hist) < max(10, int(self.window/4)):
            return orders

        arr = np.array(self.mid_hist)
        mu = arr.mean()
        sigma = arr.std(ddof=0) + 1e-12
        z = (mid - mu) / sigma

        pos = state.positions.get(self.product, 0)

        # inventory skew: reduce posting on the side that increases inventory
        inv_skew = (pos / max(1.0, self.position_limit))  # [-1,1]
        buy_skew = 1.0 - (inv_skew * self.skew_inventory_factor)   # long -> smaller buys
        sell_skew = 1.0 + (inv_skew * self.skew_inventory_factor)  # long -> larger sells

        # decide target action based on z
        target_buy_qty = 0
        target_sell_qty = 0

        # compute base per-tick size scaled by z
        def size_from_z(zval):
            base = self.max_units_per_tick
            scaling = (abs(zval) / max(self.entry_z, 1e-9))
            # gentle non-linear scaling
            size = int(min(base * (scaling ** 1.8), self.max_per_tick_cap))
            return max(1, size)

        # Maker prices inside spread (do not cross)
        candidate_bid = min(best_bid + self.maker_inside, best_ask - 1)
        candidate_ask = max(best_ask - self.maker_inside, best_bid + 1)
        # if inside spread collapsed, fallback
        if candidate_bid >= candidate_ask:
            candidate_bid = best_bid
            candidate_ask = best_ask

        # ENTRY: mean-reversion signals
        if z > self.entry_z:
            # price considered high -> short (sell) to capture reversion
            raw_size = size_from_z(z)
            # apply skew (we prefer to reduce buy side if long)
            sell_qty = int(raw_size * sell_skew)
            # cap with position and per-tick
            sell_qty = self._cap_qty(-sell_qty, pos)  # negative for sell
            if sell_qty != 0:
                # place maker sell at candidate_ask (inside the ask)
                orders.append(Order(self.product, candidate_ask, sell_qty))

        elif z < -self.entry_z:
            # price low -> buy
            raw_size = size_from_z(z)
            buy_qty = int(raw_size * buy_skew)
            buy_qty = self._cap_qty(buy_qty, pos)
            if buy_qty != 0:
                orders.append(Order(self.product, candidate_bid, buy_qty))

        # EXIT / SCALE OUT: when close to mean, unwind gradually
        elif abs(z) < self.exit_z:
            # if long, sell a chunk
            if pos > 0:
                unwind = min(self.max_units_per_tick, pos)
                unwind = self._cap_qty(-unwind, pos)
                if unwind != 0:
                    orders.append(Order(self.product, best_bid, unwind))
            elif pos < 0:
                unwind = min(self.max_units_per_tick, -pos)
                unwind = self._cap_qty(unwind, pos)
                if unwind != 0:
                    orders.append(Order(self.product, best_ask, unwind))

        # Aggressiveness: if |z| is very large, move inside more (optionally)
        if self.aggressive_when_far:
            # when z > 2*entry, move 1 tick closer to opposite side to increase fill chance
            if z > 2.1 * self.entry_z:
                # add a second, slightly more aggressive order (if within limits)
                extra = size_from_z(z)
                extra = self._cap_qty(-extra, pos)
                if extra != 0:
                    # place at best_bid to take liquidity (more aggressive)
                    orders.append(Order(self.product, best_bid, extra))
            elif z < -2.0 * self.entry_z:
                extra = size_from_z(z)
                extra = self._cap_qty(extra, pos)
                if extra != 0:
                    orders.append(Order(self.product, best_ask, extra))

        return orders
