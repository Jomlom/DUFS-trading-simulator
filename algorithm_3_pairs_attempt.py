from datamodel import Order
import numpy as np

PAIR_PARAMS = {
    ("HATFIELD_STOCKS", "COLLINGWOOD_STOCKS"): (-0.104, 1.012),
    ("HATFIELD_STOCKS", "CASTLE_STOCKS"):      (4.491, 0.180),
    ("CASTLE_STOCKS", "CHAD_STOCKS"):         (-6.238, 2.182),
    ("CASTLE_STOCKS", "COLLINGWOOD_STOCKS"):  (-14.922, 3.6605),
    ("CHADS_STOCKS", "JOHNS_STOCKS"):         (-4.325, 1.673),
    ("CUTHS_STOCKS", "JOHNS_STOCKS"):         (5.866, -0.205),
    ("CASTLE_STOCKS", "JOHNS_STOCKS"):        (-24.835, 5.545),
}

class Trader:
    def __init__(self):
        self.win = 80
        self.min_obs = 40
        self.entry_z = 2.0
        self.exit_z = 0.4
        self.max_pos = 15
        self.step_cap = 2
        self.stop_z = 3.0

        #add momentum
        self.momentum_lookback = 3

        # per-pair history & last_z
        self.spread_hist = {pair: [] for pair in PAIR_PARAMS}
        self.last_z = {pair: None for pair in PAIR_PARAMS}

    def _best_bid_ask(self, ob):
        buys = ob.get("BUY", {})
        sells = ob.get("SELL", {})
        if not buys or not sells:
            return None, None
        return max(buys), min(sells)

    def _vwap(self, ob, depth=3):
        buys = sorted(ob.get("BUY", {}).items(), key=lambda x: x[0], reverse=True)[:depth]
        sells = sorted(ob.get("SELL", {}).items(), key=lambda x: x[0])[:depth]
        if not buys or not sells:
            return None
        levels = buys + sells
        total_vol = sum(v for _, v in levels)
        if total_vol <= 0:
            return None
        total_val = sum(p * v for p, v in levels)
        return total_val / total_vol

    def run(self, state):
        orders = []
        pos = getattr(state, "position", {})

        for (A, B), (ALPHA, BETA) in PAIR_PARAMS.items():
            obA = state.orderbook.get(A)
            obB = state.orderbook.get(B)
            if obA is None or obB is None:
                continue

            vwapA = self._vwap(obA)
            vwapB = self._vwap(obB)
            if vwapA is None or vwapB is None or vwapA <= 0 or vwapB <= 0:
                continue

            logA = np.log(vwapA)
            logB = np.log(vwapB)

            # residual spread for THIS pair: logB - (alpha + beta * logA)
            spread = float(logB - (ALPHA + BETA * logA))

            hist = self.spread_hist[(A, B)]
            hist.append(spread)
            if len(hist) > self.win:
                self.spread_hist[(A, B)] = hist[-self.win:]
                hist = self.spread_hist[(A, B)]

            if len(hist) < self.min_obs:
                self.last_z[(A, B)] = None
                continue

            mu = float(np.mean(hist))
            sigma = float(np.std(hist))
            if sigma < 1e-8:
                self.last_z[(A, B)] = None
                continue

            z = (spread - mu) / sigma

            prev_z = self.last_z[(A, B)]
            self.last_z[(A, B)] = z

            posA = pos.get(A, 0)
            posB = pos.get(B, 0)
            flat = (posA == 0 and posB == 0)

            def just_turning(z_now, z_prev):
                if z_prev is None:
                    return False
                return (
                    abs(z_prev) >= self.entry_z and
                    abs(z_now) >= self.entry_z and
                    abs(z_now) < abs(z_prev)
                )
            
                # Requirement 3: Just started decreasing (current < previous)

            # default: hold current positions for this pair
            targetA, targetB = posA, posB

            if flat and just_turning(z, prev_z) and abs(z) > self.entry_z:
                # scale size with |Z| between entry_z and stop_z
                span = max(self.stop_z - self.entry_z, 1e-6)
                scaled = (abs(z) - self.entry_z) / span
                scaled = max(0.0, min(1.0, scaled))
                base = int(self.max_pos * scaled)
                base = max(base, 5)

                # z>0: B rich vs A -> long A, short B
                if z > 0:
                    targetA = +base
                    targetB = -base
                else:
                    # z<0: B cheap vs A -> short A, long B
                    targetA = -base
                    targetB = +base

            elif not flat and abs(z) < self.exit_z:
                targetA, targetB = 0, 0

            elif not flat and abs(z) > self.stop_z:
                targetA, targetB = 0, 0

            def step_to(target, current):
                d = target - current
                if d > 0:
                    return min(d, self.step_cap)
                if d < 0:
                    return max(d, -self.step_cap)
                return 0

            dA = step_to(targetA, posA)
            dB = step_to(targetB, posB)

            bidA, askA = self._best_bid_ask(obA)
            bidB, askB = self._best_bid_ask(obB)
            if bidA is None or bidB is None or askA is None or askB is None:
                continue

            if dA > 0:
                orders.append(Order(A, askA, dA))
            elif dA < 0:
                orders.append(Order(A, bidA, dA))

            if dB > 0:
                orders.append(Order(B, askB, dB))
            elif dB < 0:
                orders.append(Order(B, bidB, dB))

        return orders
