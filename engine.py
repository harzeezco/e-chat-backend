import time
import urllib.parse

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from config import asyncio, logger, message_queue, ollama_client
from crawlers_frontier.frontier import AsyncURLFrontier, SimulatedBloomFilter
from crawlers.workers import parser_worker, downloader_worker

async def sitemap_hunter(seed_url: str, session: AsyncSession, frontier: AsyncURLFrontier, url_seen: SimulatedBloomFilter, base_domain: str):
    parsed = urllib.parse.urlparse(seed_url)
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    logger.info(
        f"[{base_domain}] 🗺️ Hunting for hidden Sitemap at {sitemap_url}...")

    try:
        response = await session.get(sitemap_url, timeout=5)
        if response.status_code == 200 and ('xml' in response.text.lower() or '<urlset' in response.text.lower()):
            soup = BeautifulSoup(response.text, 'xml')
            loc_tags = soup.find_all('loc')

            added_count = 0
            for loc in loc_tags:
                url = loc.text.strip()
                if url.endswith(('.jpg', '.png', '.xml', '.pdf')):
                    continue
                await frontier.enqueue(url, url_seen, priority=2)
                added_count += 1

            if added_count > 0:
                logger.info(
                    f"[{base_domain}] ✅ Sitemap Hunter SUCCESS! Injected {added_count} URLs.")
                return True
    except Exception:
        logger.info(
            f"[{base_domain}] Sitemap lookup bypassed or timed out. Proceeding with standard crawler.")
    return False

# ==========================================
# 7. ORCHESTRATOR
# ==========================================


async def async_run_engine(seed_url: str, max_pages: int = 20, num_downloaders: int = 3, politeness_delay: float = 1.0):
    logger.info(f"🚀 INGESTION ENGINE INITIALIZING ON {seed_url}...")
    start_time = time.time()

    base_domain = urllib.parse.urlparse(seed_url).netloc.replace("www.", "")

    url_seen = SimulatedBloomFilter()
    content_seen = set()
    results_list = []

    frontier = AsyncURLFrontier(politeness_delay=politeness_delay)
    await frontier.enqueue(seed_url, url_seen, priority=1)

    try:
        async with AsyncSession(impersonate="chrome120") as session:
            await sitemap_hunter(seed_url, session, frontier, url_seen, base_domain)

            workers = []
            for _ in range(num_downloaders):
                workers.append(asyncio.create_task(
                    downloader_worker(frontier, session, max_pages,
                                      results_list, url_seen, base_domain)
                ))

            parser_task = asyncio.create_task(
                parser_worker(frontier, base_domain, max_pages,
                              results_list, content_seen, url_seen)
            )

            while True:
                if len(results_list) >= max_pages or (frontier.active_tasks == 0 and message_queue.empty()):
                    break
                await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.warning(f"\n[{base_domain}] [STOP COMMAND] Halting engine...")
    finally:
        for w in workers:
            w.cancel()
        if parser_task:
            parser_task.cancel()

        duration = round(time.time() - start_time, 2)
        logger.info(
            f"🏁 INGESTION COMPLETE! Processed and streamed {len(results_list)} products directly to Supabase in {duration}s.")

if __name__ == "__main__":
    try:
        asyncio.run(async_run_engine(
            "https://jiji.ng/",
            max_pages=20,
            num_downloaders=4,
            politeness_delay=1.0
        ))
    except KeyboardInterrupt:
        pass
