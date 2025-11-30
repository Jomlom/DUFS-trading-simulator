import logging
import importlib.util
import pandas as pd
from datamodel import Portfolio, State
from dataimport import read_file, extract_orders, extract_bot_orders
from ordermatching import match_order
from bots_functions import add_bot_orders
from datetime import datetime

# -----------------------
# PARAMETER SEARCH SPACE
# -----------------------

ENTRY_Z_VALUES = [0.8, 1.0, 1.2, 1.5]
EXIT_Z_VALUES  = [0.15, 0.2, 0.3]

# -----------------------
# UTILITY FUNCTIONS
# -----------------------

def import_trader(file_path: str) -> type:
    spec = importlib.util.spec_from_file_location("trader_module", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Trader

def init_portfolio(products):
    portfolio = Portfolio()
    for p in products:
        portfolio.quantity[p] = 0
    return portfolio

def run_sim(products, ticks, df, bot_df, TraderClass, params, target_pair):
    entry_z, exit_z = params

    algo = TraderClass(
        entry_z=entry_z,
        exit_z=exit_z
    )

    # Limit Trader to 1 pair
    algo.pairs = [target_pair]

    portfolio = init_portfolio(products)
    pos_limit = {p: 60 for p in products}

    for tick in range(1, ticks):
        orderbook = {p: extract_orders(df, tick, p) for p in products}
        bot_orders = {p: extract_bot_orders(bot_df, tick, p) for p in products}

        state = State(orderbook, portfolio.quantity, products, pos_limit)
        algo_orders = algo.run(state)

        resting = match_order(algo_orders, state.orderbook, portfolio, pos_limit)
        add_bot_orders(bot_orders, state.orderbook, resting, portfolio, pos_limit)

        # update pnl
        portfolio.pnl = portfolio.cash
        for p in products:
            best_bid = next(iter(state.orderbook[p]["BUY"]))
            best_ask = next(iter(state.orderbook[p]["SELL"]))
            mid = (best_bid + best_ask) / 2
            portfolio.pnl += portfolio.quantity[p] * mid

    return portfolio.pnl


# -----------------------
# OPTIMISATION ENGINE
# -----------------------

def optimise(round_path, algo_path):
    products, ticks, df = read_file(round_path)
    bot_df = pd.read_csv(round_path[:-4] + "_bots.csv")

    TraderClass = import_trader(algo_path)

    from algorithm_5 import PAIRS   # use your pair list

    results = []

    print("\n=== Running optimisation ===")

    for pair in PAIRS:
        print(f"\nTesting pair: {pair}")

        for entry_z in ENTRY_Z_VALUES:
            for exit_z in EXIT_Z_VALUES:

                params = (entry_z, exit_z)
                pnl = run_sim(products, ticks, df, bot_df, TraderClass, params, pair)

                results.append({
                    "pair": pair,
                    "entry_z": entry_z,
                    "exit_z": exit_z,
                    "PnL": pnl
                })

                print(f"  entry_z={entry_z:.2f}, exit_z={exit_z:.2f} → PnL={pnl:.2f}")

    # Output sorted results
    print("\n=== BEST RESULTS ===")
    df_res = pd.DataFrame(results)
    df_res = df_res.sort_values("PnL", ascending=False)
    print(df_res)

    df_res.to_csv("pair_param_results.csv", index=False)
    print("\nSaved results to pair_param_results.csv")


# -----------------------
# MAIN
# -----------------------

if __name__ == "__main__":
    optimise("Round Data/Round_4/Round_4.csv", "algo_5_test.py")
