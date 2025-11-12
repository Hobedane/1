import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path="store_bot.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Products table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price REAL NOT NULL,
                    description TEXT,
                    quantity INTEGER NOT NULL,
                    image1 TEXT,
                    image2 TEXT,
                    coordinates TEXT,
                    active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Content table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS content (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Payment settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payment_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    currency_code TEXT UNIQUE NOT NULL,
                    address TEXT NOT NULL,
                    blockchain TEXT NOT NULL
                )
            ''')
            
            # Discount codes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS discount_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    discount_percentage REAL NOT NULL,
                    expiry_date DATE,
                    max_uses INTEGER DEFAULT -1,
                    used_count INTEGER DEFAULT 0,
                    is_general BOOLEAN DEFAULT TRUE,
                    client_id INTEGER,
                    client_username TEXT,
                    active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Orders table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    user_name TEXT,
                    product_id INTEGER,
                    product_name TEXT,
                    quantity INTEGER NOT NULL,
                    total_price REAL NOT NULL,
                    order_id TEXT UNIQUE NOT NULL,
                    payment_currency TEXT,
                    payment_source_address TEXT,
                    discount_code TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Cart table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cart (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, product_id)
                )
            ''')
            
            # Insert default content
            default_content = [
                ('welcome_message', 'Hello! 👋 I am your store bot.\n\nChoose from the options below:'),
                ('about_us', 'This is our store. We sell quality products with crypto payments.'),
                ('contact', 'Contact us: @admin'),
                ('website', 'https://example.com'),
                ('rules', 'Store rules:\n1. Be respectful\n2. No refunds'),
                ('faq', 'Frequently Asked Questions:\nQ: How to pay?\nA: Use crypto payments.'),
                ('success_message', 'Thank you for your purchase! Admin will contact you soon.')
            ]
            
            cursor.executemany(
                'INSERT OR IGNORE INTO content (key, value) VALUES (?, ?)',
                default_content
            )
            
            # Insert default payment methods
            default_payments = [
                ('btc', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', 'Bitcoin'),
                ('eth', '0x742d35Cc6634C0532925a3b8D4B3b8a3b8d4b3b8', 'Ethereum'),
                ('sol', 'So1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', 'Solana'),
                ('ltc', 'Lc1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', 'Litecoin'),
                ('usdt', '0x842d35Cc6634C0532925a3b8D4B3b8a3b8d4b3b8', 'Ethereum')
            ]
            
            cursor.executemany(
                'INSERT OR IGNORE INTO payment_settings (currency_code, address, blockchain) VALUES (?, ?, ?)',
                default_payments
            )
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    def get_connection(self):
        return sqlite3.connect(self.db_path)

# Create global database instance
db = Database()
