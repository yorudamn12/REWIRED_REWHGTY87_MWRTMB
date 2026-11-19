"""Business rules: stock check, alternatives, totals, buyer choices, vendor confirm/reject."""

import json
from datetime import date

from app.db import add_message, bot_text, get_inventory

STORE_NAME = "Sharma General Store"
APP_NAME = "ListLens"  # the assistant that sits between buyer and store


def find_alternatives(inventory, original, category, qty):
    """Up to 2 in-stock items from the same category.
    original = the matched inventory item (or None if nothing matched).
    Sort: same brand first, then most words in common with the original name
    (so oil is replaced by oil, not dal), then closest price (or cheapest if there is no original).
    """
    candidates = [
        i for i in inventory
        if i["category"] == category
        and i["stock"] >= qty
        and (original is None or i["id"] != original["id"])
    ]
    if original:
        words = _name_words(original)
        candidates.sort(key=lambda i: (
            i["brand"] != original["brand"],      # False (same brand) sorts first
            -len(words & _name_words(i)),         # more shared words first
            abs(i["price"] - original["price"]),  # then closest price
        ))
    else:
        candidates.sort(key=lambda i: i["price"])
    return candidates[:2]


def _name_words(item):
    """Words in a product name, without the brand. 'Fortune Sunflower Oil 1L' -> {'sunflower', 'oil', '1l'}"""
    brand_words = set(item["brand"].lower().split())
    return {w for w in item["name"].lower().split() if w not in brand_words and w != "&"}


def build_order(conn, order_id, buyer_name, ai_items):
    """Turn AI items into order_items rows, then send summary + choice messages to the buyer."""
    inventory = get_inventory(conn)
    by_id = {i["id"]: i for i in inventory}

    available = []  # for the summary message
    choices = []    # items the buyer must decide on

    for ai in ai_items:
        qty = ai["qty"]
        item = by_id.get(ai["matched_id"])
        alternatives = []
        line_price = 0

        if item and item["stock"] >= qty:
            status = "available"
            line_price = qty * item["price"]
        else:
            status = "out_of_stock" if item else "not_found"
            category = item["category"] if item else ai["category"]
            alternatives = find_alternatives(inventory, item, category, qty)

        cur = conn.execute(
            """INSERT INTO order_items (order_id, raw_text, qty, item_id, status, chosen_item_id, line_price, alternatives_json)
               VALUES (?, ?, ?, ?, ?, NULL, ?, ?)""",
            (order_id, ai["raw_text"], qty, item["id"] if item else None, status, line_price,
             json.dumps([a["id"] for a in alternatives])),
        )
        order_item_id = cur.lastrowid

        if status == "available":
            available.append({"name": item["name"], "qty": qty, "price": line_price})
        else:
            if item:
                text = f"{item['name']} is out of stock. Pick one:"
            else:
                text = f"We don't have \"{ai['raw_text']}\". Pick one:"
            choices.append({
                "order_item_id": order_item_id,
                "text": text,
                "options": [{"item_id": a["id"], "label": a["name"], "price": qty * a["price"]}
                            for a in alternatives],
                "chosen": None,  # filled in when the buyer taps a button
            })

    total = recompute_total(conn, order_id)

    if available:
        add_message(conn, buyer_name, "bot", "summary",
                    {"order_id": order_id, "items": available, "total": total})
    for c in choices:
        add_message(conn, buyer_name, "bot", "choice", c)

    if choices:
        set_status(conn, order_id, "awaiting_buyer")
    else:
        set_status(conn, order_id, "pending_vendor")
        bot_text(conn, buyer_name, f"Sent to store ✅ Total ₹{total:g}. Waiting for confirmation.")


def recompute_total(conn, order_id):
    """Total = sum of line prices of available + replaced items. Saved on the order."""
    total = conn.execute(
        "SELECT COALESCE(SUM(line_price), 0) FROM order_items WHERE order_id = ? AND status IN ('available', 'replaced')",
        (order_id,),
    ).fetchone()[0]
    conn.execute("UPDATE orders SET total = ? WHERE id = ?", (total, order_id))
    return total


def set_status(conn, order_id, status):
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))


