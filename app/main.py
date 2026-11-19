"""ListLens FastAPI app: all HTTP routes live here.

Run with:  uvicorn app.main:app --reload
"""

import json
import sys
import time
from pathlib import Path

# Windows consoles can crash on emoji/Hindi text in print(); replace unknown characters instead
sys.stdout.reconfigure(errors="replace")

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import ai, logic
from app.db import add_message, bot_text, get_conn, get_inventory, init_db, make_sku, notify_store, now

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

init_db()  # create tables + seed inventory on startup

app = FastAPI(title="ListLens")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ---------- Pages ----------

@app.get("/")
def home():
    return RedirectResponse("/static/chat.html")


@app.get("/vendor")
def vendor_page():
    return RedirectResponse("/static/vendor.html")


@app.get("/vendor-chat")
def vendor_chat_page():
    """The store owner's phone view: ListLens order alerts."""
    return RedirectResponse("/static/vendor_chat.html")


# Example housing societies served by the store (shown as a dropdown on sign-up)
SOCIETIES = [
    "Green Meadows Apartments",
    "Sunrise Heights",
    "Lakeview Residency",
    "Palm Grove Enclave",
    "Silver Oak Towers",
]
BLOCKS = ["A", "B", "C", "D", "E", "F"]
UNITS = ["pkt", "pouch", "box", "bottle", "bag", "jar", "tube", "piece", "kg", "L"]


@app.get("/api/config")
def config():
    return {"mode": ai.AI_MODE, "societies": SOCIETIES, "blocks": BLOCKS,
            "categories": ai.CATEGORIES, "units": UNITS, "low_stock": logic.LOW_STOCK}


# ---------- Buyer side ----------

@app.post("/api/upload")
def upload(image: UploadFile = File(...), buyer_name: str = Form(...), flat: str = Form(...),
           society: str = Form(""), block: str = Form("")):
    """Buyer sends a screenshot. We save it, read it with AI, and reply in the chat."""
    # 1. Save the image file with a unique name
    ext = Path(image.filename or "").suffix.lower() or ".jpg"
    filename = f"{int(time.time() * 1000)}{ext}"
    image_bytes = image.file.read()
    (UPLOAD_DIR / filename).write_bytes(image_bytes)
    image_url = f"/uploads/{filename}"

    conn = get_conn()
    try:
        # 2. Create the order (status "reading") and show the image in the chat
        cur = conn.execute(
            """INSERT INTO orders (buyer_name, flat, society, block, status, total, image_path, created_at)
               VALUES (?, ?, ?, ?, 'reading', 0, ?, ?)""",
            (buyer_name, flat, society, block, image_url, now()),
        )
        order_id = cur.lastrowid
        add_message(conn, buyer_name, "buyer", "image", {"url": image_url})
        conn.commit()  # commit now so the chat page shows the image while AI is working

        # 3. Ask AI to read the list
        try:
            items = ai.read_list(image_bytes, image.content_type or "image/jpeg", get_inventory(conn))
        except Exception as e:
            print(f"[upload] AI failed: {e}")
            logic.set_status(conn, order_id, "failed")
            bot_text(conn, buyer_name, "Couldn't read this right now, please try again.")
            conn.commit()
            return {"order_id": order_id, "status": "failed"}

        if not items:
            logic.set_status(conn, order_id, "failed")
            bot_text(conn, buyer_name, "I couldn't find any grocery items in this picture.")
            conn.commit()
            return {"order_id": order_id, "status": "failed"}

        # 4. Match stock, find alternatives, send summary + choices
        logic.build_order(conn, order_id, buyer_name, items)
        conn.commit()
        status = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()[0]
        return {"order_id": order_id, "status": status}
    finally:
        conn.close()


