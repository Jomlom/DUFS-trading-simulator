from datamodel import *
import numpy as np
#made 10k
class Trader:
    def __init__(self):
        # ETF1 params
        self.MAX_POS1 = 40
        self.W1 = 60
        self.e1_hist = []
        self.s1_hist = []
        self.E1_ENTRY = 0.9
        self.E1_EXIT = 0.25

        # ETF2 params
        self.MAX_POS2 = 40
        self.W2 = 60
        self.e2_hist = []
        self.s2_hist = []
        self.E2_ENTRY = 0.3
        self.E2_EXIT = -2

    def mid(self, state, p):
        L = Listing(state.orderbook[p], p)
        bid = list(L.buy_orders.keys())[0]
        ask = list(L.sell_orders.keys())[0]
        return (bid + ask) / 2, bid, ask

    def run(self, state):
        orders = []

        # ---------------- ETF1 ----------------
        if all(p in state.orderbook for p in ["ETF1","bond1","bond2","bond3"]):
            mid_e, bid_e, ask_e = self.mid(state, "ETF1")
            m1,_,_ = self.mid(state, "bond1")
            m2,_,_ = self.mid(state, "bond2")
            m3,_,_ = self.mid(state, "bond3")

            syn = m1 + m2 + m3
            self.e1_hist.append(mid_e)
            self.s1_hist.append(syn)

            if len(self.e1_hist) >= self.W1:
                arr = np.array(self.e1_hist[-self.W1:]) - np.array(self.s1_hist[-self.W1:])
                mean = arr.mean()
                std  = arr.std() + 1e-6
                spread_now = mid_e - syn
                z = (spread_now - mean) / std

                pos = state.positions.get("ETF1", 0)

                if z < -self.E1_ENTRY and pos < self.MAX_POS1:
                    size = min(30, self.MAX_POS1 - pos)
                    orders.append(Order("ETF1", ask_e, size))

                if z > self.E1_ENTRY and pos > -self.MAX_POS1:
                    size = min(30, pos + self.MAX_POS1)
                    orders.append(Order("ETF1", bid_e, -size))

                if abs(z) < self.E1_EXIT:
                    if pos > 0:
                        size = min(-40, pos)          # ← YOUR EXACT LINE
                        orders.append(Order("ETF1", bid_e, -size))
                    elif pos < 0:
                        size = min(-40, -pos)         # ← YOUR EXACT LINE
                        orders.append(Order("ETF1", ask_e, size))

        # ---------------- ETF2 ----------------
        if all(p in state.orderbook for p in ["ETF2","bond1","bond2","bond4"]):
            mid_e, bid_e, ask_e = self.mid(state, "ETF2")
            m1,_,_ = self.mid(state, "bond1")
            m2,_,_ = self.mid(state, "bond2")
            m4,_,_ = self.mid(state, "bond4")

            syn = 0.5 * (m1 + m2 + m4)
            self.e2_hist.append(mid_e)
            self.s2_hist.append(syn)

            if len(self.e2_hist) >= self.W2:
                arr = np.array(self.e2_hist[-self.W2:]) - np.array(self.s2_hist[-self.W2:])
                mean = arr.mean()
                std  = arr.std() + 1e-6
                spread_now = mid_e - syn
                z = (spread_now - mean) / std

                pos = state.positions.get("ETF2", 0)

                if z < -self.E2_ENTRY and pos < self.MAX_POS2:
                    size = min(40, self.MAX_POS2 - pos)
                    orders.append(Order("ETF2", ask_e, size))

                if z > self.E2_ENTRY and pos > -self.MAX_POS2:
                    size = min(40, pos + self.MAX_POS2)
                    orders.append(Order("ETF2", bid_e, -size))

                if abs(z) < self.E2_EXIT:
                    if pos > 0:
                        size = min(-40, pos)
                        orders.append(Order("ETF2", bid_e, -size))
                    elif pos < 0:
                        size = min(-40, -pos)
                        orders.append(Order("ETF2", ask_e, size))

        return orders