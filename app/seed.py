"""Seed inventory for the demo store (Sharma General Store). Prices are demo prices in INR.

Each row: (name, brand, category, unit, price, stock)
HINDI gives the Hindi name shown under each product (also helps the AI match Hindi lists).
SKU codes are generated automatically from the category + id (see db.make_sku).
"""

SEED_ITEMS = [
    # ---- personal_care ----
    ("Head & Shoulders Anti-Dandruff Shampoo 340ml", "Head & Shoulders", "personal_care", "bottle", 399, 0),  # MUST be 0 for demo
    ("Clinic Plus Anti-Dandruff Shampoo 340ml", "Clinic Plus", "personal_care", "bottle", 245, 12),
    ("Head & Shoulders Smooth & Silky Shampoo 340ml", "Head & Shoulders", "personal_care", "bottle", 389, 8),
    ("Dove Soap 3-pack", "Dove", "personal_care", "pkt", 180, 15),
    ("Colgate Toothpaste 200g", "Colgate", "personal_care", "tube", 110, 20),
    ("Pears Soap 3-pack", "Pears", "personal_care", "pkt", 165, 10),

    # ---- staples ----
    ("Aashirvaad Atta 5kg", "Aashirvaad", "staples", "bag", 295, 25),
    ("India Gate Basmati Rice 5kg", "India Gate", "staples", "bag", 650, 10),
    ("Tata Toor Dal 1kg", "Tata", "staples", "pkt", 165, 18),
    ("Tata Sugar 1kg", "Tata", "staples", "pkt", 50, 30),
    ("Fortune Sunflower Oil 1L", "Fortune", "staples", "pouch", 155, 2),  # LOW STOCK for demo
    ("Saffola Gold Oil 1L", "Saffola", "staples", "bottle", 210, 9),
    ("Tata Salt 1kg", "Tata", "staples", "pkt", 28, 40),
    ("MDH Jeera 100g", "MDH", "staples", "pkt", 75, 14),
    ("Everest Turmeric 100g", "Everest", "staples", "pkt", 45, 16),
    ("Everest Coriander Powder 100g", "Everest", "staples", "pkt", 40, 12),

    # ---- dairy ----
    ("Amul Butter 100g", "Amul", "dairy", "pkt", 60, 20),
    ("Amul Taaza Milk 1L", "Amul", "dairy", "pouch", 68, 30),
    ("Nandini Curd 500g", "Nandini", "dairy", "pouch", 30, 15),
    ("Amul Cheese Slices", "Amul", "dairy", "pkt", 140, 8),
    ("Amul Pure Ghee 1L", "Amul", "dairy", "box", 650, 6),

    # ---- cleaning ----
    ("Surf Excel 1kg", "Surf Excel", "cleaning", "pkt", 210, 12),
    ("Vim Bar 3-pack", "Vim", "cleaning", "pkt", 60, 25),
    ("Harpic 500ml", "Harpic", "cleaning", "bottle", 105, 10),
    ("Lizol 500ml", "Lizol", "cleaning", "bottle", 120, 9),

    # ---- snacks ----
    ("Parle-G 800g", "Parle", "snacks", "pkt", 90, 22),
    ("Maggi 12-pack", "Maggi", "snacks", "pkt", 168, 14),
    ("Haldiram Bhujia 400g", "Haldiram", "snacks", "pkt", 110, 11),
    ("Britannia Good Day", "Britannia", "snacks", "pkt", 40, 35),
    ("Lay's Classic Salted 90g", "Lay's", "snacks", "pkt", 50, 18),

    # ---- beverages ----
    ("Tata Tea Gold 500g", "Tata", "beverages", "pkt", 285, 10),
    ("Bru Coffee 100g", "Bru", "beverages", "jar", 190, 7),
    ("Red Label Tea 500g", "Red Label", "beverages", "box", 260, 12),

    # ---- other ----
    ("Good Knight Refill", "Good Knight", "other", "box", 85, 10),
    ("Classmate Notebook", "Classmate", "other", "piece", 60, 20),
]

HINDI = {
    "Head & Shoulders Anti-Dandruff Shampoo 340ml": "हेड एंड शोल्डर्स शैम्पू",
    "Clinic Plus Anti-Dandruff Shampoo 340ml": "क्लिनिक प्लस शैम्पू",
    "Head & Shoulders Smooth & Silky Shampoo 340ml": "हेड एंड शोल्डर्स शैम्पू",
    "Dove Soap 3-pack": "डव साबुन",
    "Colgate Toothpaste 200g": "कोलगेट टूथपेस्ट",
    "Pears Soap 3-pack": "पियर्स साबुन",
    "Aashirvaad Atta 5kg": "आशीर्वाद आटा",
    "India Gate Basmati Rice 5kg": "बासमती चावल",
    "Tata Toor Dal 1kg": "तूर दाल / अरहर",
    "Tata Sugar 1kg": "चीनी",
    "Fortune Sunflower Oil 1L": "सूरजमुखी तेल",
    "Saffola Gold Oil 1L": "सफोला तेल",
    "Tata Salt 1kg": "नमक",
    "MDH Jeera 100g": "जीरा",
    "Everest Turmeric 100g": "हल्दी",
    "Everest Coriander Powder 100g": "धनिया पाउडर",
    "Amul Butter 100g": "मक्खन",
    "Amul Taaza Milk 1L": "दूध",
    "Nandini Curd 500g": "दही",
    "Amul Cheese Slices": "चीज़",
    "Amul Pure Ghee 1L": "घी",
    "Surf Excel 1kg": "सर्फ एक्सेल पाउडर",
    "Vim Bar 3-pack": "विम बार",
    "Harpic 500ml": "हार्पिक",
    "Lizol 500ml": "लिज़ोल",
    "Parle-G 800g": "पारले-जी बिस्कुट",
    "Maggi 12-pack": "मैगी नूडल्स",
    "Haldiram Bhujia 400g": "भुजिया",
    "Britannia Good Day": "गुड डे बिस्कुट",
    "Lay's Classic Salted 90g": "लेज़ चिप्स",
    "Tata Tea Gold 500g": "चाय पत्ती",
    "Bru Coffee 100g": "कॉफ़ी",
    "Red Label Tea 500g": "रेड लेबल चाय",
    "Good Knight Refill": "गुड नाइट रिफिल",
    "Classmate Notebook": "कॉपी",
}
