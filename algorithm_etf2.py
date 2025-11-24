from datamodel import *
import numpy as np

class Trader:
    def __init__(self):
        self.W = 60
        self.MAX_POS = 40
        self.etf_hist = []
        self.syn_hist = []
        self.ENTRY = 0.3
        self.EXIT  = -2

    def run(self, state):
        orders = []
        etf = "ETF2"
        b1, b2, b4 = "bond1", "bond2", "bond4"

        if any(p not in state.orderbook for p in [etf,b1,b2,b4]):
            return orders

        def mid(p):
            L = Listing(state.orderbook[p], p)
            bid = list(L.buy_orders.keys())[0]
            ask = list(L.sell_orders.keys())[0]
            return (bid + ask) / 2, bid, ask

        mid_e, bid_e, ask_e = mid(etf)
        mid1,_,_ = mid(b1)
        mid2,_,_ = mid(b2)
        mid4,_,_ = mid(b4)

        synthetic = 0.5 * (mid1 + mid2 + mid4)

        self.etf_hist.append(mid_e)
        self.syn_hist.append(synthetic)

        if len(self.etf_hist) < self.W:
            return orders

        arr = np.array(self.etf_hist[-self.W:]) - np.array(self.syn_hist[-self.W:])
        mean = arr.mean()
        std  = arr.std() + 1e-6
        spread_now = mid_e - synthetic
        z = (spread_now - mean) / std

        pos = state.positions.get(etf, 0)

        if z < -self.ENTRY and pos < self.MAX_POS:
            size = min(40, self.MAX_POS - pos)
            orders.append(Order(etf, ask_e, size))

        if z > self.ENTRY and pos > -self.MAX_POS:
            size = min(40, pos + self.MAX_POS)
            orders.append(Order(etf, bid_e, -size))

        if abs(z) < self.EXIT:
            if pos > 0:
                size = min(-40, pos)
                orders.append(Order(etf, bid_e, -size))
            elif pos < 0:
                size = min(-40, -pos)
                orders.append(Order(etf, ask_e, size))

        return orders
