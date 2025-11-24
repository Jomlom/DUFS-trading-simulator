from datamodel import *
from collections import deque
import numpy as np

class Trader:


    consideration_window = 50
    ENTRY_STD_MULTIPLIER = 1.5
    max_units = 10
    COOLDOWN_TICKS = 5

    pair = [
        ("ETF1", ("ETF2", "ETF2"), "E1_E2"),
        ("ETF1", ("bond1", "bond2", "bond3"), "E1_B123")
    ]

    pair_entry_threshold ={
        "E1_E2": 1.0,
        "E1_B123":1.5

    }
    pair_position_limits = {
        "E1_E2": 20,
        "E1_B123":20
    }

    pair_exit_thresholds = {
        "E1_E2": 0.3,
        "E1_B123": 0.3
    }
    def __init__(self):
        self.spread_history = {}
        self.positions = {}
        self.bid_values = {}
        self.bid_quantities = {}
        self.ask_values = {}
        self.ask_quantities = {}
        self.last_trade_tick = {}
        self.current_tick = 0
        self.price_history = {}
        self.zscore_history = {}
        self.products = {"bond1", "bond2", "bond3", "ETF1", "ETF2"}

        for product in self.products:
            self.positions[product] = 0
            self.bid_values[product] = deque(maxlen=1)
            self.bid_quantities[product] = deque(maxlen=1)
            self.ask_values[product] = deque(maxlen=1)
            self.ask_quantities[product] = deque(maxlen=1)
            self.price_history[product] = deque(maxlen=self.consideration_window)
            


        for product_a, product_b, pair_name in self.pair:
            self.spread_history[pair_name] = deque(maxlen=self.consideration_window)
            self.zscore_history[pair_name] = deque(maxlen=2)
            self.last_trade_tick[pair_name] = 0


    def run(self, state):
        orders = []
        self.current_tick += 1

        for product in self.products:
            listings = state.orderbook.get(product)
            if not listings:
                continue
            listings = Listing(listings, product)
            if not listings.buy_orders or not listings.sell_orders:
                continue
            self.bid_values[product].append(list(listings.buy_orders.keys()))
            self.bid_quantities[product].append(list(listings.buy_orders.values()))
            self.ask_values[product].append(list(listings.sell_orders.keys()))
            self.ask_quantities[product].append(list(listings.sell_orders.values()))
            if product in ["ETF1", "ETF2"]:  #Can look only at the best prices due to the good liquidity
                self.price_history[product].append((self.bid_values[product][0] + self.ask_values[product][0]) / 2)
            else: #calculate vwap for better indication of price 
                self.price_history[product].append(self.vwap(self.bid_values[product],self.bid_quantities[product],self.ask_values[product],self.ask_quantities[product]))


        for prodA, prodB, pair in self.pair:
            prodB_price_history = 0
            for val in prodB:
                prodB_price_history += self.price_history[val][-1]
            spread = self.price_history[prodA][-1] - prodB_price_history
            self.spread_history[pair].append(spread)

            mean = np.mean(self.spread_history[pair])
            std = np.std(self.spread_history[pair]) + 1e-8
            zscore = (spread - mean) / std
            self.zscore_history[pair].append(zscore)

            if self.current_tick - self.last_trade_tick[pair] < self.COOLDOWN_TICKS:
                continue

            #if self.current_tick < self.consideration_window:
            #    continue

            posB = state.positions[prodB[0]] #only look at the size of b, as the size of a varies as we trade it against 2 pairs
            posA = -posB
            #How many bid and asks we need to consider depends on how many units we would ideally like to buy
            ideal_bid = self.calculate_position_size(self.zscore_history[pair][-1], posB, pair)
            if pair == "E1_B123":
                B1_ask_quantities = []
                B2_ask_quantities = []
                B3_ask_quantities = []
                B1_bid_quantities = []
                B2_bid_quantities = []
                B3_bid_quantities = []
                for j in range(3):
                    B1_ask_quantities.append(self.ask_quantities[prodB[0]][j])
                    B2_ask_quantities.append(self.ask_quantities[prodB[1]][j])
                    B3_ask_quantities.append(self.ask_quantities[prodB[2]][j])
                    B1_bid_quantities.append(self.bid_quantities[prodB[0]][j])
                    B2_bid_quantities.append(self.bid_quantities[prodB[1]][j])
                    B3_bid_quantities.append(self.bid_quantities[prodB[2]][j])
                ideal_askbid = min(ideal_bid, sum(B1_ask_quantities), sum(B2_ask_quantities), sum(B3_ask_quantities))
                ideal_bidbid = min(ideal_bid, sum(B2_bid_quantities), sum(B1_bid_quantities), sum(B3_bid_quantities))
            
        
            if zscore > self.entry_threshold[pair] and self.check_Z(pair) == True:
                if pair == "E1_B123":
                    i = 0
                    while ideal_askbid >0:
                        orders.append(Order(prodB[0], self.ask_values[prodB[0]][i], B1_ask_quantities[i]))
                        orders.append(Order(prodB[1], self.ask_values[prodB[1]][i], B2_ask_quantities[i]))
                        orders.append(Order(prodB[2], self.ask_values[prodB[2]][i], B3_ask_quantities[i]))
                        ideal_askbid - min(B1_ask_quantities[i], B2_ask_quantities[i], B3_ask_quantities[i])
                        i += 1
                else:
                    orders.append(Order(prodB[0]), self.ask_values[prodB[0]][i], 2*ideal_bid)
                orders.append(Order(prodA, self.bid_values[0], -ideal_bid))
                self.last_trade_tick[pair] = self.current_tick
            
            elif zscore < -self.entry_threshold[pair] and self.check_Z(pair) == True:
                if pair == "E1_B123":
                    i = 0
                    while ideal_bidbid >0:
                        orders.append(Order(prodB[0], self.bid_values[prodB[0]][i], -B1_bid_quantities[i]))
                        orders.append(Order(prodB[1], self.bid_values[prodB[1]][i], -B2_bid_quantities[i]))
                        orders.append(Order(prodB[2], self.bid_values[prodB[2]][i], -B3_ask_quantities[i]))
                        ideal_bidbid - min(B1_bid_quantities[i], B2_bid_quantities[i], B3_bid_quantities[i])
                        i += 1
                else:
                    orders.append(Order(prodB[0]), self.bid_values[prodB[0]][i], -2*ideal_bid)
                orders.append(Order(prodA, self.ask_values[0], ideal_bid))
                self.last_trade_tick[pair] = self.current_tick
            
                
               
                
                if posA < 0 and posB > 0 and zscore < self.pair_exit_thresholds[pair]:  # Some exit threshold
                    ideal_bid = min(-posA, posB, self.max_units, sum(B1_bid_quantities), sum(B2_bid_quantities), sum(B3_bid_quantities))

                    if pair == "E1_B123":
                        i = 0
                        while ideal_bid >0:
                            orders.append(Order(prodB[0], self.bid_values[prodB[0]][i], -B1_bid_quantities[i]))
                            orders.append(Order(prodB[1], self.bid_values[prodB[1]][i], -B2_bid_quantities[i]))
                            orders.append(Order(prodB[2], self.bid_values[prodB[2]][i], -B3_ask_quantities[i]))
                            ideal_bid - min(B1_bid_quantities[i], B2_bid_quantities[i], B3_bid_quantities[i])
                            i += 1
                    else:
                        orders.append(Order(prodB[0]), self.bid_values[prodB[0]][i], -2*ideal_bid)
            
                orders.append(Order(prodA, self.ask_values[prodA], ideal_bid))  # Sell to reduce lon


        return orders

    def check_Z(self, pair):
        prev_Z = self.zscore_history[pair][0]
        current_Z = self.zscore_history[pair][1]
        if prev_Z > abs(self.pair_entry_threshold[pair]) and current_Z < abs(self.pair_entry_threshold):
            return True 
        return False
    
    def vwap(self, bidv, bidq, askv, askq):
        num = 0
        denom = 0
        for i, _ in enumerate(bidv):
            num += bidv[i]*bidq[i]
            denom += bidq[i]
        for i, _ in enumerate(askv):
            num += askv[i]*askq[i]
            denom += bidq[i]
        if denom == 0:
            raise ValueError('could not calculate vwap')
        else:
            return num/denom

    def calculate_position_size(self, zscore, current_pos, pair):
    
        # Base size scales with z-score strength
        base_size = min(int(abs(zscore) * 2), self.max_units)  # Adjust multiplier as needed
        
        # Adjust for current position (don't add to losing positions)
        if (zscore > 0 and current_pos < 0) or (zscore < 0 and current_pos > 0):
            # We're against our current position - be cautious
            base_size = min(base_size, self.max_units // 2)
        
        # Ensure we don't exceed position limits
        available = self.pair_position_limits[pair] - abs(current_pos) if current_pos > 0 else self.pair_position_limits[pair] + current_pos
        return abs(min(base_size, available, self.max_units))

