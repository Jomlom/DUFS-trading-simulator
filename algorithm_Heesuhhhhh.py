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

        if abs(imb)>0.6:
            if momentum==1 and buy_cap>0: return [Order(p, ask, buy_cap)]
            if momentum==-1 and sell_cap>0: return [Order(p, bid, -sell_cap)]
        if buy_size>0 and bq>0: orders.append(Order(p, our_bid, buy_size))
        if sell_size>0 and aq>0: orders.append(Order(p, our_ask, -sell_size))

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


        return orders