def choose(conn, order_item_id, chosen_item_id):
    """Buyer picked an alternative (or None = skip). Returns an error string, or None if OK."""
    oi = conn.execute("SELECT * FROM order_items WHERE id = ?", (order_item_id,)).fetchone()
    if not oi:
        return "Item not found"
    if oi["status"] not in ("out_of_stock", "not_found"):
        return "Already chosen"
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (oi["order_id"],)).fetchone()

    # chosen_label must match the button text on the chat page exactly
    if chosen_item_id is None:
        conn.execute("UPDATE order_items SET status = 'skipped', line_price = 0 WHERE id = ?", (order_item_id,))
        chosen_label = "Skip this item"
    else:
        if chosen_item_id not in json.loads(oi["alternatives_json"] or "[]"):
            return "That option is not allowed"
        alt = conn.execute("SELECT * FROM inventory WHERE id = ?", (chosen_item_id,)).fetchone()
        price = oi["qty"] * alt["price"]
        conn.execute(
            "UPDATE order_items SET status = 'replaced', chosen_item_id = ?, line_price = ? WHERE id = ?",
            (chosen_item_id, price, order_item_id),
        )
        chosen_label = f"{alt['name']} — ₹{price:g}"

    question = _mark_choice_message(conn, order["buyer_name"], order_item_id, chosen_label)
    # Like tapping a quick-reply button in a chat app: the buyer "sends" the label, quoting the question
    add_message(conn, order["buyer_name"], "buyer", "text",
                {"text": chosen_label, "quote": {"title": APP_NAME, "text": question}})
    total = recompute_total(conn, order["id"])

    # Any choices still open for this order?
    still_open = conn.execute(
        "SELECT COUNT(*) FROM order_items WHERE order_id = ? AND status IN ('out_of_stock', 'not_found')",
        (order["id"],),
    ).fetchone()[0]
    if still_open == 0:
        set_status(conn, order["id"], "pending_vendor")
        bot_text(conn, order["buyer_name"], f"Sent to store ✅ Total ₹{total:g}. Waiting for confirmation.")
    return None


def _mark_choice_message(conn, buyer_name, order_item_id, chosen_label):
    """Save the buyer's pick inside the choice message, so buttons stay disabled after a page reload.
    Returns the question text (used for the quoted reply)."""
    rows = conn.execute("SELECT id, payload_json FROM messages WHERE buyer_name = ? AND type = 'choice'",
                        (buyer_name,)).fetchall()
    for r in rows:
        payload = json.loads(r["payload_json"])
        if payload.get("order_item_id") == order_item_id:
            payload["chosen"] = chosen_label
            conn.execute("UPDATE messages SET payload_json = ? WHERE id = ?", (json.dumps(payload), r["id"]))
            return payload["text"]
    return ""


def _final_lines(conn, order_id):
    """Items that will actually be delivered: [(inventory_id, name, qty, line_price)]"""
    rows = conn.execute(
        """SELECT oi.qty, oi.line_price, inv.id AS inv_id, inv.name, inv.stock
           FROM order_items oi
           JOIN inventory inv ON inv.id = (CASE WHEN oi.status = 'replaced' THEN oi.chosen_item_id ELSE oi.item_id END)
           WHERE oi.order_id = ? AND oi.status IN ('available', 'replaced')""",
        (order_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def address_text(order):
    """e.g. 'Flat 204, Block B, Green Meadows Apartments'"""
    return f"Flat {order['flat']}, Block {order['block']}, {order['society']}"


def confirm_order(conn, order_id, delivery_date):
    """Vendor confirms with a delivery date (YYYY-MM-DD).
    Re-check stock, reduce it, tell the buyer. Returns an error string or None."""
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        return "Order not found"
    if order["status"] == "waiting_customer":
        return "Waiting for the customer's reply. Confirm after they answer."
    if order["status"] != "pending_vendor":
        return f"Order is {order['status']}, cannot confirm"
    try:
        day = date.fromisoformat(delivery_date)
    except (TypeError, ValueError):
        return "Please pick a delivery date"
    if day < date.today():
        return "Delivery date cannot be in the past"

    lines = _final_lines(conn, order_id)

    # Add up qty per product (the same product could appear twice in one list)
    need = {}
    for line in lines:
        need[line["inv_id"]] = need.get(line["inv_id"], 0) + line["qty"]
    for line in lines:
        if line["stock"] < need[line["inv_id"]]:
            return f"Not enough stock for {line['name']} (have {line['stock']}, need {need[line['inv_id']]})"

    for inv_id, qty in need.items():
        conn.execute("UPDATE inventory SET stock = stock - ? WHERE id = ?", (qty, inv_id))
    conn.execute("UPDATE orders SET status = 'confirmed', delivery_date = ? WHERE id = ?",
                 (day.isoformat(), order_id))

    item_list = "\n".join(f"• {l['name']} x{l['qty']} — ₹{l['line_price']:g}" for l in lines)
    nice_day = day.strftime("%a, %d %b")  # e.g. Fri, 20 Nov
    bot_text(conn, order["buyer_name"],
             f"✅ Order confirmed by {STORE_NAME}. Total ₹{order['total']:g}.\n"
             f"🚚 Delivery on {nice_day} to {address_text(order)}.\n{item_list}")
    return None


def reject_order(conn, order_id, reason):
    """Vendor rejects with a reason. Returns an error string or None."""
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        return "Order not found"
    # Rejecting is also allowed while waiting for the customer's reply (in case they never answer)
    if order["status"] not in ("pending_vendor", "waiting_customer"):
        return f"Order is {order['status']}, cannot reject"
    set_status(conn, order_id, "rejected")
    bot_text(conn, order["buyer_name"], f"❌ Order rejected: {reason or 'No reason given'}")
    return None
