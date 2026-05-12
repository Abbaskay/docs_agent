_FAKE_ORDERS = {
    "HZ001": {
        "status": "delivered",
        "customer": "Alice",
        "items": "Pizza, Coke",
        "total": "$18.50",
        "eta": "Delivered on time",
    },
    "HZ002": {
        "status": "in_transit",
        "customer": "Bob",
        "items": "Burger, Fries",
        "total": "$12.00",
        "eta": "10 minutes",
    },
    "HZ003": {
        "status": "preparing",
        "customer": "Charlie",
        "items": "Sushi, Miso Soup",
        "total": "$24.00",
        "eta": "25 minutes",
    },
}


def escalate_to_human(order_id: str, issue_summary: str) -> str:
    return (
        f"[TICKET CREATED] Order {order_id} has been escalated to a human agent. "
        f"Issue: {issue_summary}. A support representative will follow up shortly."
    )


def get_eta(order_id: str) -> str:
    order = _FAKE_ORDERS.get(order_id)
    if not order:
        return f"Order {order_id} not found."
    return f"Order {order_id} ETA: {order['eta']}"


def get_order_status(order_id: str) -> str:
    order = _FAKE_ORDERS.get(order_id)
    if not order:
        return f"Order {order_id} not found."
    return (
        f"Order {order_id}: {order['status'].replace('_', ' ').title()}\n"
        f"Customer: {order['customer']}\n"
        f"Items: {order['items']}\n"
        f"Total: {order['total']}"
    )


def request_refund(order_id: str, reason: str) -> str:
    order = _FAKE_ORDERS.get(order_id)
    if not order:
        return f"Order {order_id} not found. Cannot process refund."
    return (
        f"[REFUND INITIATED] Order {order_id} ({order['total']}) refund requested. "
        f"Reason: {reason}. Refund ID: RFD-{order_id}. Please allow 5-7 business days."
    )