@app.get("/api/messages")
def messages(buyer: str, after: int = 0):
    """Chat messages for one buyer with id greater than `after` (used for polling)."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM messages WHERE buyer_name = ? AND id > ? ORDER BY id", (buyer, after)
    ).fetchall()
    conn.close()
    return [{
        "id": r["id"], "sender": r["sender"], "type": r["type"],
        "payload": json.loads(r["payload_json"]), "created_at": r["created_at"],
    } for r in rows]


class TextBody(BaseModel):
    buyer_name: str
    text: str


@app.post("/api/text")
def send_text(body: TextBody):
    """Buyer typed a normal text message.
    - If the store asked a question (order is 'waiting_customer'), this is the answer:
      the order goes back to the vendor ('pending_vendor') so they can decide.
    - If any other order is still open, the message is for the store owner, so the bot stays quiet.
    - Otherwise the bot replies with a hint to send a photo."""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Empty message")
    conn = get_conn()
    add_message(conn, body.buyer_name, "buyer", "text", {"text": text})
    waiting = conn.execute(
        "SELECT id FROM orders WHERE buyer_name = ? AND status = 'waiting_customer'", (body.buyer_name,)
    ).fetchall()
    for o in waiting:
        logic.set_status(conn, o["id"], "pending_vendor")
        notify_store(conn, f"💬 {body.buyer_name} replied on order #{o['id']}:\n“{text}”", o["id"])
    open_order = conn.execute(
        "SELECT 1 FROM orders WHERE buyer_name = ? AND status IN ('awaiting_buyer', 'pending_vendor')",
        (body.buyer_name,),
    ).fetchone()
    if not open_order:
        bot_text(conn, body.buyer_name, "Hi! 👋 Please send a photo or screenshot of your grocery list 📷 and I'll prepare your order.")
    conn.commit()
    conn.close()
    return {"ok": True}


class ChooseBody(BaseModel):
    order_item_id: int
    chosen_item_id: int | None = None  # None means "Skip"


@app.post("/api/choose")
def choose(body: ChooseBody):
    conn = get_conn()
    try:
        error = logic.choose(conn, body.order_item_id, body.chosen_item_id)
        if error:
            raise HTTPException(400, error)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ---------- Vendor side ----------

@app.get("/api/vendor/orders")
def vendor_orders():
    """All orders (except failed ones), newest first, each with its items."""
    conn = get_conn()
    orders = conn.execute("SELECT * FROM orders WHERE status != 'failed' ORDER BY id DESC").fetchall()
    names = {i["id"]: i["name"] for i in get_inventory(conn)}
    result = []
    for o in orders:
        rows = conn.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (o["id"],)).fetchall()
        items = []
        for r in rows:
            # Show the replacement name if the buyer picked one, else the matched name
            shown_id = r["chosen_item_id"] if r["status"] == "replaced" else r["item_id"]
            items.append({
                "raw_text": r["raw_text"],
                "matched_name": names.get(shown_id),
                "original_name": names.get(r["item_id"]),
                "qty": r["qty"],
                "price": r["line_price"],
                "status": r["status"],
            })
        # Who spoke last in this buyer's chat, and did the store ever step in?
        # Used to show "Customer replied" on the dashboard.
        last = conn.execute(
            "SELECT sender FROM messages WHERE buyer_name = ? ORDER BY id DESC LIMIT 1", (o["buyer_name"],)
        ).fetchone()
        store_spoke = conn.execute(
            "SELECT 1 FROM messages WHERE buyer_name = ? AND sender = 'vendor'", (o["buyer_name"],)
        ).fetchone()
        result.append({**dict(o), "items": items,
                       "customer_replied": bool(store_spoke) and last is not None and last["sender"] == "buyer"})
    conn.close()
    return result


class ConfirmBody(BaseModel):
    delivery_date: str = ""  # YYYY-MM-DD, picked by the vendor


@app.post("/api/vendor/orders/{order_id}/confirm")
def confirm(order_id: int, body: ConfirmBody):
    conn = get_conn()
    try:
        error = logic.confirm_order(conn, order_id, body.delivery_date)
        if error:
            raise HTTPException(400, error)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


class RejectBody(BaseModel):
    reason: str = ""


@app.post("/api/vendor/orders/{order_id}/reject")
def reject(order_id: int, body: RejectBody):
    conn = get_conn()
    try:
        error = logic.reject_order(conn, order_id, body.reason.strip())
        if error:
            raise HTTPException(400, error)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


class VendorMessageBody(BaseModel):
    buyer_name: str
    text: str
    order_id: int | None = None  # the order the vendor is looking at


@app.post("/api/vendor/message")
def vendor_message(body: VendorMessageBody):
    """Human intervention: the shop owner types directly into the buyer's chat.
    If that order was waiting for the vendor's OK, it is put on hold until the customer replies."""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Empty message")
    conn = get_conn()
    add_message(conn, body.buyer_name, "vendor", "text", {"text": text})
    if body.order_id:
        conn.execute(
            "UPDATE orders SET status = 'waiting_customer' WHERE id = ? AND status = 'pending_vendor'",
            (body.order_id,),
        )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/inventory")
