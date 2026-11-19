# ListLens

**Snap your grocery list. We turn it into an order.**

ListLens turns a photo or screenshot of a grocery list into a ready order for the local store.
AI reads the list, matches every line to the store's **live inventory**, and the customer picks
replacements for anything out of stock. The store owner confirms or rejects the order on a
dashboard, and stock updates live.

Demo store: **Sharma General Store** (fictional).

---

## The problem

In Indian housing societies, people often order groceries by sending the local kirana store a
photo of a handwritten list or a typed list in a chat. The shopkeeper then has to:

- read every list by hand (mixed Hindi/English, short forms like "cheeni 2kg", "Amul butter x2"),
- check the shelf for each item,
- message back and forth about items that are out of stock,
- and keep stock numbers up to date by hand.

It is slow and error-prone, and the customer doesn't know what is available or what the total
is until the shop replies.

## The solution

ListLens sits between the customer and the store:

```
Customer (chat)  <-->  ListLens bot (AI)  <-->  Store owner (dashboard + phone alerts)
```

1. The customer sends a list photo in a familiar chat screen.
2. Google Gemini reads the list and matches each line to a real product in stock
   (it understands Hindi words — every product has a Hindi name).
3. Available items are added straight away with prices and a total.
4. For out-of-stock or unknown items, the bot offers up to 2 **similar** products
   (shampoo → another shampoo) or "Skip this item". If the store sells nothing similar, only Skip is shown.
5. The finished order goes to the store dashboard, and the owner's phone gets an alert.
6. The owner can open the chat and ask the customer a question — the order is **held**
   until the customer replies (human in the loop).
7. The owner sets a delivery date and confirms (stock is reduced automatically) or rejects with a reason.

---

## Features

### Customer chat — `/`
- First-time sign-up inside the chat: name, society (list), block, flat number.
- Send a list photo from gallery or camera, with a preview.
- Order summary, alternative buttons, quoted replies, store owner messages, delivery confirmation.
- Logo profile picture with a verified badge.
- Type **`/resetchatgrocery`** to wipe this chat and start again as a new customer.

### Store dashboard — `/vendor`
- **Orders:** stat cards (need your OK, waiting for reply, confirmed today, today's sales,
  low stock), search, filters, item-by-item view (what was written → what was matched),
  confirm with delivery date, reject with reason, view and join the chat,
  delete one order or **delete all orders** (inventory is not changed — sold stock stays sold).
- **Inventory:** 239 products with SKU codes and Hindi names, add item, edit price,
  stock +/− and quick restock +10, low/out-of-stock filters, category filter, search, delete.
- Refreshes every 2 seconds.

### Store phone alerts — `/vendor-chat`
- A separate mobile chat screen for the owner's phone.
- Alerts for new orders, customer replies and low stock, with a banner, a beep and an
  "Open order" link.

---

## Architecture

```
 +------------------+    +---------------------+    +--------------------+
 |  Customer chat   |    |  Store dashboard    |    | Store phone alerts |
 |  /  (chat.html)  |    |  /vendor            |    | /vendor-chat       |
 +--------+---------+    +----------+----------+    +---------+----------+
          |  photo, choices, text,  |  orders, confirm,       |  alerts
          |  poll every 2 s         |  reject, inventory,     |  poll every 2 s
          v                         v  chat, poll every 2 s   v
 +-------------------------------------------------------------------------+
 |                  FastAPI backend  (app/main.py)                         |
 |        REST API  +  serves the static pages  +  saves uploaded photos   |
 +--------------+-------------------------------+--------------------------+
                |                               |
                v                               v
 +---------------------------+     +-------------------------------+
 | app/ai.py                 |     | app/logic.py                  |
 | read_list(image)          |---->| match + stock check,          |
 | mock mode OR Gemini API   |     | similar-item suggestions,     |
 +-------------+-------------+     | choices, confirm / reject,    |
               |                   | alerts                        |
               v                   +---------------+---------------+
 +---------------------------+                     |
 | Google Gemini API         |                     v
 | gemini-3.5-flash-lite     |     +-------------------------------+
 +---------------------------+     | SQLite  (listlens.db)         |
                                   | inventory, orders,            |
                                   | order_items, messages         |
                                   +-------------------------------+
```

**How the AI step works:** the photo and the store's inventory list
(`id | name | brand | category | Hindi name`) are sent to Gemini with JSON output turned on.
Gemini returns one entry per list line: `raw_text, qty, matched_id, category`. The server checks
every value (the id must exist, quantity ≥ 1, category from a fixed list), retries once on bad JSON,
and caches answers per image so the same photo never uses the API twice. The raw JSON is printed
in the server console.

**How suggestions work:** a product's "kind" is the last word of its English or Hindi name
(`Fortune Sunflower Oil 1L` → *oil / तेल*). Only products of the same kind are suggested, sorted by
shared words, same brand, then closest price.

### Project structure
```
app/
  main.py      API routes and pages
  ai.py        reads the list image (mock or Gemini)
  logic.py     matching, suggestions, order flow
  db.py        tables, chat messages, store alerts
  seed.py      239 demo products with Hindi names
static/
  chat.html          customer chat
  vendor.html        store dashboard
  vendor_chat.html   store phone alerts
  style.css, vendor.css, logo.svg
requirements.txt
.env.example
```

---

## Run it on Windows

You need **Python 3.10 or newer**.

```powershell
# 1. Get the code and open PowerShell in the project folder
cd ListLens

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install the libraries
pip install -r requirements.txt

# 4. Create your settings file
copy .env.example .env
```

Open `.env` and fill it in:

```
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.5-flash-lite
AI_MODE=gemini
```

Use `AI_MODE=mock` to demo without an API key. A fixed sample list is used, and it shows every case
(available, out of stock, not found).

```powershell
# 5. Start the server
uvicorn app.main:app --reload --port 8000
```

Then open:

| Page | Link |
|---|---|
| Customer chat | http://localhost:8000/ |
| Store dashboard | http://localhost:8000/vendor |
| Store phone alerts | http://localhost:8000/vendor-chat |

**Start fresh:** stop the server, delete `listlens.db`, start again (the inventory is re-created).
To open the pages on a phone on the same Wi-Fi, start with `--host 0.0.0.0` and use the
laptop's IP address instead of `localhost`.

> Never commit `.env` — it holds your API key. It is already in `.gitignore`.

---

## Tech stack

- **Backend:** Python, FastAPI, Uvicorn
- **Database:** SQLite (Python's built-in `sqlite3`)
- **AI:** Google Gemini API (`gemini-3.5-flash-lite`) over REST with `httpx`
- **Frontend:** plain HTML, CSS and vanilla JavaScript (no framework, no build step)
- **Live updates:** polling every 2 seconds

## Limitations and next steps

- Prototype: no login, a single demo store, no payments or delivery tracking.
- The chat is our own web page; it is not connected to any real messaging app.
- Polling instead of push updates.
- Next: official business-messaging integration, multiple stores, UPI payment link,
  editing items inside an order, voice and regional-language lists, sales reports.

---

## Declarations

Libraries and services used:

- [FastAPI](https://fastapi.tiangolo.com/)
- [Uvicorn](https://www.uvicorn.org/)
- [httpx](https://www.python-httpx.org/)
- [python-dotenv](https://github.com/theskumar/python-dotenv)
- [python-multipart](https://github.com/Kludex/python-multipart)
- SQLite (via Python's built-in `sqlite3`)
- Google Gemini API, model **`gemini-3.5-flash-lite`**

Code written with AI assistance (Claude Code).

The store, societies, customers and prices in the demo are fictional. No third-party logos
are used in the interface.
