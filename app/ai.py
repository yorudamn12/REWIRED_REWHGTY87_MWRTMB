"""Reads a grocery-list screenshot and returns a list of items.

AI_MODE=mock   -> returns a fixed sample list (no API call, no quota used)
AI_MODE=gemini -> sends the image to Google Gemini and asks for JSON back
"""

import base64
import hashlib
import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()  # read settings from the .env file

AI_MODE = os.getenv("AI_MODE", "mock").strip().lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

CATEGORIES = ["staples", "dairy", "personal_care", "cleaning", "snacks", "beverages", "other"]

PROMPT = (
    "You read Indian grocery lists from screenshots or photos (typed, handwritten, WhatsApp chat "
    "screenshots, Hindi/Hinglish/Kannada words). Extract every item the person wants to buy. For each "
    "item return: raw_text (as written), qty (integer number of packs/units, default 1), matched_id (id "
    "from INVENTORY that best matches, else null), category (one of: staples, dairy, personal_care, "
    "cleaning, snacks, beverages, other), confidence (0-1). Map regional words to English (aata->atta, "
    "cheeni->sugar, dhaniya->coriander, haldi->turmeric, doodh->milk). If a specific brand is written and "
    "that exact product exists in inventory, match it even if out of stock (we handle stock separately). "
    "Ignore chat text that is not an item (greetings, names, times). Return ONLY a JSON array."
)

# Sample answer used in mock mode. We match by product name, so ids are looked up at runtime.
MOCK_ITEMS = [
    {"raw_text": "Aashirvaad aata 5kg", "qty": 1, "match_name": "Aashirvaad Atta 5kg", "category": "staples"},
    {"raw_text": "cheeni 2kg", "qty": 2, "match_name": "Tata Sugar 1kg", "category": "staples"},
    {"raw_text": "Head & Shoulders anti dandruff", "qty": 1,
     "match_name": "Head & Shoulders Anti-Dandruff Shampoo 340ml", "category": "personal_care"},  # stock 0
    {"raw_text": "Amul butter x2", "qty": 2, "match_name": "Amul Butter 100g", "category": "dairy"},
    {"raw_text": "Fortune oil 1L", "qty": 1, "match_name": "Fortune Sunflower Oil 1L", "category": "staples"},
    {"raw_text": "kesar 1g", "qty": 1, "match_name": None, "category": "staples"},  # not in inventory
]

# Remember answers by image fingerprint, so the same screenshot never uses the API twice
_cache = {}


class AIError(Exception):
    """Raised when the list could not be read (rate limit, network, bad answer)."""


def read_list(image_bytes, mime_type, inventory):
    """Main entry point. Returns a list of dicts:
    {raw_text, qty, matched_id, category, confidence}
    """
    if AI_MODE == "mock":
        return _mock_items(inventory)

    # Same image bytes -> same SHA-256 -> reuse the earlier answer
    key = hashlib.sha256(image_bytes).hexdigest()
    if key in _cache:
        print("[ai] cache hit, skipping API call")
        return _cache[key]

    items = None
    for attempt in range(2):  # try once, retry once if the JSON is bad
        raw = _call_gemini(image_bytes, mime_type, inventory)
        print(f"[ai] raw model JSON (attempt {attempt + 1}):\n{raw}")
        try:
            items = json.loads(raw)
            if isinstance(items, dict):  # sometimes models wrap the array: {"items": [...]}
                items = next((v for v in items.values() if isinstance(v, list)), None)
            if isinstance(items, list):
                break
        except json.JSONDecodeError:
            pass
        items = None
    if items is None:
        raise AIError("Model did not return a valid JSON list")

    clean = _validate(items, inventory)
    _cache[key] = clean
    return clean


def _call_gemini(image_bytes, mime_type, inventory):
    """Send the image + prompt to Gemini. Returns the model's text (should be JSON)."""
    if not GEMINI_API_KEY:
        raise AIError("GEMINI_API_KEY is not set in .env")

    # Inventory as short lines: "12 | Tata Sugar 1kg | Tata | staples | चीनी"
    inv_lines = "\n".join(
        f"{i['id']} | {i['name']} | {i['brand']} | {i['category']} | {i.get('hindi_name') or ''}" for i in inventory
    )
    prompt = PROMPT + "\n\nINVENTORY:\n" + inv_lines

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}},
                {"text": prompt},
            ]
        }],
        "generationConfig": {"responseMimeType": "application/json"},  # no temperature/top_p/top_k
    }
    try:
        resp = httpx.post(url, headers={"x-goog-api-key": GEMINI_API_KEY}, json=body, timeout=60)
    except httpx.HTTPError as e:
        raise AIError(f"Network error calling Gemini: {e}")

    if resp.status_code == 429:
        raise AIError("Gemini rate limit hit (429). Wait a minute and try again.")
    if resp.status_code != 200:
        raise AIError(f"Gemini error {resp.status_code}: {resp.text[:300]}")

    try:
        parts = resp.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, ValueError):
        raise AIError(f"Unexpected Gemini response: {resp.text[:300]}")


def _validate(items, inventory):
    """Clean up the model's answer so the rest of the code can trust it."""
    valid_ids = {i["id"] for i in inventory}
    clean = []
    for it in items:
        if not isinstance(it, dict) or not it.get("raw_text"):
            continue
        # qty: must be a positive integer, else 1
        try:
            qty = int(it.get("qty") or 1)
        except (TypeError, ValueError):
            qty = 1
        if qty <= 0:
            qty = 1
        # matched_id: must exist in our inventory, else None
        try:
            matched = int(it.get("matched_id")) if it.get("matched_id") is not None else None
        except (TypeError, ValueError):
            matched = None
        if matched not in valid_ids:
            matched = None
        # category: must be from our fixed list, else "other"
        category = it.get("category") if it.get("category") in CATEGORIES else "other"
        clean.append({
            "raw_text": str(it["raw_text"]),
            "qty": qty,
            "matched_id": matched,
            "category": category,
            "confidence": it.get("confidence", 1),
        })
    return clean


def _mock_items(inventory):
    """Build the fixed sample list, looking up real ids by product name."""
    by_name = {i["name"]: i["id"] for i in inventory}
    return [{
        "raw_text": m["raw_text"],
        "qty": m["qty"],
        "matched_id": by_name.get(m["match_name"]),
        "category": m["category"],
        "confidence": 0.95,
    } for m in MOCK_ITEMS]