def inventory():
    conn = get_conn()
    items = get_inventory(conn)
    conn.close()
    return items


class NewItemBody(BaseModel):
    name: str
    hindi_name: str = ""
    brand: str = ""
    category: str
    unit: str = "pkt"
    price: float
    stock: int


@app.post("/api/inventory")
def add_item(body: NewItemBody):
    """Vendor adds a new product. The SKU code is created automatically."""
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Name is required")
    if body.category not in ai.CATEGORIES:
        raise HTTPException(400, "Unknown category")
    if body.price <= 0 or body.stock < 0:
        raise HTTPException(400, "Price must be above 0 and stock cannot be negative")
    brand = body.brand.strip() or name.split()[0]  # no brand given -> use the first word ("MDH Haldi" -> "MDH")
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO inventory (name, brand, category, unit, price, stock, hindi_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, brand, body.category, body.unit.strip() or "pkt", body.price, body.stock, body.hindi_name.strip()),
    )
    sku = make_sku(body.category, cur.lastrowid)
    conn.execute("UPDATE inventory SET sku = ? WHERE id = ?", (sku, cur.lastrowid))
    conn.commit()
    conn.close()
    return {"ok": True, "id": cur.lastrowid, "sku": sku}


class UpdateItemBody(BaseModel):
    price: float | None = None      # new price
    stock_delta: int | None = None  # +1 / -1 from the stepper, +10 from "Quick restock"


@app.patch("/api/inventory/{item_id}")
def update_item(item_id: int, body: UpdateItemBody):
    """Change price and/or stock of one product. Stock never goes below 0."""
    conn = get_conn()
    try:
        if not conn.execute("SELECT 1 FROM inventory WHERE id = ?", (item_id,)).fetchone():
            raise HTTPException(404, "Item not found")
        if body.price is not None:
            if body.price <= 0:
                raise HTTPException(400, "Price must be above 0")
            conn.execute("UPDATE inventory SET price = ? WHERE id = ?", (body.price, item_id))
        if body.stock_delta is not None:
            conn.execute("UPDATE inventory SET stock = MAX(0, stock + ?) WHERE id = ?", (body.stock_delta, item_id))
        conn.commit()
        return dict(conn.execute("SELECT * FROM inventory WHERE id = ?", (item_id,)).fetchone())
    finally:
        conn.close()


@app.delete("/api/inventory/{item_id}")
def delete_item(item_id: int):
    """Remove a product. Not allowed while it is part of an order that is still open."""
    conn = get_conn()
    try:
        in_use = conn.execute(
            """SELECT 1 FROM order_items oi JOIN orders o ON o.id = oi.order_id
               WHERE (oi.item_id = ? OR oi.chosen_item_id = ?)
                 AND o.status IN ('reading', 'awaiting_buyer', 'pending_vendor', 'waiting_customer')""",
            (item_id, item_id),
        ).fetchone()
        if in_use:
            raise HTTPException(400, "This item is in an open order. Confirm or reject that order first.")
        conn.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
