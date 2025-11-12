import logging
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters,
    ContextTypes,
    ConversationHandler
)

from config import Config
from client_handlers import ClientHandlers
from admin_handlers import AdminHandlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class StoreBot:
    def __init__(self):
        self.config = Config()
        self.client = ClientHandlers(self.config)
        self.admin = AdminHandlers(self.config)
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if user.id == self.config.ADMIN_ID:
            await self.admin.show_admin_panel(update, context)
        else:
            await self.client.show_main_menu(update, context)
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Client handlers
        if data == "browse_products":
            await self.client.show_products(update, context)
        elif data == "view_cart":
            await self.client.show_cart(update, context)
        elif data == "about":
            await self.client.show_about(update, context)
        elif data == "contact":
            await self.client.show_contact(update, context)
        elif data == "website":
            await self.client.show_website(update, context)
        elif data == "rules":
            await self.client.show_rules(update, context)
        elif data == "faq":
            await self.client.show_faq(update, context)
        elif data == "main_menu":
            await self.client.show_main_menu(update, context)
        elif data.startswith("product_"):
            product_id = int(data.split("_")[1])
            await self.client.show_product_detail(update, context, product_id)
        elif data.startswith("add_to_cart_"):
            product_id = int(data.split("_")[3])
            await self.client.add_to_cart(update, context, product_id)
        elif data == "back_to_products":
            await self.client.show_products(update, context)
        elif data == "continue_shopping":
            await self.client.show_products(update, context)
        elif data == "clear_cart":
            await self.client.clear_cart(update, context)
        elif data == "checkout_all":
            await self.client.start_checkout(update, context)
        elif data.startswith("buy_now_"):
            product_id = int(data.split("_")[2])
            await self.client.buy_now(update, context, product_id)
        elif data == "no_discount":
            await self.client.show_payment_methods(update, context)
        elif data == "continue_to_payment":
            await self.client.ask_discount_code(update, context)
        elif data.startswith("payment_"):
            currency = data.split("_")[1]
            await self.client.show_payment_details(update, context, currency)
        elif data == "payment_made":
            await self.client.ask_payment_source_address(update, context)
        elif data == "back_to_payment_methods":
            await self.client.show_payment_methods(update, context)
        
        # Admin handlers
        elif data == "admin_panel":
            await self.admin.show_admin_panel(update, context)
        elif data == "product_management":
            await self.admin.show_product_management(update, context)
        elif data == "content_management":
            await self.admin.show_content_management(update, context)
        elif data == "payment_settings":
            await self.admin.show_payment_settings(update, context)
        elif data == "discount_codes":
            await self.admin.show_discount_management(update, context)
        elif data == "statistics":
            await self.admin.show_statistics(update, context)
        elif data == "add_new_product":
            await self.admin.start_add_product(update, context)
        elif data.startswith("edit_product_"):
            product_id = int(data.split("_")[2])
            await self.admin.show_product_edit(update, context, product_id)
        elif data.startswith("delete_product_"):
            product_id = int(data.split("_")[2])
            await self.admin.confirm_delete_product(update, context, product_id)
        elif data.startswith("confirm_delete_"):
            product_id = int(data.split("_")[2])
            await self.admin.delete_product(update, context, product_id)
        elif data.startswith("cancel_delete_"):
            product_id = int(data.split("_")[2])
            await self.admin.show_product_edit(update, context, product_id)
        
        # Admin payment confirmation
        elif data.startswith("admin_confirm_"):
            order_id = data.split("_")[2]
            await self.admin.ask_admin_confirmation(update, context, order_id)
        elif data.startswith("admin_confirm_yes_"):
            order_id = data.split("_")[3]
            await self.admin.confirm_payment(update, context, order_id)
        elif data.startswith("admin_confirm_no_"):
            order_id = data.split("_")[3]
            await self.admin.cancel_confirmation(update, context, order_id)
        elif data.startswith("admin_reject_"):
            order_id = data.split("_")[2]
            await self.admin.reject_payment(update, context, order_id)

    def setup_handlers(self, application):
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Add product conversation
        add_product_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.admin.start_add_product, pattern="^add_new_product$")],
            states={
                self.config.PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin.receive_product_name)],
                self.config.PRODUCT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin.receive_product_price)],
                self.config.PRODUCT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin.receive_product_description)],
                self.config.PRODUCT_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin.receive_product_quantity)],
                self.config.PRODUCT_IMAGE1: [MessageHandler(filters.PHOTO, self.admin.receive_product_image1)],
                self.config.PRODUCT_IMAGE2_OPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin.receive_product_image2_option)],
                self.config.PRODUCT_IMAGE2: [MessageHandler(filters.PHOTO, self.admin.receive_product_image2)],
                self.config.PRODUCT_COORDINATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin.receive_product_coordinates)],
            },
            fallbacks=[],
        )
        
        application.add_handler(add_product_conv)
        
        # Payment source address handler
        payment_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.client.ask_payment_source_address, pattern="^payment_made$")],
            states={
                self.config.PAYMENT_SOURCE_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.client.receive_payment_source_address)],
            },
            fallbacks=[],
        )
        
        application.add_handler(payment_conv)
        
        # Discount code input handler
        discount_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.client.ask_discount_code, pattern="^continue_to_payment$")],
            states={
                self.config.DISCOUNT_CODE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.client.receive_discount_code)],
            },
            fallbacks=[],
        )
        
        application.add_handler(discount_conv)

    def run(self):
        application = Application.builder().token(self.config.BOT_TOKEN).build()
        self.setup_handlers(application)
        
        logger.info("Bot is running...")
        application.run_polling()

if __name__ == '__main__':
    bot = StoreBot()
    bot.run()
