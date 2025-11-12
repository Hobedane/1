import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class ClientHandlers:
    def __init__(self, config):
        self.config = config
        self.exchange_rate = config.EXCHANGE_RATE

    def get_content(self, key: str) -> str:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM content WHERE key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "Content not found"

    async def show_products(self, update, context):
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, price, quantity FROM products 
            WHERE active = TRUE AND quantity > 0
            ORDER BY name
        ''')
        products = cursor.fetchall()
        conn.close()
        
        if not products:
            text = "🛍️ Our Products:\n\nNo products available at the moment."
        else:
            text = "🛍️ Our Products:"
        
        keyboard = []
        for product in products:
            product_id, name, price, quantity = product
            button_text = f"{name} - {price}€" if quantity == 1 else f"{name} - {price}€ ({quantity} pcs)"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"product_{product_id}")])
        
        keyboard.append([
            InlineKeyboardButton("🛒 View Cart", callback_data="view_cart"),
            InlineKeyboardButton("🔙 Back", callback_data="main_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_product_detail(self, update, context, product_id: int):
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT name, description, price, quantity FROM products 
            WHERE id = ? AND active = TRUE
        ''', (product_id,))
        product = cursor.fetchone()
        conn.close()
        
        if not product:
            await update.callback_query.edit_message_text("Product not found!")
            return
        
        name, description, price, quantity = product
        
        text = f"""🛍️ {name}

📝 {description}
💰 Price: {price}€
📦 Available: {quantity} pcs"""
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Buy Now", callback_data=f"buy_now_{product_id}"),
                InlineKeyboardButton("🛒 Add to Cart", callback_data=f"add_to_cart_{product_id}")
            ],
            [
                InlineKeyboardButton("🔙 Back to Products", callback_data="browse_products"),
                InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def add_to_cart(self, update, context, product_id: int):
        user_id = update.callback_query.from_user.id
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT name, price, quantity FROM products WHERE id = ? AND active = TRUE', (product_id,))
        product = cursor.fetchone()
        
        if not product:
            await update.callback_query.answer("Product not available!", show_alert=True)
            return
        
        name, price, available_quantity = product
        
        cursor.execute('SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?', (user_id, product_id))
        existing_item = cursor.fetchone()
        
        if existing_item:
            current_quantity = existing_item[0]
            if current_quantity + 1 > available_quantity:
                await update.callback_query.answer("Not enough quantity available!", show_alert=True)
                return
            cursor.execute(
                'UPDATE cart SET quantity = quantity + 1 WHERE user_id = ? AND product_id = ?',
                (user_id, product_id)
            )
        else:
            cursor.execute(
                'INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1)',
                (user_id, product_id)
            )
        
        conn.commit()
        conn.close()
        
        await update.callback_query.answer(f"Added {name} to cart!")

    async def show_cart(self, update, context):
        user_id = update.callback_query.from_user.id
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.product_id, c.quantity, p.name, p.price 
            FROM cart c 
            JOIN products p ON c.product_id = p.id 
            WHERE c.user_id = ? AND p.active = TRUE
        ''', (user_id,))
        cart_items = cursor.fetchall()
        conn.close()
        
        if not cart_items:
            text = "🛒 Your cart is empty!"
            keyboard = [
                [
                    InlineKeyboardButton("🛍️ Continue Shopping", callback_data="browse_products"),
                    InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
                ]
            ]
        else:
            text = "🛒 Your Cart:\n\n"
            total = 0
            total_items = 0
            
            for item in cart_items:
                product_id, quantity, name, price = item
                item_total = price * quantity
                text += f"🛍️ {name}\n 💰 {price}€ × {quantity} = {item_total:.2f}€\n\n"
                total += item_total
                total_items += quantity
            
            usd_total = total * self.exchange_rate
            text += f"💵 Total: {total:.2f}€ (${usd_total:.2f})"
            
            keyboard = [
                [
                    InlineKeyboardButton("💰 Checkout All", callback_data="checkout_all"),
                    InlineKeyboardButton("🗑️ Clear Cart", callback_data="clear_cart")
                ],
                [
                    InlineKeyboardButton("🛍️ Continue Shopping", callback_data="continue_shopping"),
                    InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
                ]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def clear_cart(self, update, context):
        user_id = update.callback_query.from_user.id
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM cart WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        await update.callback_query.answer("Cart cleared!")
        await self.show_cart(update, context)

    async def buy_now(self, update, context, product_id: int):
        context.user_data['current_order'] = {
            'type': 'single',
            'product_id': product_id,
            'quantity': 1
        }
        await self.start_checkout(update, context)

    async def start_checkout(self, update, context):
        user_id = update.callback_query.from_user.id
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        if 'current_order' in context.user_data and context.user_data['current_order']['type'] == 'single':
            product_id = context.user_data['current_order']['product_id']
            cursor.execute('SELECT name, price FROM products WHERE id = ?', (product_id,))
            product = cursor.fetchone()
            
            if product:
                name, price = product
                total = price
                context.user_data['checkout_total'] = total
                context.user_data['checkout_items'] = [{'product_id': product_id, 'name': name, 'price': price, 'quantity': 1}]
        else:
            cursor.execute('''
                SELECT c.product_id, c.quantity, p.name, p.price 
                FROM cart c 
                JOIN products p ON c.product_id = p.id 
                WHERE c.user_id = ?
            ''', (user_id,))
            cart_items = cursor.fetchall()
            
            total = 0
            checkout_items = []
            for item in cart_items:
                product_id, quantity, name, price = item
                item_total = price * quantity
                total += item_total
                checkout_items.append({
                    'product_id': product_id,
                    'name': name,
                    'price': price,
                    'quantity': quantity
                })
            
            context.user_data['checkout_total'] = total
            context.user_data['checkout_items'] = checkout_items
        
        conn.close()
        
        await self.ask_discount_code(update, context)

    async def ask_discount_code(self, update, context):
        total = context.user_data.get('checkout_total', 0)
        usd_total = total * self.exchange_rate
        
        text = f"""💰 {total:.2f}€ (${usd_total:.2f})

Do you have a discount code? Enter it below or press 'No Code' to continue:"""
        
        keyboard = [
            [
                InlineKeyboardButton("🚫 No Code", callback_data="no_discount"),
                InlineKeyboardButton("✅ Continue to Payment", callback_data="continue_to_payment")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)
        
        return self.config.DISCOUNT_CODE_INPUT

    async def receive_discount_code(self, update, context):
        discount_code = update.message.text.upper()
        user_id = update.effective_user.id
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT discount_percentage, expiry_date, max_uses, used_count, is_general, client_id, client_username, active
            FROM discount_codes 
            WHERE code = ? AND active = TRUE
        ''', (discount_code,))
        code_data = cursor.fetchone()
        
        if not code_data:
            await update.message.reply_text("❌ Invalid discount code. Please try again or press 'No Code':")
            return self.config.DISCOUNT_CODE_INPUT
        
        discount_percentage, expiry_date, max_uses, used_count, is_general, client_id, client_username, active = code_data
        
        if expiry_date and datetime.now().date() > datetime.strptime(expiry_date, '%Y-%m-%d').date():
            await update.message.reply_text("❌ Discount code has expired. Please try another code or press 'No Code':")
            return self.config.DISCOUNT_CODE_INPUT
        
        if max_uses != -1 and used_count >= max_uses:
            await update.message.reply_text("❌ Discount code has reached maximum uses. Please try another code or press 'No Code':")
            return self.config.DISCOUNT_CODE_INPUT
        
        if not is_general:
            if client_id and client_id != user_id:
                await update.message.reply_text("❌ This discount code is not for you. Please try another code or press 'No Code':")
                return self.config.DISCOUNT_CODE_INPUT
            if client_username and client_username != update.effective_user.username:
                await update.message.reply_text("❌ This discount code is not for you. Please try another code or press 'No Code':")
                return self.config.DISCOUNT_CODE_INPUT
        
        original_total = context.user_data.get('checkout_total', 0)
        discount_amount = original_total * (discount_percentage / 100)
        new_total = original_total - discount_amount
        
        context.user_data['discount_code'] = discount_code
        context.user_data['checkout_total'] = new_total
        
        usd_new_total = new_total * self.exchange_rate
        
        text = f"""🎫 Discount Applied!
💰 Original: {original_total:.2f}€
📊 Discount: {discount_percentage}%
💵 New Total: {new_total:.2f}€ (${usd_new_total:.2f})"""
        
        keyboard = [
            [InlineKeyboardButton("✅ Continue to Payment", callback_data="continue_to_payment")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)
        return ConversationHandler.END

    async def show_payment_methods(self, update, context):
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT currency_code, address, blockchain FROM payment_settings')
        payment_methods = cursor.fetchall()
        conn.close()
        
        total = context.user_data.get('checkout_total', 0)
        usd_total = total * self.exchange_rate
        
        if 'current_order' in context.user_data and context.user_data['current_order']['type'] == 'single':
            product_id = context.user_data['current_order']['product_id']
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT name, price FROM products WHERE id = ?', (product_id,))
            product = cursor.fetchone()
            conn.close()
            product_text = f"🛍️ {product[0]}\n💰 Price: {product[1]}€"
        else:
            product_text = "🛍️ Multiple products from cart"
        
        text = f"""💳 Choose payment method:

{product_text}
💰 Total: {total:.2f}€ (${usd_total:.2f})"""
        
        keyboard = []
        for method in payment_methods:
            currency_code, address, blockchain = method
            currency_name = {
                'btc': '₿ Bitcoin',
                'eth': 'Ξ Ethereum', 
                'sol': '◎ Solana',
                'ltc': '💎 Litecoin',
                'usdt': '💵 USDT'
            }.get(currency_code, currency_code.upper())
            
            keyboard.append([InlineKeyboardButton(currency_name, callback_data=f"payment_{currency_code}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="view_cart")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_payment_details(self, update, context, currency: str):
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT address, blockchain FROM payment_settings WHERE currency_code = ?', (currency,))
        payment_method = cursor.fetchone()
        conn.close()
        
        if not payment_method:
            await update.callback_query.edit_message_text("Payment method not found!")
            return
        
        address, blockchain = payment_method
        total = context.user_data.get('checkout_total', 0)
        usd_total = total * self.exchange_rate
        
        currency_name = {
            'btc': 'Bitcoin',
            'eth': 'Ethereum',
            'sol': 'Solana', 
            'ltc': 'Litecoin',
            'usdt': 'USDT'
        }.get(currency, currency.upper())
        
        text = f"""💳 **PAYMENT DETAILS**

🛍️ {'Single product' if 'current_order' in context.user_data else 'Cart items'}
💰 Total: {total:.2f}€ (${usd_total:.2f})
⛓️ Blockchain: {blockchain}

📧 **SEND PAYMENT TO ADDRESS:**
`{address}`

⚠️ **IMPORTANT:**
• Send exactly {total:.2f}€ worth of {currency_name}
• Copy address exactly

After payment, click the button below:"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ PAYMENT MADE", callback_data="payment_made"),
                InlineKeyboardButton("🔙 Back to Payment Methods", callback_data="back_to_payment_methods")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.user_data['payment_currency'] = currency
        context.user_data['payment_address'] = address
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def ask_payment_source_address(self, update, context):
        text = """🔍 **PAYMENT CONFIRMATION**

Please enter the payment source address (where you sent from):

⚠️ **IMPORTANT:** This helps us identify your payment and link it to your order!

Example: `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa`"""
        
        await update.callback_query.edit_message_text(text, parse_mode='Markdown')
        return self.config.PAYMENT_SOURCE_ADDRESS

    async def receive_payment_source_address(self, update, context):
        payment_source = update.message.text
        user = update.effective_user
        order_id = str(uuid.uuid4())[:8].upper()
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        checkout_items = context.user_data.get('checkout_items', [])
        total = context.user_data.get('checkout_total', 0)
        currency = context.user_data.get('payment_currency')
        discount_code = context.user_data.get('discount_code')
        
        for item in checkout_items:
            cursor.execute('''
                INSERT INTO orders 
                (user_id, user_name, product_id, product_name, quantity, total_price, order_id, payment_currency, payment_source_address, discount_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user.id,
                user.username or user.first_name,
                item['product_id'],
                item['name'],
                item['quantity'],
                total,
                order_id,
                currency,
                payment_source,
                discount_code
            ))
            
            cursor.execute('''
                UPDATE products SET quantity = quantity - ? WHERE id = ?
            ''', (item['quantity'], item['product_id']))
        
        if 'current_order' not in context.user_data:
            cursor.execute('DELETE FROM cart WHERE user_id = ?', (user.id,))
        
        if discount_code:
            cursor.execute('''
                UPDATE discount_codes SET used_count = used_count + 1 
                WHERE code = ? AND (max_uses = -1 OR used_count < max_uses)
            ''', (discount_code,))
        
        conn.commit()
        conn.close()
        
        context.user_data.pop('checkout_total', None)
        context.user_data.pop('checkout_items', None)
        context.user_data.pop('payment_currency', None)
        context.user_data.pop('current_order', None)
        context.user_data.pop('discount_code', None)
        
        await self.notify_admin_of_payment(context, user, order_id, total, currency, payment_source, discount_code)
        
        text = f"""✅ Notified admin of your payment!
🆔 Order ID: {order_id}
💰 Total: {total:.2f}€
📧 Payment source address: {payment_source}

Admin will check your transaction and send products after confirmation."""
        
        await update.message.reply_text(text)
        
        await self.show_main_menu(update, context)
        return ConversationHandler.END

    async def notify_admin_of_payment(self, context, user, order_id: str, total: float, currency: str, payment_source: str, discount_code: str = None):
        user_info = f"@{user.username}" if user.username else user.first_name
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT product_name FROM orders WHERE order_id = ? LIMIT 1', (order_id,))
        order = cursor.fetchone()
        conn.close()
        
        product_name = order[0] if order else "Cart checkout"
        
        text = f"""🔄 PAYMENT AWAITING CONFIRMATION!

👤 Client: {user_info}
🆔 User ID: {user.id}
🛍️ Product: {product_name}
💰 Price: {total:.2f}€
🆔 Order ID: {order_id}
⛓️ Crypto: {currency.upper()}
📧 Payment source address: {payment_source}
🎫 Discount Code: {discount_code if discount_code else 'None'}
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Is payment visible in your wallet?"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm Payment", callback_data=f"admin_confirm_{order_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{order_id}")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=self.config.ADMIN_ID,
            text=text,
            reply_markup=reply_markup
        )

    async def show_about(self, update, context):
        text = self.get_content('about_us')
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_contact(self, update, context):
        text = self.get_content('contact')
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_website(self, update, context):
        website_url = self.get_content('website')
        text = f"🌐 Visit our website: {website_url}"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_rules(self, update, context):
        text = self.get_content('rules')
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_faq(self, update, context):
        text = self.get_content('faq')
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_main_menu(self, update, context):
        welcome_message = self.get_content('welcome_message')
        
        keyboard = [
            [
                InlineKeyboardButton("🛍️ Browse Products", callback_data="browse_products"),
                InlineKeyboardButton("🛒 My Cart", callback_data="view_cart")
            ],
            [
                InlineKeyboardButton("ℹ️ About Us", callback_data="about"),
                InlineKeyboardButton("📞 Contact", callback_data="contact")
            ],
            [
                InlineKeyboardButton("🌐 Website", callback_data="website"),
                InlineKeyboardButton("📝 Rules", callback_data="rules")
            ],
            [
                InlineKeyboardButton("🔍 FAQ", callback_data="faq")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'message') and update.message:
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text(welcome_message, reply_markup=reply_markup)
