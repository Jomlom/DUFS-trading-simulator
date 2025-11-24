from datamodel import *
from collections import deque
import numpy as np

'''
This algorithms strategy (option-backed mean reversion):

    monitor the underlying and its call and put options
    
    calculate a fair value for the underlying using the strike and option prices
    
    buy or sell the underlying when it deviates from fair value expecting it to revert
    
    simultaneously take opposite positions in the options to capture extra profit
    
    scale trades based on deviation size and gradually exit as it returns to normal
'''

class Trader:
    position_limit = 50
    window = 60
    entry_z = 1.5
    exit_z = 0.5
    max_units_per_tick = 6
    cooldown = 3
    strike = 10000

    underlyings = ["Underlying"]
    options = {"Underlying": ("Call", "Put")}

    def __init__(self):
        self.bids = {}
        self.asks = {}
        self.spread_hist = {u: deque(maxlen=self.window) for u in self.underlyings}
        self.positions = {}
        self.last_trade = {u: -999 for u in self.underlyings}
        self.tick = 0

    def run(self, state):
        orders = []
        self.tick += 1

        # update bids and asks for underlying and its options
        for u in self.underlyings:
            if u not in self.options:
                continue
            call, put = self.options[u]

            for p in [u, call, put]:
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

            # compute fair value from call and put prices
            mid_call = self._mid(call)
            mid_put = self._mid(put)
            if mid_call is None or mid_put is None:
                continue
            fair_value = mid_call - mid_put + self.strike

            mid_u = self._mid(u)
            if mid_u is None:
                continue

            # track underlying mid prices for z-score
            self.spread_hist[u].append(mid_u)
            hist = np.array(list(self.spread_hist[u]))
            if len(hist) < int(self.window/3):
                continue

            diffs = hist - fair_value
            mu, sigma = diffs.mean(), diffs.std() + 1e-8
            z = (mid_u - fair_value - mu) / sigma

            if self.tick - self.last_trade[u] < self.cooldown:
                continue

            pos = self.positions[u]

            def qty_from_z(z_val):
                # scale trade size based on signal strength
                scaled = int((abs(z_val)/self.entry_z)**0.5 * self.max_units_per_tick)
                return min(scaled, self.position_limit)

            target_qty = 0
            # decide whether to buy or sell underlying
            if z > self.entry_z and pos > -self.position_limit:
                target_qty = -min(qty_from_z(z), self.position_limit + pos)
            elif z < -self.entry_z and pos < self.position_limit:
                target_qty = min(qty_from_z(z), self.position_limit - pos)
            elif abs(z) < self.exit_z and pos != 0:
                # unwind position gradually
                target_qty = -np.sign(pos) * min(self.max_units_per_tick, abs(pos))

            if target_qty != 0:
                price = self.bids[u][-1] if target_qty < 0 else self.asks[u][-1]
                orders.append(Order(u, price, target_qty))
                self.positions[u] += target_qty
                self.last_trade[u] = self.tick

                # mirror trades on call and put to capture extra profit
                call_qty = -target_qty
                put_qty = -target_qty
                call_price = self.asks[call][-1] if call_qty > 0 else self.bids[call][-1]
                put_price  = self.asks[put][-1] if put_qty > 0 else self.bids[put][-1]
                orders.append(Order(call, call_price, call_qty))
                orders.append(Order(put, put_price, put_qty))
                self.positions[call] += call_qty
                self.positions[put] += put_qty

        return orders

    def _mid(self, p):
        bids = self.bids.get(p)
        asks = self.asks.get(p)
        if not bids or not asks:
            return None
        return (bids[-1] + asks[-1]) / 2
