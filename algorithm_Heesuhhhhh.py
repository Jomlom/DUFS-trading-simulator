from datamodel import *
import numpy as np
from collections import deque

class Trader:
    def __init__(self):
        self.MAX_POS = 40
        self.VOL_WINDOW = 30
        self.mid_buf = deque(maxlen=self.VOL_WINDOW)
        self.last_mid = None

        self.arb_threshold = 0.015
        self.arb_size = 12

    def run(self, state):

        p = "ETF1"
        if p not in state.orderbook: return []
        L = Listing(state.orderbook[p], p)
        bid, ask = list(L.buy_orders.keys())[0], list(L.sell_orders.keys())[0]
        bq, aq = L.buy_orders[bid], L.sell_orders[ask]
        if ask - bid <= 0: return []

        pos = state.positions.get(p, 0)
        mid = 0.5*(bid+ask)
        self.mid_buf.append(mid)
        vol = np.std(np.diff(self.mid_buf))+1e-6 if len(self.mid_buf)>=5 else 1.0
        diff = mid - self.last_mid if self.last_mid is not None else 0
        momentum = 1 if diff>0.5 else -1 if diff<-0.5 else 0
        self.last_mid = mid

        imb = (bq-aq)/max(1,bq+aq)
        tilt = int(imb*2)
        boost = max(1,int(0.65*(ask-bid)+12*vol))
        lean = int(0.025*pos)

        our_bid = min(bid+boost-lean+tilt, ask-1)
        our_ask = max(ask-boost-lean+tilt, bid+1)

        base = 30+int(9*(ask-bid))+int(90*vol)
        size = max(10, base + int(abs(imb)*110) - int(abs(pos)*0.55))
        buy_cap, sell_cap = max(0,self.MAX_POS-pos), max(0,self.MAX_POS+pos)
        buy_size, sell_size = min(size,buy_cap), min(size,sell_cap)
        orders = []

        def get_best(product_name):
            if product_name not in state.orderbook:
                return None
            Lp = Listing(state.orderbook[product_name], product_name)
            if not Lp.buy_orders or not Lp.sell_orders:
                return None
            b = list(Lp.buy_orders.keys())[0]
            a = list(Lp.sell_orders.keys())[0]
            return b, a, 0.5 * (b+a)

        b1 = get_best("bond1")
        b2 = get_best("bond2")
        b3 = get_best("bond3")

        if b1 and b2 and b3:
            b1_bid, b1_ask, b1_mid = b1
            b2_bid, b2_ask, b2_mid = b2
            b3_bid, b3_ask, b3_mid = b3

            synth_mid = b1_mid + b2_mid + b3_mid
            if synth_mid > 0:
                spread = mid - synth_mid
                rel_spread = spread / synth_mid

                if abs(rel_spread) > self.arb_threshold:
                    etf_pos = state.positions.get("ETF1", 0)
                    etf_buy_cap = max(0, self.MAX_POS - etf_pos)
                    etf_sell_cap = max(0, self.MAX_POS + etf_pos)

                    if rel_spread > 0:
                        qty = min(self.arb_size, etf_sell_cap)
                        if qty > 0:
                            bond_qty = max(1, qty // 3)
                            orders.append(Order("ETF1", bid, -qty))
                            orders.append(Order("bond1", b1_ask, bond_qty))
                            orders.append(Order("bond2", b2_ask, bond_qty))
                            orders.append(Order("bond3", b3_ask, bond_qty))
                            return orders  # skip momentum/MM this tick

                    else:
                        # ETF1 cheap: long ETF1, short bonds
                        qty = min(self.arb_size, etf_buy_cap)
                        if qty > 0:
                            bond_qty = max(1, qty // 3)
                            orders.append(Order("ETF1", ask, qty))
                            orders.append(Order("bond1", b1_bid, -bond_qty))
                            orders.append(Order("bond2", b2_bid, -bond_qty))
                            orders.append(Order("bond3", b3_bid, -bond_qty))
                            return orders
                        
        if abs(imb)>0.6:
            if momentum==1 and buy_cap>0: return [Order(p, ask, buy_cap)]
            if momentum==-1 and sell_cap>0: return [Order(p, bid, -sell_cap)]
        if buy_size>0 and bq>0: orders.append(Order(p, our_bid, buy_size))
        if sell_size>0 and aq>0: orders.append(Order(p, our_ask, -sell_size))

        return orders
'''
        product = "bond4"
        listings = Listing(state.orderbook[product], product)
        if listings.buy_orders and listings.sell_orders:
            highest_bid, lowest_ask = list(listings.buy_orders.keys())[0], list(listings.sell_orders.keys())[0]
            bid_qty, ask_qty = listings.buy_orders[highest_bid], listings.sell_orders[lowest_ask]
            spread = lowest_ask - highest_bid
            if not spread < 2:
                base_qty, boost = (2, 1) if spread <= 3 else (3, 2) if spread <= 5 else (5, 3)
                our_bid = min(highest_bid + boost, lowest_ask - 1)
                our_ask = max(lowest_ask - boost, highest_bid + 1)

                if bid_qty > 0:
                    orders.append(Order(product, our_bid, base_qty))
                if ask_qty > 0:
                    orders.append(Order(product, our_ask, -base_qty))

        product2 = "bond2"
        orders.append(Order(product2, list(Listing(state.orderbook[product], product2).sell_orders.keys())[0], 40))

        return orders
        '''
