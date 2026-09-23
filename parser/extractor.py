import re
import urllib.parse
import markdownify
import json
from bs4 import BeautifulSoup

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
