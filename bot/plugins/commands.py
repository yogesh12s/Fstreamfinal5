from hydrogram import Client, filters
from hydrogram.types import Message
from bot.config import Telegram
from bot.modules.static import *
from bot.modules.decorators import verify_user

@Client.on_message(filters.command(['start', 'help']) & filters.private)
@verify_user
async def start_command(client: Client, msg: Message):
    await msg.reply(
        text = WelcomeText % {'first_name': msg.from_user.first_name},
        quote = True
    )

@Client.on_message(filters.command('privacy') & filters.private)
@verify_user
async def privacy_command(client: Client, msg: Message):
    await msg.reply(text=PrivacyText, quote=True, disable_web_page_preview=True)

@Client.on_message(filters.command('log') & filters.chat(Telegram.OWNER_ID))
async def log_command(client: Client, msg: Message):
    await msg.reply_document('event-log.txt', quote=True)
