from typing import Dict
from datamodel import Portfolio

def clean_resting_orders(resting_orders: Dict[str, Dict[str, Dict[int, int]]]):
    """
    Removes price levels with 0 quantity from order books.

    :param resting_orders: An orderbook to clean.
    """
    for product, sides in resting_orders.items():
        for side, book in sides.items():
            empty_prices = [price for price, qty in book.items() if qty == 0]
            for price in empty_prices:
                del book[price]

def add_bot_orders(
    bot_orders: Dict[str, Dict],
    market_orderbook: Dict[str, Dict],
    algo_resting_orders: Dict[str, Dict],
    portfolio: Portfolio,
    pos_limit: Dict[str, int],
) -> None:
    """
    Process bot orders against the market and algo resting orders.

    :param bot_orders: Bot orders in the same format as the orderbook
    :param market_orderbook: The main market orderbook
    :param algo_resting_orders: The algo's resting orders
    :param portfolio: The portfolio to be updated
    :param pos_limit: The maximum quantity the portfolio can hold
    """

    for product, sides in bot_orders.items():
        if "BUY" in sides:
            for bot_price in sorted(sides["BUY"].keys(), reverse=True):
                bot_quantity = sides["BUY"][bot_price]

                market_sells = market_orderbook[product]["SELL"]
                for market_sell_price in sorted(market_sells.keys()):
                    if bot_quantity == 0:
                        break
                    if market_sell_price > bot_price:
                        break

                    available = market_sells[market_sell_price]
                    filled = min(bot_quantity, available)

                    if filled > 0:
                        market_sells[market_sell_price] -= filled
                        bot_quantity -= filled

                if product in algo_resting_orders:
                    algo_sells = algo_resting_orders[product]["SELL"]
                    for algo_sell_price in sorted(algo_sells.keys()):
                        if bot_quantity == 0:
                            break
                        if algo_sell_price > bot_price:
                            break

                        available = algo_sells.get(algo_sell_price, 0)
                        if available == 0:
                            continue

                        sell_room = int(
                            portfolio.quantity.get(product, 0) + pos_limit[product]
                        )
                        filled = min(bot_quantity, available, sell_room)

                        if filled > 0:
                            portfolio.quantity[product] -= filled
                            portfolio.cash += filled * algo_sell_price
                            algo_sells[algo_sell_price] -= filled
                            bot_quantity -= filled

                if bot_quantity > 0:
                    market_buys = market_orderbook[product]["BUY"]
                    if bot_price in market_buys:
                        market_buys[bot_price] += bot_quantity
                    else:
                        market_buys[bot_price] = bot_quantity

        if "SELL" in sides:
            for bot_price in sorted(sides["SELL"].keys()):
                bot_quantity = sides["SELL"][bot_price]

                market_buys = market_orderbook[product]["BUY"]
                for market_buy_price in sorted(market_buys.keys(), reverse=True):
                    if bot_quantity == 0:
                        break
                    if market_buy_price < bot_price:
                        break

                    available = market_buys[market_buy_price]
                    filled = min(bot_quantity, available)

                    if filled > 0:
                        market_buys[market_buy_price] -= filled
                        bot_quantity -= filled

                if product in algo_resting_orders:
                    algo_buys = algo_resting_orders[product]["BUY"]
                    for algo_buy_price in sorted(algo_buys.keys(), reverse=True):
                        if bot_quantity == 0:
                            break
                        if algo_buy_price < bot_price:
                            break

                        available = algo_buys.get(algo_buy_price, 0)
                        if available == 0:
                            continue

                        buy_room = int(
                            pos_limit[product] - portfolio.quantity.get(product, 0)
                        )
                        filled = min(bot_quantity, available, buy_room)

                        if filled > 0:
                            portfolio.quantity[product] += filled
                            portfolio.cash -= filled * algo_buy_price
                            algo_buys[algo_buy_price] -= filled
                            bot_quantity -= filled

                if bot_quantity > 0:
                    market_sells = market_orderbook[product]["SELL"]
                    if bot_price in market_sells:
                        market_sells[bot_price] += bot_quantity
                    else:
                        market_sells[bot_price] = bot_quantity

    clean_resting_orders(algo_resting_orders)