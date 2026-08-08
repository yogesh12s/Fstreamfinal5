import sys
try:
    import cryptg
    class TgCryptoMock:
        @staticmethod
        def ige256_encrypt(data, key, iv):
            return cryptg.encrypt_ige(data, key, iv)
        @staticmethod
        def ige256_decrypt(data, key, iv):
            return cryptg.decrypt_ige(data, key, iv)
        @staticmethod
        def ctr256_encrypt(data, key, iv, state=None):
            return cryptg.encrypt_ctr(data, key, iv)
        @staticmethod
        def ctr256_decrypt(data, key, iv, state=None):
            return cryptg.decrypt_ctr(data, key, iv)
    sys.modules['tgcrypto'] = TgCryptoMock
except Exception:
    pass

from hydrogram import Client
from logging import getLogger
from logging.config import dictConfig
from .config import Telegram, LOGGER_CONFIG_JSON

dictConfig(LOGGER_CONFIG_JSON)

version = 1.8
logger = getLogger('bot')

TelegramBot = Client(
    name = 'bot',
    api_id = Telegram.API_ID,
    api_hash = Telegram.API_HASH,
    bot_token = Telegram.BOT_TOKEN,
    plugins = {'root': 'bot/plugins'},
    sleep_threshold = -1,
    max_concurrent_transmissions = 10,
)
