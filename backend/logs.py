import asyncio
from typing import List, AsyncGenerator

class LogManager:
    def __init__(self):
        self.listeners: List[asyncio.Queue] = []

    async def subscribe(self) -> AsyncGenerator[str, None]:
        queue = asyncio.Queue()
        self.listeners.append(queue)
        try:
            while True:
                try:
                    # Wait for message or heartbeat timeout
                    msg = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
        finally:
            self.listeners.remove(queue)

    def push(self, msg: str):
        print(f"📡 [LOG] {msg}")
        for q in self.listeners:
            q.put_nowait(msg)

log_manager = LogManager()
