import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from datetime import datetime

logger = logging.getLogger(__name__)

class AdminHandlers:
    def __init__(self, config):
        self.config = config

    def is_admin(self, user_id):
        return user_id == self.config.ADMIN_ID

    async def show_admin_panel(self, update, context):
        if not self.is_admin(update.effective_user.id):
            if hasattr(update, 'callback_query'):
                await update.callback_query.answer("Access denied!", show_alert=True)
            return
        
        text = "🛠️ Admin Panel:"
        
        keyboard = [
            [InlineKeyboardButton("📦 Product Management", callback_data="product_management")],
            [InlineKeyboardButton("📝 Content Management", callback_data="content_management")],
            [InlineKeyboardButton("💳 Payment Settings", callback_data="payment_settings")],
            [InlineKeyboardButton("🎫 Discount Codes", callback_data="discount_codes")],
            [InlineKeyboardButton("📊 Statistics", callback_data="statistics")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)

    async def show_product_management(self, update, context):
        if not self.is_admin(update.effective_user.id):
            await update.callback_query.answer("Access denied!", show_alert=True)
            return
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, price, active FROM products ORDER BY name')
        products = cursor.fetchall()
        conn.close()
        
        text = "📦 Product Management:"
        
        keyboard = []
        for product in products:
            product_id, name, price, active = product
            status = "✅" if active else "❌"
            keyboard.append([InlineKeyboardButton(
                f"{status} {name} - {price}€", 
                callback_data=f"edit_product_{product_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("➕ Add New Product", callback_data="add_new_product")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def start_add_product(self, update, context):
        if not self.is_admin(update.effective_user.id):
            await update.callback_query.answer("Access denied!", show_alert=True)
            return
        
        context.user_data['new_product'] = {}
        await update.callback_query.edit_message_text("Enter product name:")
        return self.config.PRODUCT_NAME

    async def receive_product_name(self, update, context):
        context.user_data['new_product']['name'] = update.message.text
        await update.message.reply_text("Enter product price (example: 25.00):")
        return self.config.PRODUCT_PRICE

    async def receive_product_price(self, update, context):
        try:
            price = float(update.message.text)
            context.user_data['new_product']['price'] = price
            await update.message.reply_text("Enter product description:")
            return self.config.PRODUCT_DESCRIPTION
        except ValueError:
            await update.message.reply_text("Invalid price format. Please enter a number (example: 25.00):")
            return self.config.PRODUCT_PRICE

    async def receive_product_description(self, update, context):
        context.user_data['new_product']['description'] = update.message.text
        await update.message.reply_text("Enter product quantity (example: 5):")
        return self.config.PRODUCT_QUANTITY

    async def receive_product_quantity(self, update, context):
        try:
            quantity = int(update.message.text)
            context.user_data['new_product']['quantity'] = quantity
            await update.message.reply_text("Now send the first product image:")
            return self.config.PRODUCT_IMAGE1
        except ValueError:
            await update.message.reply_text("Invalid quantity. Please enter a whole number (example: 5):")
            return self.config.PRODUCT_QUANTITY

    async def receive_product_image1(self, update, context):
        if update.message.photo:
            photo = update.message.photo[-1]
            context.user_data['new_product']['image1'] = photo.file_id
            await update.message.reply_text("Would you like to add a second image? Send 'yes' to add second image or 'no' to skip:")
            return self.config.PRODUCT_IMAGE2_OPTION
        else:
            await update.message.reply_text("Please send an image file:")
            return self.config.PRODUCT_IMAGE1

    async def receive_product_image2_option(self, update, context):
        response = update.message.text.lower()
        if response == 'yes':
            await update.message.reply_text("Please send the second product image:")
            return self.config.PRODUCT_IMAGE2
        elif response == 'no':
            context.user_data['new_product']['image2'] = None
            await update.message.reply_text("Now you can add map coordinates (optional). Enter coordinates in format: 59.4370, 24.7536\nOr send 'skip' to skip.")
            return self.config.PRODUCT_COORDINATES
        else:
            await update.message.reply_text("Please send 'yes' or 'no':")
            return self.config.PRODUCT_IMAGE2_OPTION

    async def receive_product_image2(self, update, context):
        if update.message.photo:
            photo = update.message.photo[-1]
            context.user_data['new_product']['image2'] = photo.file_id
            await update.message.reply_text("Now you can add map coordinates (optional). Enter coordinates in format: 59.4370, 24.7536\nOr send 'skip' to skip.")
            return self.config.PRODUCT_COORDINATES
        else:
            await update.message.reply_text("Please send an image file:")
            return self.config.PRODUCT_IMAGE2

    async def receive_product_coordinates(self, update, context):
        coords_text = update.message.text.strip()
        if coords_text.lower() == 'skip':
            context.user_data['new_product']['coordinates'] = None
        else:
            try:
                lat, lon = map(float, coords_text.split(','))
                context.user_data['new_product']['coordinates'] = coords_text
            except ValueError:
                await update.message.reply_text("Invalid coordinates format. Please use format: 59.4370, 24.7536\nOr send 'skip' to skip.")
                return self.config.PRODUCT_COORDINATES
        
        product_data = context.user_data['new_product']
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO products (name, price, description, quantity, image1, image2, coordinates, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, TRUE)
        ''', (
            product_data['name'],
            product_data['price'],
            product_data['description'],
            product_data['quantity'],
            product_data.get('image1'),
            product_data.get('image2'),
            product_data.get('coordinates')
        ))
        
        conn.commit()
        conn.close()
        
        coord_message = f"📍 Coordinates: {product_data.get('coordinates') or 'Not set'}\n\n" if product_data.get('coordinates') else ""
        image_count = 1 + (1 if product_data.get('image2') else 0)
        
        text = f"""🎉 Product added completely!
{coord_message}
📦 {product_data['name']}
💰 {product_data['price']}€
🖼️ {image_count} image(s) attached

Product is now available to clients."""
        
        await update.message.reply_text(text)
        
        context.user_data.pop('new_product')
        await self.show_product_management(update, context)
        return ConversationHandler.END

    async def show_product_edit(self, update, context, product_id: int):
        if not self.is_admin(update.effective_user.id):
            await update.callback_query.answer("Access denied!", show_alert=True)
            return
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name, price, description, quantity, coordinates, active FROM products WHERE id = ?', (product_id,))
        product = cursor.fetchone()
        conn.close()
        
        if not product:
            await update.callback_query.edit_message_text("Product not found!")
            return
        
        name, price, description, quantity, coordinates, active = product
        status = "Active" if active else "Inactive"
        
        text = f"""📦 Product: {name}
💰 Price: {price}€
📝 Description: {description}
📦 Quantity: {quantity}
📍 Coordinates: {coordinates or 'Not set'}
🎯 Status: {status}"""
        
        keyboard = [
            [InlineKeyboardButton("✏️ Edit Name", callback_data=f"edit_name_{product_id}")],
            [InlineKeyboardButton("💰 Edit Price", callback_data=f"edit_price_{product_id}")],
            [InlineKeyboardButton("📝 Edit Description", callback_data=f"edit_description_{product_id}")],
            [InlineKeyboardButton("📦 Edit Quantity", callback_data=f"edit_quantity_{product_id}")],
            [InlineKeyboardButton("📍 Edit Coordinates", callback_data=f"edit_coordinates_{product_id}")],
            [InlineKeyboardButton("🖼️ Add/Replace Image 1", callback_data=f"edit_image1_{product_id}")],
            [InlineKeyboardButton("🖼️ Add/Replace Image 2", callback_data=f"edit_image2_{product_id}")],
            [InlineKeyboardButton("🔄 Toggle Active", callback_data=f"toggle_active_{product_id}")],
            [InlineKeyboardButton("🗑️ Delete Product", callback_data=f"delete_product_{product_id}")],
            [InlineKeyboardButton("🔙 Back to Products", callback_data="product_management")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def confirm_delete_product(self, update, context, product_id: int):
        if not self.is_admin(update.effective_user.id):
            await update.callback_query.answer("Access denied!", show_alert=True)
            return
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name, price FROM products WHERE id = ?', (product_id,))
        product = cursor.fetchone()
        conn.close()
        
        if not product:
            await update.callback_query.edit_message_text("Product not found!")
            return
        
        name, price = product
        
        text = f"""🗑️ **DELETE CONFIRMATION**

Are you sure you want to delete this product?

📦 {name}
💰 {price}€

⚠️ **This action cannot be undone!**"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ YES, delete", callback_data=f"confirm_delete_{product_id}"),
                InlineKeyboardButton("❌ NO, cancel", callback_data=f"cancel_delete_{product_id}")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def delete_product(self, update, context, product_id: int):
        if not self.is_admin(update.effective_user.id):
            await update.callback_query.answer("Access denied!", show_alert=True)
            return
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        conn.close()
        
        await update.callback_query.answer("Product deleted!")
        await self.show_product_management(update, context)

    async def show_content_management(self, update, context):
        if not self.is_admin(update.effective_user.id):
            await update.callback_query.answer("Access denied!", show_alert=True)
            return
        
        text = "📝 Content Management:"
        
        keyboard = [
            [InlineKeyboardButton("👋 Welcome Message", callback_data="edit_content_welcome_message")],
            [InlineKeyboardButton("ℹ️ About Us", callback_data="edit_content_about_us")],
            [InlineKeyboardButton("📞 Contact", callback_data="edit_content_contact")],
            [InlineKeyboardButton("🌐 Website", callback_data="edit_content_website")],
            [InlineKeyboardButton("📝 Rules", callback_data="edit_content_rules")],
            [InlineKeyboardButton("🔍 FAQ", callback_data="edit_content_faq")],
            [InlineKeyboardButton("🎉 Success Message", callback_data="edit_content_success_message")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_payment_settings(self, update, context):
        if not self.is_admin(update.effective_user.id):
            await update.callback_query.answer("Access denied!", show_alert=True)
            return
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT currency_code, address, blockchain FROM payment_settings')
        payment_methods = cursor.fetchall()
        conn.close()
        
        text = "💳 Payment Settings:\n\n"
        
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
            
            text += f"{currency_name}:\n`{address}`\n\n"
            
            keyboard.append([
                InlineKeyboardButton(f"✏️ Edit {currency_name}", callback_data=f"edit_payment_{currency_code}"),
                InlineKeyboardButton(f"🗑️ Remove {currency_name}", callback_data=f"remove_payment_{currency_code}")
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Add New Crypto", callback_data="add_new_crypto")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_discount_management(self, update, context):
        if not self.is_admin(update.effective_user.id):
            await update.callback_query.answer("Access denied!", show_alert=True)
            return
        
        text = "🎫 Discount Code Management:"
        
        keyboard = [
            [InlineKeyboardButton("👤 Add Client-Specific", callback_data="add_client_specific_code")],
            [InlineKeyboardButton("🌍 Add General Discount", callback_data="add_general_discount")],
            [InlineKeyboardButton("📋 View All Codes", callback_data="view_all_codes")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_statistics(self, update, context):
        if not self.is_admin(update.effective_user.id):
            await update.callback_query.answer("Access denied!", show_alert=True)
            return
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM products')
        total_products = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM products WHERE active = TRUE')
        active_products = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM orders')
        total_orders = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM orders WHERE status = "completed"')
        completed_orders = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM orders WHERE status = "pending"')
        pending_orders = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM cart')
        products_in_carts = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM discount_codes')
        total_codes = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM discount_codes WHERE active = TRUE')
        active_codes = cursor.fetchone()[0]
        
        conn.close()
        
        text = f"""📊 STORE STATISTICS

🛍️ PRODUCTS:
• All products: {total_products}
• Active products: {active_products}

📦 ORDERS:
• All orders: {total_orders}
• Completed: {completed_orders}
• Pending: {pending_orders}

🛒 CARTS:
• Products in carts: {products_in_carts}

🎫 DISCOUNT CODES:
• All codes: {total_codes}
• Active: {active_codes}"""
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)

    # Payment confirmation handlers
    async def ask_admin_confirmation(self, update, context, order_id: str):
        text = f"""🔍 **CONFIRMATION**

Are you sure you want to approve this payment?

🆔 Order ID: {order_id}"""

        keyboard = [
            [
                InlineKeyboardButton("✅ YES, confirm payment", callback_data=f"admin_confirm_yes_{order_id}"),
                InlineKeyboardButton("❌ NO, cancel", callback_data=f"admin_confirm_no_{order_id}")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def confirm_payment(self, update, context, order_id: str):
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT user_id, product_id, product_name, quantity FROM orders WHERE order_id = ?', (order_id,))
        orders = cursor.fetchall()

        cursor.execute('UPDATE orders SET status = ? WHERE order_id = ?', ('completed', order_id))
        conn.commit()

        for order in orders:
            user_id, product_id, product_name, quantity = order

            cursor.execute('SELECT image1, image2, coordinates FROM products WHERE id = ?', (product_id,))
            product = cursor.fetchone()

            if product:
                image1, image2, coordinates = product

                text = f"✅ Your payment has been confirmed!\n\n🛍️ Product: {product_name}\n📦 Quantity: {quantity}"

                if coordinates:
                    text += f"\n📍 Location: {coordinates}"

                await context.bot.send_message(chat_id=user_id, text=text)

                if image1:
                    await context.bot.send_photo(chat_id=user_id, photo=image1, caption="Product image 1")
                if image2:
                    await context.bot.send_photo(chat_id=user_id, photo=image2, caption="Product image 2")

        conn.close()

        query = update.callback_query
        await query.edit_message_text(f"✅ Payment for order {order_id} confirmed and client notified!")

    async def cancel_confirmation(self, update, context, order_id: str):
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, user_name, product_name, total_price, payment_currency, payment_source_address, discount_code FROM orders WHERE order_id = ? LIMIT 1', (order_id,))
        order = cursor.fetchone()
        conn.close()

        if order:
            user_id, user_name, product_name, total_price, payment_currency, payment_source_address, discount_code = order

            text = f"""🔄 PAYMENT AWAITING CONFIRMATION!

👤 Client: {user_name}
🆔 User ID: {user_id}
🛍️ Product: {product_name}
💰 Price: {total_price:.2f}€
🆔 Order ID: {order_id}
⛓️ Crypto: {payment_currency}
📧 Payment source address: {payment_source_address}
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

            query = update.callback_query
            await query.edit_message_text(text, reply_markup=reply_markup)

    async def reject_payment(self, update, context, order_id: str):
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE orders SET status = ? WHERE order_id = ?', ('rejected', order_id))
        conn.commit()

        cursor.execute('SELECT user_id FROM orders WHERE order_id = ? LIMIT 1', (order_id,))
        order = cursor.fetchone()
        if order:
            user_id = order[0]
            await context.bot.send_message(
                chat_id=user_id, 
                text=f"❌ Your payment for order {order_id} has been rejected. Please contact admin."
            )

        conn.close()

        query = update.callback_query
        await query.edit_message_text(f"❌ Payment for order {order_id} rejected!")
