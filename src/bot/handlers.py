from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
from bot.loader import rabbit, db


subscribe_helper_text = """
Please run command /subscribe with the following arguments
- application number (usually 4 to 5 digits)
- application suffix (put 0, if you don't have it)
- application type (TP,DP,MK, etc...)
- year of application (4 digits)

Example: /subscribe 12345 0 TP 2023

"""

logger = logging.getLogger(__name__)


# Handler for the /start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a message with three inline buttons attached"""
    logging.info(f"Received /start command from {update.message.chat_id}")
    keyboard = [
        [InlineKeyboardButton("Subscribe", callback_data="subscribe")],
        [InlineKeyboardButton("Unsubscribe", callback_data="unsubscribe")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please choose:", reply_markup=reply_markup)


# Handler for button clicks
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "subscribe":
        if await db.check_subscription_in_db(query.message.chat_id):
            await query.edit_message_text("You are already subscribed.")
        else:
            await query.edit_message_text(subscribe_helper_text)
    elif query.data == "unsubscribe":
        if await db.check_subscription_in_db(query.message.chat_id):
            await db.remove_from_db(query.message.chat_id)
            await query.edit_message_text("You have unsubscribed.")
        else:
            await query.edit_message_text("You are not subscribed.")


# Handler for the /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays info on how to use the bot."""
    await update.message.reply_text("Press bot menu for this list of available commands.")


# Handler for unknown commands
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")


# Handler for /status command
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns current status of the application"""
    logger.info(f"Received /status command from {update.effective_chat.id}")

    if await db.check_subscription_in_db(update.message.chat_id):
        app_status = await db.get_status_from_db(update.message.chat_id)
        await update.message.reply_text(app_status)
    else:
        await update.message.reply_text("You are not subscribed")


# Handler for /unsubscribe command
async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unsubscribes user from application status updates"""
    logger.info(f"Received /unsubscribe command from {update.effective_chat.id}")

    if await db.check_subscription_in_db(update.message.chat_id):
        await db.remove_from_db(update.message.chat_id)
        await update.message.reply_text("You have unsubscribed")
    else:
        await update.message.reply_text("You are not subscribed")


# Handler for /subscribe command
async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Subscribes user for application status updates"""
    app_data = context.args
    logger.info(f"Received /subscribe command with args {app_data} from {update.effective_chat.id}")

    if await db.check_subscription_in_db(update.message.chat_id):
        await update.message.reply_text("You are already subscribed")
        return
    try:
        if len(app_data) == 4:
            number, suffix, type, year = context.args
            # Input sanitization
            if not number.isdigit():
                await update.message.reply_text("Invalid application number.")
                return
            if not suffix.isdigit():
                await update.message.reply_text("Invalid suffix. It should be a number.")
                return
            if len(type) != 2:
                await update.message.reply_text("Invalid type. It should be two letters (e.g. TP, DP, MK and so on)")
                return
            if not year.isdigit() or len(year) != 4:
                await update.message.reply_text("Invalid year. It should be 4 digits.")
                return

            message = {
                "chat_id": update.message.chat_id,
                "number": number,
                "suffix": suffix,
                "type": type.upper(),
                "year": year,
            }
            logger.info(f"Received application details {message}")
            # add data to the db
            await db.add_to_db(update.message.chat_id, number, suffix, type.upper(), int(year))

            # publish request for fetchers
            await rabbit.publish_message(message)

            await update.message.reply_text(
                f"You have been subscribed for application <b>OAM-{number}-{suffix}/{type.upper()}-{year}</b> updates.",
            )
        else:
            await update.message.reply_text(subscribe_helper_text)
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")