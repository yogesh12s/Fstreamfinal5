from hydrogram import Client
from itertools import cycle
from logging import getLogger
from bot.config import Telegram

logger = getLogger('bot')

class ClientPoolManager:
    def __init__(self):
        self.clients = []
        self._cycler = None

    async def start(self, primary_client: Client):
        """Starts secondary worker clients and initializes the client pool."""
        self.clients.clear()
        # Include primary client in pool
        self.clients.append(primary_client)

        for i, token in enumerate(Telegram.MULTI_TOKENS, start=1):
            if not token.strip():
                continue
            logger.info(f"Starting worker client #{i}...")
            try:
                worker = Client(
                    name=f"worker_{i}",
                    api_id=Telegram.API_ID,
                    api_hash=Telegram.API_HASH,
                    bot_token=token.strip(),
                    plugins={'root': 'bot/plugins'},  # Enables plugin commands (like /start) for all worker bots
                    in_memory=True,                    # Prevents SQLite DB lock conflicts
                    sleep_threshold=-1,
                    max_concurrent_transmissions=10,
                )
                await worker.start()
                self.clients.append(worker)
                logger.info(f"Worker client #{i} connected successfully.")
            except Exception as e:
                logger.error(f"Failed to start worker client #{i}: {e}")

        self._cycler = cycle(self.clients)
        logger.info(f"Client Pool active with {len(self.clients)} total client(s).")

    async def stop(self):
        """Stops secondary worker clients gracefully."""
        # Stop secondary workers (skip index 0 as main bot is stopped separately)
        for client in self.clients[1:]:
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"Error stopping worker client: {e}")
        self.clients.clear()
        self._cycler = None

    def get_client(self) -> Client:
        """Returns the next client from the pool in a round-robin sequence."""
        if not self.clients or self._cycler is None:
            raise RuntimeError("Client pool is not initialized!")
        return next(self._cycler)

ClientPool = ClientPoolManager()
