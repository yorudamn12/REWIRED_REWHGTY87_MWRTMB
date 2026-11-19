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
from app.db import add_message, bot_text, get_conn, get_inventory, init_db, now

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


@app.get("/api/config")
def config():
    return {"mode": ai.AI_MODE}


# ---------- Buyer side ----------

@app.post("/api/upload")
def upload(image: UploadFile = File(...), buyer_name: str = Form(...), flat: str = Form(...)):
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
            "INSERT INTO orders (buyer_name, flat, status, total, image_path, created_at) VALUES (?, ?, 'reading', 0, ?, ?)",
            (buyer_name, flat, image_url, now()),
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
    """Buyer typed a normal text message. The bot only understands photos, so it replies with a hint."""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Empty message")
    conn = get_conn()
    add_message(conn, body.buyer_name, "buyer", "text", {"text": text})
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
        result.append({**dict(o), "items": items})
    conn.close()
    return result


@app.post("/api/vendor/orders/{order_id}/confirm")
def confirm(order_id: int):
    conn = get_conn()
    try:
        error = logic.confirm_order(conn, order_id)
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


@app.get("/api/inventory")
def inventory():
    conn = get_conn()
    items = get_inventory(conn)
    conn.close()
    return items
