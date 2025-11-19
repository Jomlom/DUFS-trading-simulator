from typing import Dict, List
from datamodel import Order, Portfolio

def match_order(
    algo_orders: List[Order],
    orderbook: Dict[str, Dict[str, Dict[int, int]]],
    portfolio: Portfolio,
    pos_limit: Dict[str, int],
) -> Dict[str, Dict[str, Dict[int, int]]]:
    """
    Match an order with an order in the orderbook.

    :param order: The order to be matched.
    :param orderbook: The orderbook to match with.
    :param portfolio: The portfolio to be updated.
    :param pos_limit: The maximum quantity the portfolio can hold.
    """

    algo_resting_orders: Dict[str, Dict[str, Dict[int, int]]] = {}

    all_products = set(order.product for order in algo_orders)
    for product in all_products:
        if product not in algo_resting_orders:
            algo_resting_orders[product] = {"BUY": {}, "SELL": {}}

    for order in algo_orders:
        product = order.product
        unfilled_quantity = 0

        if order.quantity > 0:
            unfilled_quantity = match_buy_order(
                order, orderbook[product]["SELL"], portfolio, pos_limit
            )

            if unfilled_quantity > 0:
                price = order.price
                book = algo_resting_orders[product]["BUY"]
                if price in book:
                    book[price] += unfilled_quantity
                else:
                    book[price] = unfilled_quantity

        elif order.quantity < 0:
            unfilled_quantity = match_sell_order(
                order, orderbook[product]["BUY"], portfolio, pos_limit
            )

            if unfilled_quantity < 0:
                price = order.price
                book = algo_resting_orders[product]["SELL"]
                unfilled_abs = -unfilled_quantity
                if price in book:
                    book[price] += unfilled_abs
                else:
                    book[price] = unfilled_abs
        else:
            pass

    return algo_resting_orders


def match_buy_order(
    order: Order,
    sell_orders: Dict[int, int],
    portfolio: Portfolio,
    pos_limit: Dict[str, int],
) -> int:
    product = order.product
    product_limit = pos_limit[product]
    limit_price = order.price
    outstanding_quantity = order.quantity

    for pricepoint in sorted(sell_orders.keys()):
        if outstanding_quantity == 0:
            break

        if pricepoint > limit_price:
            break

        if sell_orders[pricepoint] > 0:
            fulfilled_amount = min(
                int(product_limit - portfolio.quantity.get(product, 0)),
                outstanding_quantity,
                sell_orders[pricepoint],
            )  # quantity before order limit, order quantity remaining, quantity avaliable,

            if fulfilled_amount > 0:
                # Update portfolio
                portfolio.quantity[product] += fulfilled_amount
                portfolio.cash -= fulfilled_amount * pricepoint

                sell_orders[pricepoint] -= fulfilled_amount
                outstanding_quantity -= fulfilled_amount
                # print(f"selling {fulfilled_amount} at {buy_prices[i]}")

    return outstanding_quantity


def match_sell_order(
    order: Order,
    buy_orders: Dict[int, int],
    portfolio: Portfolio,
    pos_limit: Dict[str, int],
) -> int:
    product = order.product
    product_limit = pos_limit[product]
    limit_price = order.price
    outstanding_quantity = order.quantity

    for pricepoint in sorted(buy_orders.keys(), reverse=True):
        if outstanding_quantity == 0:
            break

        if pricepoint < limit_price:
            break

        if buy_orders[pricepoint] > 0:
            fulfilled_amount = min(
                int(product_limit + portfolio.quantity.get(product, 0)),
                -outstanding_quantity,
                buy_orders[pricepoint],
            )  # quantity before order limit, order quantity remaining, quantity avaliable,

            if fulfilled_amount > 0:
                # Update portfolio
                portfolio.quantity[product] -= fulfilled_amount
                portfolio.cash += fulfilled_amount * pricepoint

                buy_orders[pricepoint] -= fulfilled_amount
                outstanding_quantity += fulfilled_amount
                # print(f"selling {fulfilled_amount} at {buy_prices[i]}")

    return outstanding_quantity