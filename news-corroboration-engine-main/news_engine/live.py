import asyncio


class LiveHub:
    """Bounded per-client queues keep slow clients from blocking ingestion."""

    def __init__(self):
        self.queues = set()

    def subscribe(self):
        queue = asyncio.Queue(maxsize=100)
        self.queues.add(queue)
        return queue

    def unsubscribe(self, queue):
        self.queues.discard(queue)

    async def publish(self, event):
        for queue in tuple(self.queues):
            if queue.full():
                # Tell the client to resync via REST rather than silently dropping updates.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait({"type": "resync_required"})
            else:
                queue.put_nowait(event)
