from datamodel import *
import numpy as np
from collections import deque

class Trader:
    def __init__(self):
        self.MAX_POS = 160
        self.VOL_WINDOW = 30
        self.mid_buf = deque(maxlen=self.VOL_WINDOW)
        self.last_mid = None

    def run(self, state):
        p = "ETF1"
        if p not in state.orderbook:
            return []

        L = Listing(state.orderbook[p], p)
        bid = list(L.buy_orders.keys())[0]
        ask = list(L.sell_orders.keys())[0]
        bq = L.buy_orders[bid]
        aq = L.sell_orders[ask]
        spread = ask - bid
        if spread <= 0:
            return []

        pos = state.positions.get(p, 0)

        # --------------------------
        # VOL & MID
        # --------------------------
        mid = 0.5 * (bid + ask)
        self.mid_buf.append(mid)

        if len(self.mid_buf) >= 5:
            vol = np.std(np.diff(self.mid_buf)) + 1e-6
        else:
            vol = 1.0

        # --------------------------
        # MOMENTUM SIGNAL
        # --------------------------
        momentum = 0
        if self.last_mid is not None:
            diff = mid - self.last_mid
            if diff > 0.5: momentum = 1
            elif diff < -0.5: momentum = -1
        self.last_mid = mid

        # --------------------------
        # ORDERBOOK IMBALANCE
        # --------------------------
        imb = (bq - aq) / max(1, bq + aq)
        tilt = int(imb * 2)

        # --------------------------
        # BOOST
        # --------------------------
        boost = max(1, int(0.65 * spread + 12 * vol))

        # --------------------------
        # INVENTORY LEAN
        # --------------------------
        lean = int(0.025 * pos)

        # --------------------------
        # QUOTES
        # --------------------------
        our_bid = bid + boost - lean + tilt
        our_ask = ask - boost - lean + tilt

        if our_bid >= ask:
            our_bid = ask - 1
        if our_ask <= bid:
            our_ask = bid + 1

        # --------------------------
        # SIZE MODEL (buffed)
        # --------------------------
        base = 30 + int(9 * spread) + int(90 * vol)
        imb_add = int(abs(imb) * 110)
        inv_pen = int(abs(pos) * 0.55)

        size = max(10, base + imb_add - inv_pen)

        buy_cap = max(0, self.MAX_POS - pos)
        sell_cap = max(0, self.MAX_POS + pos)

        buy_size = min(size, buy_cap)
        sell_size = min(size, sell_cap)

        orders = []

        # --------------------------
        # NEW: AGGRESSIVE SNAP MODE
        # --------------------------
        if abs(imb) > 0.6 and momentum == 1 and buy_cap > 0:
            orders.append(Order(p, ask, buy_cap))     # take to max long
            return orders

        if abs(imb) > 0.6 and momentum == -1 and sell_cap > 0:
            orders.append(Order(p, bid, -sell_cap))   # take to max short
            return orders

        # --------------------------
        # NORMAL MAKER MODE
        # --------------------------
        if buy_size > 0 and bq > 0:
            orders.append(Order(p, our_bid, buy_size))
        if sell_size > 0 and aq > 0:
            orders.append(Order(p, our_ask, -sell_size))

        return orders
