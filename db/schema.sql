-- PaldoDamdA OS schema (SQLite)

CREATE TABLE IF NOT EXISTS suppliers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  platform TEXT,
  website_url TEXT,
  order_url TEXT,
  address TEXT,
  contact_name TEXT,
  phone TEXT,
  kakao TEXT,
  default_shipping_fee INTEGER,
  jeju_available TEXT,
  jeju_extra_fee INTEGER,
  island_available TEXT,
  island_extra_fee INTEGER,
  order_deadline TEXT,
  memo TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  supplier_id INTEGER,
  file_name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_type TEXT,
  received_date TEXT,
  sheet_name TEXT,
  table_index INTEGER,
  parsed_status TEXT,
  row_count INTEGER,
  memo TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS raw_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  supplier_id INTEGER,
  source_file_id INTEGER,
  raw_product_name TEXT,
  raw_order_name TEXT,
  raw_option TEXT,
  raw_price TEXT,
  raw_origin TEXT,
  raw_memo TEXT,
  raw_status TEXT,
  raw_shipping TEXT,
  raw_json TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
  FOREIGN KEY (source_file_id) REFERENCES source_files(id)
);

CREATE TABLE IF NOT EXISTS standard_products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_code TEXT UNIQUE,
  standard_name TEXT NOT NULL,
  category TEXT,
  subcategory TEXT,
  season_start TEXT,
  season_end TEXT,
  memo TEXT
);

CREATE TABLE IF NOT EXISTS product_offers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  raw_item_id INTEGER,
  supplier_id INTEGER,
  standard_product_id INTEGER,
  standard_name TEXT,
  attributes TEXT,
  cultivation_type TEXT,
  quality_grade TEXT,
  package_type TEXT,
  weight_value REAL,
  weight_unit TEXT,
  quantity_value INTEGER,
  quantity_unit TEXT,
  option_text TEXT,
  origin TEXT,
  price INTEGER,
  shipping_fee INTEGER,
  jeju_available TEXT,
  jeju_extra_fee INTEGER,
  island_available TEXT,
  island_extra_fee INTEGER,
  status TEXT,
  first_ship_date TEXT,
  file_date TEXT,
  match_confidence REAL,
  needs_review INTEGER DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (raw_item_id) REFERENCES raw_items(id),
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
  FOREIGN KEY (standard_product_id) REFERENCES standard_products(id)
);

CREATE TABLE IF NOT EXISTS product_aliases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alias TEXT NOT NULL,
  standard_product_id INTEGER,
  standard_name TEXT NOT NULL,
  attributes_hint TEXT,
  confidence REAL DEFAULT 1.0,
  memo TEXT,
  FOREIGN KEY (standard_product_id) REFERENCES standard_products(id)
);

CREATE INDEX IF NOT EXISTS idx_raw_items_name ON raw_items(raw_product_name);
CREATE INDEX IF NOT EXISTS idx_offers_standard_name ON product_offers(standard_name);
CREATE INDEX IF NOT EXISTS idx_offers_price ON product_offers(price);
CREATE INDEX IF NOT EXISTS idx_aliases_alias ON product_aliases(alias);
