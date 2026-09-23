import hashlib
import asyncio
import time
import urllib.parse


class SimulatedBloomFilter:
    def __init__(self, size=5000000):
        self.bit_array = bytearray(size)

    def add(self, url):
        idx = int(hashlib.md5(url.encode()).hexdigest(),
                  16) % len(self.bit_array)
        self.bit_array[idx] = 1

    def __contains__(self, url):
        idx = int(hashlib.md5(url.encode()).hexdigest(),
                  16) % len(self.bit_array)
        return self.bit_array[idx] == 1


class AsyncURLFrontier:
    def __init__(self, politeness_delay=1.0):
        self.front_queue = asyncio.PriorityQueue()
        self.domain_last_hit = {}
        self.delay = politeness_delay
        self.lock = asyncio.Lock()
        self.active_tasks = 0

    async def enqueue(self, url: str, url_seen: SimulatedBloomFilter, priority: int = 5, force: bool = False):
        if force or url not in url_seen:
            if not force:
                url_seen.add(url)
            await self.front_queue.put((priority, url))
            async with self.lock:
                self.active_tasks += 1

    async def get_url(self) -> str:
        _, url = await self.front_queue.get()
        domain = urllib.parse.urlparse(url).netloc
        async with self.lock:
            now = time.time()
            last_hit = self.domain_last_hit.get(domain, 0)
            next_allowed = max(now, last_hit + self.delay)
            self.domain_last_hit[domain] = next_allowed
            sleep_time = next_allowed - now

        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        return url

    async def task_done(self):
        self.front_queue.task_done()
        async with self.lock:
            self.active_tasks -= 1
