import asyncio
import hashlib
import time
import json
import uuid
import os
import re
import urllib.parse
from bs4 import BeautifulSoup
import markdownify
import logging
import warnings
from bs4 import XMLParsedAsHTMLWarning
from curl_cffi.requests import AsyncSession
import ollama
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Suppress XML warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# ==========================================
# 1. LOGGING & CONFIGURATION SETUP
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("agent_engine_debug.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AskFastaIngestionEngine")

# Production Credentials / Environment Variables
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "your-production-ollama-key")
SUPABASE_URL = os.getenv("SUPABASE_URL", "your-supabase-url")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-supabase-key")

# Initialize Clients
ollama_client = ollama.Client(
    host=OLLAMA_HOST,
    headers={'Authorization': f'Bearer {OLLAMA_API_KEY}'} if OLLAMA_API_KEY != "your-production-ollama-key" else {}
)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Pure RAM Memory Queue (No Disk I/O)
message_queue = asyncio.Queue(maxsize=50)


class ProxyManager:
    def __init__(self, proxy_url=None):
        self.proxy_url = proxy_url or os.getenv("RESIDENTIAL_PROXY_URL", None)

    def get_curl_proxy(self):
        return {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None


proxy_mgr = ProxyManager()

# ==========================================
# 2. RAM-BASED BLOOM FILTER & URL FRONTIER
# ==========================================


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

# ==========================================
# 3. PURE RAM DOWNLOADER WORKER
# ==========================================


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

        except Exception:
            pass

        finally:
            if not download_successful:
                await frontier.task_done()

# ==========================================
# 4. DATA SANITIZER & DUAL-LAYER EXTRACTOR
# ==========================================


def clean_agent_knowledge(raw_text: str, title: str, price: str) -> str:
    if not raw_text:
        return ""

    boilerplate_patterns = [
        r"Type your search here.*?(?=#|$)",
        r"Sell faster.*?Buy smarter",
        r"Sign in.*?Registration",
        r"1\.\s+\[All ads\].*?#\s+" + re.escape(title),
        r"Safety tips.*",
        r"Report Abuse.*",
        r"Show contact.*",
        r"Make an offer.*",
        r"\[.*?\]\(.*?\)"
    ]

    cleaned = raw_text
    for pattern in boilerplate_patterns:
        cleaned = re.sub(pattern, " ", cleaned,
                         flags=re.DOTALL | re.IGNORECASE)

    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r'[ \t]+', ' ', cleaned).strip()

    structured_payload = (
        f"Product: {title}\n"
        f"Price: {price}\n"
        f"Key Specifications & Details:\n{cleaned}"
    )

    return structured_payload


def is_pagination_link(url: str) -> bool:
    url_lower = url.lower()
    pagination_signatures = ['page=', '?p=', '&p=', '/page/', '/p/']
    return any(sig in url_lower for sig in pagination_signatures)


def is_universal_product_page(soup: BeautifulSoup, url: str) -> bool:
    parsed_url = urllib.parse.urlparse(url)

    if parsed_url.path.endswith('/') and len(parsed_url.path) > 1:
        return False

    subdomain = parsed_url.netloc.split('.')[0].lower()
    if subdomain in ['blog', 'support', 'help', 'forum', 'news', 'affiliate']:
        return False

    ignore_paths = [
        '/blog/', '/contact', '/about', '/terms', '/cart',
        '/checkout', '/category/', '/author/', '/buyers-guide/',
        '/events-fashion-health/', '/cdn-cgi/'
    ]
    if any(path in url.lower() for path in ignore_paths):
        return False

    og_type = soup.find('meta', property='og:type')
    if og_type and og_type.get('content', '').lower() == 'product':
        return True

    for script in soup.find_all('script', type='application/ld+json'):
        if script.string and '"@type": "Product"' in script.string:
            return True

    text_content = soup.get_text().lower()
    if any(kw in text_content for kw in ["add to cart", "buy now", "add to bag"]):
        if soup.find('meta', property='product:price:amount') or soup.find('meta', property='og:price:amount'):
            return True

    return False


