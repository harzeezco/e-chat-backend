import json
import uuid
import hashlib
import asyncio
from config import logger, message_queue
from parser.extractor import extract_agent_product_data  # Ensure this is imported
from crawlers_frontier.frontier import SimulatedBloomFilter, AsyncURLFrontier
from curl_cffi.requests import AsyncSession
import os


class ProxyManager:
    def __init__(self, proxy_url=None):
        self.proxy_url = proxy_url or os.getenv("RESIDENTIAL_PROXY_URL", None)

    def get_curl_proxy(self):
        return {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None


proxy_mgr = ProxyManager()


async def parser_worker(frontier, base_domain: str, max_pages: int, results_list: list, content_seen: set, url_seen):
    batch_buffer = []
    batch_size = 5  # Flush batch to file every 5 extracted products
    # Using .jsonl because we are appending line by line
    file_name = "raw_products.json"

    while True:
        task = None
        try:
            task = await asyncio.wait_for(message_queue.get(), timeout=2.0)
            url, html = task["url"], task["html"]

            parsed_data = await asyncio.to_thread(extract_agent_product_data, html, url, base_domain)

            content_hash = hashlib.md5(parsed_data["clean_markdown"].encode(
                'utf-8', errors='ignore')).hexdigest()

            if content_hash not in content_seen:
                content_seen.add(content_hash)

                if parsed_data["is_product"] and len(results_list) < max_pages:
                    product_item = {
                        "product_id": str(uuid.uuid4()),
                        "product_title": parsed_data["title"],
                        "detected_price": parsed_data["price"],
                        "image_url": parsed_data["image_url"],
                        "source_url": url,
                        "raw_knowledge_for_agent": parsed_data["clean_markdown"][:1200]
                    }
                    results_list.append(product_item)
                    batch_buffer.append(product_item)

                    logger.info(
                        f"[{base_domain}] 🟢 [EXTRACTED {len(results_list)}/{max_pages}] -> {url}")

                    # Trigger batch write when buffer hits target size
                    if len(batch_buffer) >= batch_size:
                        with open(file_name, "a", encoding="utf-8") as f:
                            for item in batch_buffer:
                                f.write(json.dumps(
                                    item, ensure_ascii=False) + "\n")
                        batch_buffer.clear()  # CRITICAL: Empty the buffer after saving!
                else:
                    # Correctly aligned with the 'is_product' if-statement
                    logger.info(f"[{base_domain}] 🟡 [SEARCHING] -> {url}")

            for new_url, priority in parsed_data["links"]:
                await frontier.enqueue(new_url, url_seen, priority)

        except asyncio.TimeoutError:
            if len(results_list) >= max_pages or (frontier.active_tasks == 0 and message_queue.empty()):
                break
        except Exception as e:
            logger.error(f"Parser worker error: {e}")
        finally:
            if task is not None:
                message_queue.task_done()
                await frontier.task_done()

    # Flush any remaining items in the buffer before shutting down
    if batch_buffer:
        with open(file_name, "a", encoding="utf-8") as f:
            for item in batch_buffer:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        batch_buffer.clear()


async def downloader_worker(frontier: AsyncURLFrontier, session: AsyncSession, max_pages: int, results_list: list, url_seen: SimulatedBloomFilter, base_domain: str):
    while True:
        if len(results_list) >= max_pages:
            break

        url = await frontier.get_url()
        download_successful = False

        try:
            proxies = proxy_mgr.get_curl_proxy()
            response = await session.get(url, timeout=15, proxies=proxies)

            if response.status_code == 200:
                html_text = response.text
                if html_text:
                    # Pass raw HTML straight into RAM queue
                    await message_queue.put({"url": url, "html": html_text})
                    download_successful = True

            elif response.status_code == 429:
                logger.warning(
                    f"[{base_domain}] [429 RATE LIMIT] Pausing 5s -> {url}")
                await asyncio.sleep(5.0)
                await frontier.enqueue(url, url_seen, priority=2, force=True)

            elif response.status_code in [401, 403]:
                logger.warning(f"[{base_domain}] [WAF 403] BLOCKED -> {url}")

        except Exception as e:
            logger.error(
                f"[{base_domain}] ❌ Network/Download Error on {url}: {e}")
            pass

        finally:
            if not download_successful:
                await frontier.task_done()
