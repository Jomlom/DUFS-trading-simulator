from datamodel import *
import numpy as np
#made 6.1k

class Trader:
    def __init__(self):
        self.MAX_POS = 40
        self.W = 60
        self.etf_hist = []
        self.syn_hist = []
        self.ENTRY = 0.9
        self.EXIT = 0.25

    def run(self, state):
        orders = []
        etf = "ETF1"
        b1 = "bond1"
        b2 = "bond2"
        b3 = "bond3"

        # All books required
        if etf not in state.orderbook or b1 not in state.orderbook:
            return orders

        # Mid prices
        def mid(p):
            L = Listing(state.orderbook[p], p)
            bid = list(L.buy_orders.keys())[0]
            ask = list(L.sell_orders.keys())[0]
            return (bid + ask) / 2, bid, ask

        mid_e, bid_e, ask_e = mid(etf)
        mid_1, _, _ = mid(b1)
        mid_2, _, _ = mid(b2)
        mid_3, _, _ = mid(b3)

        synthetic = mid_1 + mid_2 + mid_3

        # Save history
        self.etf_hist.append(mid_e)
        self.syn_hist.append(synthetic)

        if len(self.etf_hist) < self.W:
            return orders

        # Compute spread + zscore like Excel
        spread_arr = np.array(self.etf_hist[-self.W:]) - np.array(self.syn_hist[-self.W:])
        mean = spread_arr.mean()
        std = spread_arr.std() + 1e-6
        spread_now = mid_e - synthetic
        z = (spread_now - mean) / std

        pos = state.positions.get(etf, 0)

        # BUY (same profitable logic as original)
        if z < -self.ENTRY and pos < self.MAX_POS:
            size = min(30, self.MAX_POS - pos)
            orders.append(Order(etf, ask_e, size))

        # SELL (new synthetic-based logic)
        if z > self.ENTRY and pos > -self.MAX_POS:
            size = min(30, pos + self.MAX_POS)
            orders.append(Order(etf, bid_e, -size))

        # EXIT positions when mispricing normalizes
        if abs(z) < self.EXIT:
            if pos > 0:
                size = min(-40, pos)
                orders.append(Order(etf, bid_e, -size))
            elif pos < 0:
                size = min(-40, -pos)
                orders.append(Order(etf, ask_e, size))

        return orders
