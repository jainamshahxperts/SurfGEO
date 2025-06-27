import os
import json
import asyncio
import time
from urllib.parse import urlparse, urljoin, urlunparse
from typing import Dict, List, Optional, TYPE_CHECKING, Any
from parsel import Selector
from playwright.async_api import async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

if TYPE_CHECKING:
    from .schemas import ResearchState

class ScraperAgent:
    def __init__(self):
        self.visited = set()
        self.rejected_urls = []
        self.domain_cache = {}
        self.semaphore = asyncio.Semaphore(20)  # Concurrent pages
        self.load_times = []

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        return ' '.join(text.strip().split())

    def normalize_domain(self, domain: str) -> str:
        if domain not in self.domain_cache:
            self.domain_cache[domain] = domain.lower().replace("www.", "").strip()
        return self.domain_cache[domain]

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', '', ''))

    def is_valid_url(self, url: str, domain: str) -> bool:
        parsed = urlparse(url)
        url_domain = self.normalize_domain(parsed.netloc)
        base_domain = self.normalize_domain(domain)
        is_valid = (
            url_domain == base_domain and
            url not in self.visited and
            not any(url.endswith(ext) for ext in ('.pdf', '.jpg', '.png', '.gif', '.css', '.js', '.woff', '.woff2', '.mp4', '.webm')) and
            '#' not in url
        )
        if not is_valid:
            self.rejected_urls.append(url)
        return is_valid

    def extract_lists(self, selector: Selector) -> Dict[str, List[str]]:
        bullets = [
            self.clean_text(li) for li in selector.xpath('//ul[not(ancestor::nav or ancestor::header or ancestor::footer)]//li/text()').getall()
            if li.strip()
        ]
        numbers = [
            self.clean_text(li) for li in selector.xpath('//ol//li/text()').getall()
            if li.strip()
        ]
        return {"bullet_points": bullets, "numbered_lists": numbers}

    def extract_faq(self, selector: Selector) -> List[Dict[str, str]]:
        faqs = []
        faq_containers = selector.xpath('//*[contains(@class, "faq") or contains(@id, "faq")]')
        for container in faq_containers:
            questions = container.xpath('.//h2/text() | .//h3/text() | .//dt/text()').getall()
            for q in questions:
                question = self.clean_text(q)
                answer = self.clean_text(
                    container.xpath(
                        '(.//h2|.//h3|.//dt)[text()=$q]/following-sibling::p[1]/text() | '
                        '(.//h2|.//h3|.//dt)[text()=$q]/following-sibling::div[1]/text() | '
                        '(.//h2|.//h3|.//dt)[text()=$q]/following-sibling::dd[1]/text()',
                        q=q
                    ).get(default='')
                )
                if question and answer:
                    faqs.append({"question": question, "answer": answer})
        for dl in selector.xpath('//dl'):
            for dt, dd in zip(dl.xpath('./dt/text()').getall(), dl.xpath('./dd/text()').getall()):
                q, a = self.clean_text(dt), self.clean_text(dd)
                if q and a:
                    faqs.append({"question": q, "answer": a})
        return faqs

    def extract_ctas(self, selector: Selector) -> List[str]:
        selectors = [
            '//a[contains(@class, "btn") or contains(@class, "cta")]/text()',
            '//button[contains(@class, "btn") or contains(@class, "cta")]/text()',
            '//a[contains(@href, "contact") or contains(@href, "signup") or contains(@href, "register") or '
            'contains(@href, "buy") or contains(@href, "purchase") or contains(@href, "order")]/text()'
        ]
        ctas = set()
        for sel in selectors:
            for txt in selector.xpath(sel).getall():
                txt = self.clean_text(txt)
                if txt:
                    ctas.add(txt)
        return list(ctas)

    def extract_blogs(self, selector: Selector, url: str) -> Dict[str, Any]:
        """
        Extract blog post data from the page.

        Args:
            selector: The parsel Selector object for the page.
            url: The URL of the page.

        Returns:
            Dictionary containing blog data if the page is a blog, else empty.
        """
        # Check if the URL indicates a blog page
        blog_indicators = ['/blog/', '/news/', '/articles/', '/post/', '/posts/']
        is_blog = any(indicator in url.lower() for indicator in blog_indicators) or \
                  selector.xpath('//article').get() is not None

        if not is_blog:
            return {}

        # Extract blog title (prefer h1, fallback to h2)
        title = self.clean_text(
            selector.xpath('//h1/text()').get(default='') or
            selector.xpath('//h2/text()').get(default='')
        )

        # Extract blog content (paragraphs within article or main content area)
        content = [
            self.clean_text(p) for p in selector.xpath(
                '//article//p[not(ancestor::footer) and string-length(text()) > 20]/text() | '
                '//main//p[not(ancestor::footer) and string-length(text()) > 20]/text()'
            ).getall()
        ]

        # Extract publication date if available
        date = self.clean_text(
            selector.xpath(
                '//time/text() | '
                '//meta[@name="date" or @property="article:published_time"]/@content | '
                '//*[contains(@class, "date") or contains(@class, "published")]/text()'
            ).get(default='')
        )

        if title or content:
            return {
                "url": url,
                "title": title,
                "content": content,
                "date": date
            }
        return {}

    def extract_page_data(self, url: str, selector: Selector) -> Dict:
        """
        Extract page data including blog content.
        """
        blog_data = self.extract_blogs(selector, url)
        return {
            "url": url,
            "titles": {
                "h1": [self.clean_text(h) for h in selector.xpath('//h1/text()').getall()],
                "h2": [self.clean_text(h) for h in selector.xpath('//h2/text()').getall()],
                "h3": [self.clean_text(h) for h in selector.xpath('//h3/text()').getall()]
            },
            "paragraphs": [
                self.clean_text(p) for p in selector.xpath('//p[not(ancestor::footer) and string-length(text()) > 20]/text()').getall()
            ],
            "lists": self.extract_lists(selector),
            "faq": self.extract_faq(selector),
            "call_to_actions": self.extract_ctas(selector),
            "blog": blog_data if blog_data else None
        }

    def get_links(self, selector: Selector, current_url: str, domain: str) -> List[str]:
        links = set()
        for href in selector.xpath('//a/@href').getall():
            if href.startswith('#'):
                continue
            full_url = self.normalize_url(urljoin(current_url, href).split('#')[0])
            # Fix common URL typos
            full_url = full_url.replace('fframeworks', 'frameworks')
            if self.is_valid_url(full_url, domain):
                links.add(full_url)
        return list(links)

    async def scrape_and_extract(self, url: str, domain: str, browser_context,
                                retries: int = 2) -> Dict:
        print(f"🔍 Scraping: {url}")
        async with self.semaphore:
            for attempt in range(retries):
                try:
                    start_time = time.time()
                    page = await browser_context.new_page()
                    # Block additional resource types
                    await page.route("**/*.{png,jpg,gif,css,js,woff,woff2,mp4,webm}", lambda route: route.abort())
                    try:
                        await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                    except PlaywrightTimeoutError:
                        print(f"Timeout on {url}, capturing partial content")
                        content = await page.content()
                    else:
                        content = await page.content()
                    await page.close()
                    load_time = time.time() - start_time
                    self.load_times.append(load_time)

                    selector = Selector(text=content)
                    return {
                        "url": url,
                        "data": self.extract_page_data(url, selector),
                        "links": self.get_links(selector, url, domain)
                    }
                except Exception as e:
                    print(f"⚠️ Error scraping {url} (attempt {attempt + 1}/{retries}): {e}")
                    if attempt == retries - 1:
                        self.rejected_urls.append(url)
                        return {"url": url, "error": str(e)}
                    await asyncio.sleep(0.1)
                finally:
                    if 'page' in locals():
                        await page.close()
        return {"url": url, "error": "Max retries reached"}

    async def scrape_site(self, base_url: str, max_pages: int = 100) -> List[Dict]:
        self.visited.clear()
        self.rejected_urls.clear()
        self.load_times.clear()
        scraped_pages = []
        # Ensure base_url has a scheme
        if not urlparse(base_url).scheme:
            base_url = "https://" + base_url

        domain = self.normalize_domain(urlparse(base_url).netloc)
        queue = [self.normalize_url(base_url)]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            while queue and len(scraped_pages) < max_pages:
                batch_size = min(20, max_pages - len(scraped_pages), len(queue))
                urls_to_fetch = []
                for _ in range(batch_size):
                    if not queue:
                        break
                    url = queue.pop(0)
                    if url not in self.visited:
                        urls_to_fetch.append(url)
                        self.visited.add(url)

                tasks = [self.scrape_and_extract(url, domain, context) for url in urls_to_fetch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        continue
                    if "error" not in result:
                        scraped_pages.append(result["data"])
                        for link in result["links"]:
                            if len(scraped_pages) + len(queue) < max_pages and link not in self.visited and link not in queue:
                                queue.append(link)
                    else:
                        self.rejected_urls.append(result["url"])

            await context.close()
            await browser.close()

        os.makedirs("output", exist_ok=True)
        with open("output/rejected_urls.json", "w", encoding="utf-8") as f:
            json.dump(self.rejected_urls, f, indent=2)
        return scraped_pages

    async def scrape_website(self, state: dict) -> dict:
        try:
            company_url = state.get("company_name", "").strip()
            if not company_url:
                state['error'] = "No company_name provided"
                return state
            if not company_url.startswith(('http://', 'https://')):
                company_url = "https://" + company_url

            pages = await self.scrape_site(company_url, max_pages=100)

            os.makedirs("output", exist_ok=True)
            with open("output/pages_with_content.json", "w", encoding="utf-8") as f:
                json.dump(pages, f, indent=4, ensure_ascii=False)
            state["website_content_individual"] = pages

            compiled = {
                "website_url": company_url,
                "total_pages_scraped": len(pages),
                "compiled_content": {
                    "all_h1_titles": [],
                    "all_h2_titles": [],
                    "all_h3_titles": [],
                    "all_paragraphs": [],
                    "all_faq": [],
                    "all_bullet_points": [],
                    "all_numbered_lists": [],
                    "all_call_to_actions": [],
                    "all_blogs": []
                }
            }

            for page in pages:
                compiled["compiled_content"]["all_h1_titles"].extend(page["titles"]["h1"])
                compiled["compiled_content"]["all_h2_titles"].extend(page["titles"]["h2"])
                compiled["compiled_content"]["all_h3_titles"].extend(page["titles"]["h3"])
                compiled["compiled_content"]["all_paragraphs"].extend(page["paragraphs"])
                compiled["compiled_content"]["all_faq"].extend(page["faq"])
                compiled["compiled_content"]["all_bullet_points"].extend(page["lists"]["bullet_points"])
                compiled["compiled_content"]["all_numbered_lists"].extend(page["lists"]["numbered_lists"])
                compiled["compiled_content"]["all_call_to_actions"].extend(page["call_to_actions"])
                if page["blog"]:
                    compiled["compiled_content"]["all_blogs"].append(page["blog"])

            for key in compiled["compiled_content"]:
                if key != "all_faq" and key != "all_blogs":
                    compiled["compiled_content"][key] = list(dict.fromkeys(compiled["compiled_content"][key]))

            seen = set()
            unique_faqs = []
            for faq in compiled["compiled_content"]["all_faq"]:
                key = (faq.get("question", ""), faq.get("answer", ""))
                if key not in seen:
                    seen.add(key)
                    unique_faqs.append(faq)
            compiled["compiled_content"]["all_faq"] = unique_faqs

            # Deduplicate blogs based on URL and title
            seen = set()
            unique_blogs = []
            for blog in compiled["compiled_content"]["all_blogs"]:
                key = (blog.get("url", ""), blog.get("title", ""))
                if key not in seen:
                    seen.add(key)
                    unique_blogs.append(blog)
            compiled["compiled_content"]["all_blogs"] = unique_blogs

            with open("output/compiled_scraped_data.json", "w", encoding="utf-8") as f:
                print("writing compiled data")
                json.dump(compiled, f, indent=4, ensure_ascii=False)

            state["website_content"] = compiled
            state["scraped_summary"] = {
                "total_pages": compiled["total_pages_scraped"],
                "total_h1": len(compiled["compiled_content"]["all_h1_titles"]),
                "total_h2": len(compiled["compiled_content"]["all_h2_titles"]),
                "total_h3": len(compiled["compiled_content"]["all_h3_titles"]),
                "total_paragraphs": len(compiled["compiled_content"]["all_paragraphs"]),
                "total_faq": len(compiled["compiled_content"]["all_faq"]),
                "total_bullets": len(compiled["compiled_content"]["all_bullet_points"]),
                "total_numbers": len(compiled["compiled_content"]["all_numbered_lists"]),
                "total_ctas": len(compiled["compiled_content"]["all_call_to_actions"]),
                "total_blogs": len(compiled["compiled_content"]["all_blogs"]),
                "average_page_load_speed": sum(self.load_times) / len(self.load_times) if self.load_times else 0.0
            }

            # Write scraped_summary to a separate file
            with open("output/scraped_summary.json", "w", encoding="utf-8") as f:
                print("writing summary")
                json.dump(state["scraped_summary"], f, indent=2, ensure_ascii=False)

            return state

        except Exception as e:
            state["error"] = f"Scraping failed: {str(e)}"
            return state