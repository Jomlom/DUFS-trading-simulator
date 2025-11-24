from datamodel import *
import numpy as np
from collections import deque

class Trader:
    def __init__(self, base='bond1', alt='bond4', W=120, ENTRY=1.5, EXIT=0.5, MAX_POS=40, SIZE=10):
        self.base = base
        self.alt  = alt
        self.W = W
        self.ENTRY = ENTRY
        self.EXIT  = EXIT
        self.MAX_POS = MAX_POS
        self.SIZE = SIZE
        self.b_base = deque(maxlen=W)
        self.b_alt  = deque(maxlen=W)

    def _mid(self, state, p):
        L = Listing(state.orderbook[p], p)
        bid = list(L.buy_orders.keys())[0]; ask = list(L.sell_orders.keys())[0]
        return 0.5*(bid+ask), bid, ask

    def run(self, state):
        orders=[]
        if any(p not in state.orderbook for p in (self.base, self.alt)):
            return orders

        mid_b, bid_b, ask_b = self._mid(state, self.base)
        mid_a, bid_a, ask_a = self._mid(state, self.alt)

        self.b_base.append(mid_b); self.b_alt.append(mid_a)
        if len(self.b_base) < self.W:
            return orders

        spread = np.array(self.b_base) - np.array(self.b_alt)
        mean = spread.mean(); std = spread.std() + 1e-9
        current = mid_b - mid_a
        z = (current - mean) / std

        pos_b = int(state.positions.get(self.base, 0))
        pos_a = int(state.positions.get(self.alt, 0))

        # If base is cheap vs alt -> BUY base, SELL alt (hedged)
        if z < -self.ENTRY and pos_b < self.MAX_POS and pos_a > -self.MAX_POS:
            q = min(self.SIZE, self.MAX_POS - pos_b)           # buy base
            h = q                                              # hedge 1:1 (change if you want ratio)
            orders.append(Order(self.base, ask_b, q))
            orders.append(Order(self.alt, bid_a, -h))
            return orders

        # If base is rich vs alt -> SELL base, BUY alt
        if z > self.ENTRY and pos_b > -self.MAX_POS and pos_a < self.MAX_POS:
            q = min(self.SIZE, self.MAX_POS + pos_b)          # sell base
            h = q
            orders.append(Order(self.base, bid_b, -q))
            orders.append(Order(self.alt, ask_a, h))
            return orders

        # Exit / trim when normalized
        if abs(z) < self.EXIT:
            # pare down base position
            if pos_b > 0:
                q = min(self.SIZE, pos_b)
                orders.append(Order(self.base, bid_b, -q))
            elif pos_b < 0:
                q = min(self.SIZE, -pos_b)
                orders.append(Order(self.base, ask_b, q))
            # pare down alt
            if pos_a > 0:
                q = min(self.SIZE, pos_a)
                orders.append(Order(self.alt, bid_a, -q))
            elif pos_a < 0:
                q = min(self.SIZE, -pos_a)
                orders.append(Order(self.alt, ask_a, q))
            return orders

        return orders
