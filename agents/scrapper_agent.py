import os
import json
import asyncio
import time
import logging
from urllib.parse import urlparse, urljoin, urlunparse
from typing import Dict, List, Optional, TYPE_CHECKING, Any
from parsel import Selector
from playwright.async_api import async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .schemas import ResearchState

class ScraperAgent:
    def __init__(self):
        logger.info("Initializing ScraperAgent")
        self.visited = set()
        self.rejected_urls = []
        self.domain_cache = {}
        self.semaphore = asyncio.Semaphore(20)  # Concurrent pages
        self.load_times = []
        logger.debug("ScraperAgent initialized with empty visited set, rejected_urls list, domain_cache, and semaphore limit of 20")

    def clean_text(self, text: str) -> str:
        if not text:
            logger.debug("Cleaning text: empty input, returning empty string")
            return ""
        cleaned = ' '.join(text.strip().split())
        logger.debug(f"Cleaned text: '{text}' -> '{cleaned}'")
        return cleaned

    def normalize_domain(self, domain: str) -> str:
        logger.debug(f"Normalizing domain: {domain}")
        if domain not in self.domain_cache:
            normalized = domain.lower().replace("www.", "").strip()
            self.domain_cache[domain] = normalized
            logger.debug(f"Added to domain cache: {domain} -> {normalized}")
        else:
            logger.debug(f"Domain found in cache: {domain}")
        return self.domain_cache[domain]

    def normalize_url(self, url: str) -> str:
        logger.debug(f"Normalizing URL: {url}")
        parsed = urlparse(url)
        normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', '', ''))
        logger.debug(f"Normalized URL: {url} -> {normalized}")
        return normalized

    def is_valid_url(self, url: str, domain: str) -> bool:
        logger.debug(f"Checking if URL is valid: {url} for domain: {domain}")
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
            logger.debug(f"URL rejected: {url}")
            self.rejected_urls.append(url)
        else:
            logger.debug(f"URL valid: {url}")
        return is_valid

    def extract_lists(self, selector: Selector) -> Dict[str, List[str]]:
        logger.debug("Extracting lists from page")
        bullets = [
            self.clean_text(li) for li in selector.xpath('//ul[not(ancestor::nav or ancestor::header or ancestor::footer)]//li/text()').getall()
            if li.strip()
        ]
        numbers = [
            self.clean_text(li) for li in selector.xpath('//ol//li/text()').getall()
            if li.strip()
        ]
        logger.debug(f"Extracted {len(bullets)} bullet points and {len(numbers)} numbered list items")
        return {"bullet_points": bullets, "numbered_lists": numbers}

    def extract_faq(self, selector: Selector) -> List[Dict[str, str]]:
        logger.debug("Extracting FAQs from page")
        faqs = []
        faq_containers = selector.xpath('//*[contains(@class, "faq") or contains(@id, "faq")]')
        logger.debug(f"Found {len(faq_containers)} FAQ containers")
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
                    logger.debug(f"Extracted FAQ: Q: {question} | A: {answer}")
        for dl in selector.xpath('//dl'):
            for dt, dd in zip(dl.xpath('./dt/text()').getall(), dl.xpath('./dd/text()').getall()):
                q, a = self.clean_text(dt), self.clean_text(dd)
                if q and a:
                    faqs.append({"question": q, "answer": a})
                    logger.debug(f"Extracted FAQ from dl: Q: {q} | A: {a}")
        logger.debug(f"Total FAQs extracted: {len(faqs)}")
        return faqs

    def extract_ctas(self, selector: Selector) -> List[str]:
        logger.debug("Extracting CTAs from page")
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
                    logger.debug(f"Extracted CTA: {txt}")
        logger.debug(f"Total unique CTAs extracted: {len(ctas)}")
        return list(ctas)

    def extract_blogs(self, selector: Selector, url: str) -> Dict[str, Any]:
        logger.debug(f"Extracting blog data from URL: {url}")
        blog_indicators = ['/blog/', '/news/', '/articles/', '/post/', '/posts/']
        is_blog = any(indicator in url.lower() for indicator in blog_indicators) or \
                  selector.xpath('//article').get() is not None
        logger.debug(f"Is blog page: {is_blog}")

        if not is_blog:
            logger.debug("Not a blog page, returning empty dict")
            return {}

        title = self.clean_text(
            selector.xpath('//h1/text()').get(default='') or
            selector.xpath('//h2/text()').get(default='')
        )
        logger.debug(f"Blog title: {title}")

        content = [
            self.clean_text(p) for p in selector.xpath(
                '//article//p[not(ancestor::footer) and string-length(text()) > 20]/text() | '
                '//main//p[not(ancestor::footer) and string-length(text()) > 20]/text()'
            ).getall()
        ]
        logger.debug(f"Extracted {len(content)} paragraphs of blog content")

        date = self.clean_text(
            selector.xpath(
                '//time/text() | '
                '//meta[@name="date" or @property="article:published_time"]/@content | '
                '//*[contains(@class, "date") or contains(@class, "published")]/text()'
            ).get(default='')
        )
        logger.debug(f"Blog publication date: {date}")

        if title or content:
            blog_data = {
                "url": url,
                "title": title,
                "content": content,
                "date": date
            }
            logger.debug(f"Blog data extracted: {json.dumps(blog_data, indent=2)}")
            return blog_data
        logger.debug("No title or content found, returning empty dict")
        return {}

    def extract_page_data(self, url: str, selector: Selector) -> Dict:
        logger.debug(f"Extracting page data for URL: {url}")
        blog_data = self.extract_blogs(selector, url)
        page_data = {
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
        logger.debug(f"Page data extracted: {url} - H1: {len(page_data['titles']['h1'])}, "
                     f"H2: {len(page_data['titles']['h2'])}, H3: {len(page_data['titles']['h3'])}, "
                     f"Paragraphs: {len(page_data['paragraphs'])}, FAQs: {len(page_data['faq'])}, "
                     f"CTAs: {len(page_data['call_to_actions'])}, Blog: {bool(page_data['blog'])}")
        return page_data

    def get_links(self, selector: Selector, current_url: str, domain: str) -> List[str]:
        logger.debug(f"Extracting links from URL: {current_url}")
        links = set()
        for href in selector.xpath('//a/@href').getall():
            if href.startswith('#'):
                logger.debug(f"Skipping anchor link: {href}")
                continue
            full_url = self.normalize_url(urljoin(current_url, href).split('#')[0])
            full_url = full_url.replace('fframeworks', 'frameworks')
            if self.is_valid_url(full_url, domain):
                links.add(full_url)
                logger.debug(f"Valid link added: {full_url}")
        logger.debug(f"Total unique links extracted: {len(links)}")
        return list(links)

    async def scrape_and_extract(self, url: str, domain: str, browser_context, retries: int = 2) -> Dict:
        logger.info(f"Scraping URL: {url}")
        async with self.semaphore:
            for attempt in range(retries):
                try:
                    start_time = time.time()
                    logger.debug(f"Creating new page for URL: {url}, attempt {attempt + 1}/{retries}")
                    page = await browser_context.new_page()
                    await page.route("**/*.{png,jpg,gif,css,js,woff,woff2,mp4,webm}", lambda route: route.abort())
                    logger.debug(f"Blocked resource types for {url}")
                    try:
                        await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                        logger.debug(f"Successfully loaded {url}")
                    except PlaywrightTimeoutError:
                        logger.warning(f"Timeout on {url}, capturing partial content")
                        content = await page.content()
                    else:
                        content = await page.content()
                    await page.close()
                    load_time = time.time() - start_time
                    self.load_times.append(load_time)
                    logger.debug(f"Page load time: {load_time:.2f} seconds")

                    selector = Selector(text=content)
                    data = self.extract_page_data(url, selector)
                    links = self.get_links(selector, url, domain)
                    logger.info(f"Successfully scraped {url} - Extracted data and {len(links)} links")
                    return {
                        "url": url,
                        "data": data,
                        "links": links
                    }
                except Exception as e:
                    logger.error(f"Error scraping {url} (attempt {attempt + 1}/{retries}): {str(e)}")
                    if attempt == retries - 1:
                        logger.error(f"Max retries reached for {url}, marking as rejected")
                        self.rejected_urls.append(url)
                        return {"url": url, "error": str(e)}
                    await asyncio.sleep(0.1)
                finally:
                    if 'page' in locals():
                        await page.close()
                        logger.debug(f"Closed page for {url}")
        logger.error(f"Failed to scrape {url} after {retries} attempts")
        return {"url": url, "error": "Max retries reached"}

    async def scrape_site(self, base_url: str, max_pages: int = 100) -> List[Dict]:
        logger.info(f"Starting site scrape for {base_url} with max_pages: {max_pages}")
        self.visited.clear()
        self.rejected_urls.clear()
        self.load_times.clear()
        logger.debug("Cleared visited, rejected_urls, and load_times")
        scraped_pages = []
        if not urlparse(base_url).scheme:
            base_url = "https://" + base_url
            logger.debug(f"Added https scheme to base_url: {base_url}")

        domain = self.normalize_domain(urlparse(base_url).netloc)
        queue = [self.normalize_url(base_url)]
        logger.debug(f"Initialized queue with base URL: {base_url}")

        async with async_playwright() as p:
            logger.debug("Launching Playwright browser")
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            logger.debug("Browser context created with user agent")

            while queue and len(scraped_pages) < max_pages:
                batch_size = min(20, max_pages - len(scraped_pages), len(queue))
                logger.debug(f"Processing batch of {batch_size} URLs")
                urls_to_fetch = []
                for _ in range(batch_size):
                    if not queue:
                        break
                    url = queue.pop(0)
                    if url not in self.visited:
                        urls_to_fetch.append(url)
                        self.visited.add(url)
                        logger.debug(f"Added URL to fetch: {url}")

                tasks = [self.scrape_and_extract(url, domain, context) for url in urls_to_fetch]
                logger.debug(f"Created {len(tasks)} scraping tasks")
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Exception in batch processing: {str(result)}")
                        continue
                    if "error" not in result:
                        scraped_pages.append(result["data"])
                        logger.info(f"Successfully scraped page: {result['url']}, total pages: {len(scraped_pages)}")
                        for link in result["links"]:
                            if len(scraped_pages) + len(queue) < max_pages and link not in self.visited and link not in queue:
                                queue.append(link)
                                logger.debug(f"Added new link to queue: {link}")
                    else:
                        logger.warning(f"Failed to scrape {result['url']}: {result['error']}")
                        self.rejected_urls.append(result["url"])

            await context.close()
            await browser.close()
            logger.debug("Closed browser context and browser")

        os.makedirs("output", exist_ok=True)
        logger.debug("Created output directory")
        with open("output/rejected_urls.json", "w", encoding="utf-8") as f:
            json.dump(self.rejected_urls, f, indent=2)
            logger.info(f"Saved {len(self.rejected_urls)} rejected URLs to output/rejected_urls.json")
        logger.info(f"Completed site scrape, total pages scraped: {len(scraped_pages)}")
        return scraped_pages

    async def scrape_website(self, state: dict) -> dict:
        logger.info("Starting website scrape")
        try:
            company_url = state.get("company_name", "").strip()
            logger.debug(f"Company URL from state: {company_url}")
            if not company_url:
                logger.error("No company_name provided")
                state['error'] = "No company_name provided"
                return state
            if not company_url.startswith(('http://', 'https://')):
                company_url = "https://" + company_url
                logger.debug(f"Added https scheme to company_url: {company_url}")

            pages = await self.scrape_site(company_url, max_pages=100)
            logger.info(f"Scraped {len(pages)} pages")

            os.makedirs("output", exist_ok=True)
            with open("output/pages_with_content.json", "w", encoding="utf-8") as f:
                json.dump(pages, f, indent=4, ensure_ascii=False)
                logger.info("Saved individual page content to output/pages_with_content.json")

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
            logger.debug("Initialized compiled content structure")

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
                logger.debug(f"Processed page {page['url']} for compiled content")

            for key in compiled["compiled_content"]:
                if key != "all_faq" and key != "all_blogs":
                    compiled["compiled_content"][key] = list(dict.fromkeys(compiled["compiled_content"][key]))
                    logger.debug(f"Deduplicated {key}: {len(compiled['compiled_content'][key])} items")

            seen = set()
            unique_faqs = []
            for faq in compiled["compiled_content"]["all_faq"]:
                key = (faq.get("question", ""), faq.get("answer", ""))
                if key not in seen:
                    seen.add(key)
                    unique_faqs.append(faq)
            compiled["compiled_content"]["all_faq"] = unique_faqs
            logger.debug(f"Deduplicated FAQs: {len(unique_faqs)} unique FAQs")

            seen = set()
            unique_blogs = []
            for blog in compiled["compiled_content"]["all_blogs"]:
                key = (blog.get("url", ""), blog.get("title", ""))
                if key not in seen:
                    seen.add(key)
                    unique_blogs.append(blog)
            compiled["compiled_content"]["all_blogs"] = unique_blogs
            logger.debug(f"Deduplicated blogs: {len(unique_blogs)} unique blogs")

            with open("output/compiled_scraped_data.json", "w", encoding="utf-8") as f:
                logger.info("Writing compiled data to output/compiled_scraped_data.json")
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
            logger.debug(f"Scraped summary: {json.dumps(state['scraped_summary'], indent=2)}")

            with open("output/scraped_summary.json", "w", encoding="utf-8") as f:
                logger.info("Writing summary to output/scraped_summary.json")
                json.dump(state["scraped_summary"], f, indent=2, ensure_ascii=False)

            logger.info("Website scrape completed successfully")
            return state

        except Exception as e:
            logger.error(f"Scraping failed: {str(e)}")
            state["error"] = f"Scraping failed: {str(e)}"
            return state