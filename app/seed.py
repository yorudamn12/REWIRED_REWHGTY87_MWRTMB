"""Seed inventory for the demo store (Sharma General Store). Prices are demo prices in INR.

Each row: (name, brand, category, unit, price, stock)
"""

SEED_ITEMS = [
    # ---- personal_care ----
    ("Head & Shoulders Anti-Dandruff Shampoo 340ml", "Head & Shoulders", "personal_care", "bottle", 399, 0),  # MUST be 0 for demo
    ("Clinic Plus Anti-Dandruff Shampoo 340ml", "Clinic Plus", "personal_care", "bottle", 245, 12),
    ("Head & Shoulders Smooth & Silky Shampoo 340ml", "Head & Shoulders", "personal_care", "bottle", 389, 8),
    ("Dove Soap 3-pack", "Dove", "personal_care", "pack", 180, 15),
    ("Colgate Toothpaste 200g", "Colgate", "personal_care", "tube", 110, 20),
    ("Pears Soap 3-pack", "Pears", "personal_care", "pack", 165, 10),

    # ---- staples ----
    ("Aashirvaad Atta 5kg", "Aashirvaad", "staples", "bag", 295, 25),
    ("India Gate Basmati Rice 5kg", "India Gate", "staples", "bag", 650, 10),
    ("Tata Toor Dal 1kg", "Tata", "staples", "pack", 165, 18),
    ("Tata Sugar 1kg", "Tata", "staples", "pack", 50, 30),
    ("Fortune Sunflower Oil 1L", "Fortune", "staples", "bottle", 155, 2),  # LOW STOCK for demo
    ("Saffola Gold Oil 1L", "Saffola", "staples", "bottle", 210, 9),
    ("Tata Salt 1kg", "Tata", "staples", "pack", 28, 40),
    ("MDH Jeera 100g", "MDH", "staples", "pack", 75, 14),
    ("Everest Turmeric 100g", "Everest", "staples", "pack", 45, 16),
    ("Everest Coriander Powder 100g", "Everest", "staples", "pack", 40, 12),

    # ---- dairy ----
    ("Amul Butter 100g", "Amul", "dairy", "pack", 60, 20),
    ("Amul Taaza Milk 1L", "Amul", "dairy", "pack", 68, 30),
    ("Nandini Curd 500g", "Nandini", "dairy", "pack", 30, 15),
    ("Amul Cheese Slices", "Amul", "dairy", "pack", 140, 8),
    ("Amul Pure Ghee 1L", "Amul", "dairy", "pack", 650, 6),

    # ---- cleaning ----
    ("Surf Excel 1kg", "Surf Excel", "cleaning", "pack", 210, 12),
    ("Vim Bar 3-pack", "Vim", "cleaning", "pack", 60, 25),
    ("Harpic 500ml", "Harpic", "cleaning", "bottle", 105, 10),
    ("Lizol 500ml", "Lizol", "cleaning", "bottle", 120, 9),

    # ---- snacks ----
    ("Parle-G 800g", "Parle", "snacks", "pack", 90, 22),
    ("Maggi 12-pack", "Maggi", "snacks", "pack", 168, 14),
    ("Haldiram Bhujia 400g", "Haldiram", "snacks", "pack", 110, 11),
    ("Britannia Good Day", "Britannia", "snacks", "pack", 40, 35),
    ("Lay's Classic Salted 90g", "Lay's", "snacks", "pack", 50, 18),

    # ---- beverages ----
    ("Tata Tea Gold 500g", "Tata", "beverages", "pack", 285, 10),
    ("Bru Coffee 100g", "Bru", "beverages", "jar", 190, 7),
    ("Red Label Tea 500g", "Red Label", "beverages", "pack", 260, 12),

    # ---- other ----
    ("Good Knight Refill", "Good Knight", "other", "pack", 85, 10),
    ("Classmate Notebook", "Classmate", "other", "piece", 60, 20),
]