def extract_agent_product_data(html: str, url: str, base_domain: str):
    soup = BeautifulSoup(html, 'html.parser')
    is_product = is_universal_product_page(soup, url)

    title = ""
    price = "Check Website"
    image_url = ""
    structured_specs = {}

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            if not script.string:
                continue
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get('@type') == 'Product' or 'Product' in str(item.get('@type', '')):
                    title = item.get('name', title)
                    offer = item.get('offers', {})
                    if isinstance(offer, list):
                        offer = offer[0]
                    p_val = offer.get('price') or offer.get('lowPrice')
                    if p_val:
                        price = f"₦ {p_val}" if not str(
                            p_val).startswith('₦') else str(p_val)
                    img = item.get('image')
                    if img:
                        image_url = img[0] if isinstance(img, list) else img
                    break
        except Exception:
            pass

    if not title:
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title.get('content').strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

    if price == "Check Website":
        og_price = soup.find('meta', property='product:price:amount') or soup.find(
            'meta', property='og:price:amount')
        if og_price and og_price.get('content'):
            price = og_price.get('content').strip()
        else:
            text_body = soup.get_text()
            price_match = re.search(r'(?:₦|N)\s*([\d,]+\.?\d*)', text_body)
            if price_match:
                price = f"₦ {price_match.group(1)}"

    if not image_url:
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = urllib.parse.urljoin(
                url, og_image.get('content').strip())
        else:
            first_img = soup.find('img', src=True)
            if first_img:
                src = first_img.get('src', '')
                if src.startswith('/_next/image'):
                    parsed_src = urllib.parse.urlparse(src)
                    params = urllib.parse.parse_qs(parsed_src.query)
                    if 'url' in params:
                        image_url = urllib.parse.urljoin(
                            url, urllib.parse.unquote(params['url'][0]))
                elif not src.endswith(('.svg', '.gif')):
                    image_url = urllib.parse.urljoin(url, src)

    for row in soup.find_all(['tr', 'li', 'div']):
        text = row.get_text(separator="|", strip=True)
        if "|" in text:
            parts = [p.strip() for p in text.split("|") if p.strip()]
            if len(parts) == 2 and len(parts[0]) < 30 and len(parts[1]) < 50:
                structured_specs[parts[0]] = parts[1]

    links = []
    for tag in soup.find_all("a", href=True):
        new_url = urllib.parse.urljoin(url, tag["href"]).split("#")[0]
        parsed_new = urllib.parse.urlparse(new_url)
        if parsed_new.netloc.replace("www.", "").endswith(base_domain):
            if is_pagination_link(new_url):
                links.append((new_url, 1))
            else:
                links.append((new_url, 5))

    for element in soup(["script", "style", "nav", "footer", "meta", "noscript", "svg", "header", "button", "iframe", "img"]):
        element.decompose()

    raw_markdown = markdownify.markdownify(
        str(soup), heading_style="ATX").strip()
    specs_text = "\n".join(
        [f"- {k}: {v}" for k, v in structured_specs.items()])

    clean_markdown = clean_agent_knowledge(raw_markdown, title, price)
    if specs_text:
        clean_markdown += f"\n\nExtracted Attributes:\n{specs_text}"

    return {
        "title": title,
        "price": price,
        "image_url": image_url,
        "url": url,
        "clean_markdown": clean_markdown,
        "is_product": is_product,
        "links": links
    }

# ==========================================
# 5. STREAMING EMBEDDING & BATCH UPSERT TO SUPABASE
# ==========================================


async def generate_local_embedding(text: str) -> list:
    try:
        response = await asyncio.to_thread(
            ollama_client.embed,
            model="nomic-embed-text",
            input=text
        )
        return response['embeddings'][0]
    except Exception as e:
        logger.error(f"Ollama embedding error: {e}")
        return []


async def flush_batch_to_supabase(batch_list: list, base_domain: str):
    """Sends accumulated product records with embeddings in a single batch upsert."""
    if not batch_list:
        return

    payloads = []
    for prod in batch_list:
        vector = await generate_local_embedding(prod["raw_knowledge_for_agent"])
        if not vector:
            continue

        payloads.append({
            "product_id": prod["product_id"],
            "merchant_domain": base_domain,
            "product_title": prod["product_title"],
            "detected_price": prod["detected_price"],
            "image_url": prod["image_url"],
            "source_url": prod["source_url"],
            "content": prod["raw_knowledge_for_agent"],
            "embedding": vector
        })

    if payloads:
        with open('products.json', 'w', encoding='utf-8') as f:
            f.write(payloads)

    batch_list.clear()


async def parser_worker(frontier: AsyncURLFrontier, base_domain: str, max_pages: int, results_list: list, content_seen: set, url_seen: SimulatedBloomFilter):
    batch_buffer = []
    batch_size = 5  # Flush batch to Supabase every 5 extracted products

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
                        "product_id": str(uuid.uuid4())[:8],
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
                        await flush_batch_to_supabase(batch_buffer, base_domain)
                else:
                    logger.info(f"[{base_domain}] 🟡 [SEARCHING] -> {url}")

            for new_url, priority in parsed_data["links"]:
                await frontier.enqueue(new_url, url_seen, priority)

        except asyncio.TimeoutError:
            if len(results_list) >= max_pages or (frontier.active_tasks == 0 and message_queue.empty()):
                break
        except Exception:
            pass
        finally:
            if task is not None:
                message_queue.task_done()
                await frontier.task_done()

    # Flush any remaining items in the buffer before shutting down
    if batch_buffer:
        await flush_batch_to_supabase(batch_buffer, base_domain)

# ==========================================
# 6. SITEMAP HUNTER
# ==========================================


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
