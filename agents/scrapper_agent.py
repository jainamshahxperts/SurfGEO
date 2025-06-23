import os
import json
import requests
import concurrent.futures
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from typing import Dict, List
from .schemas import ResearchState


class ScraperAgent:
    def __init__(self):
        self.visited = set()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }

    def clean_text(self, text: str) -> str:
        return ' '.join(text.strip().split())

    def is_valid_url(self, url: str, domain: str) -> bool:
        parsed = urlparse(url)
        return (
            parsed.netloc == domain and
            url not in self.visited and
            not url.endswith(('.pdf', '.jpg', '.png', '.gif', '.css', '.js')) and
            '#' not in url
        )

    def extract_lists(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        bullets, numbers = [], []
        for ul in soup.find_all('ul'):
            if ul.find_parent(['nav', 'header', 'footer']):
                continue
            bullets.extend([self.clean_text(li.get_text()) for li in ul.find_all('li') if self.clean_text(li.get_text())])
        for ol in soup.find_all('ol'):
            numbers.extend([self.clean_text(li.get_text()) for li in ol.find_all('li') if self.clean_text(li.get_text())])
        return {"bullet_points": bullets, "numbered_lists": numbers}

    def extract_faq(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        faqs = []
        containers = soup.select('[class*="faq"], [id*="faq"]')
        for container in containers:
            questions = container.find_all(['h2', 'h3', 'dt'])
            for q in questions:
                question = self.clean_text(q.get_text())
                answer_tag = q.find_next_sibling(['p', 'div', 'dd'])
                answer = self.clean_text(answer_tag.get_text()) if answer_tag else ""
                if question and answer:
                    faqs.append({"question": question, "answer": answer})
        for dl in soup.find_all('dl'):
            for dt, dd in zip(dl.find_all('dt'), dl.find_all('dd')):
                q, a = self.clean_text(dt.text), self.clean_text(dd.text)
                if q and a:
                    faqs.append({"question": q, "answer": a})
        return faqs

    def extract_ctas(self, soup: BeautifulSoup) -> List[str]:
        selectors = [
            'a[class*="btn"]', 'button[class*="btn"]',
            'a[class*="cta"]', 'button[class*="cta"]',
            'a[href*="contact"]', 'a[href*="signup"]', 'a[href*="register"]',
            'a[href*="buy"]', 'a[href*="purchase"]', 'a[href*="order"]'
        ]
        ctas = set()
        for selector in selectors:
            for tag in soup.select(selector):
                txt = self.clean_text(tag.get_text())
                if txt:
                    ctas.add(txt)
        return list(ctas)

    def extract_page_data(self, url: str, soup: BeautifulSoup) -> Dict:
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()
        return {
            "url": url,
            "titles": {
                "h1": [self.clean_text(h.text) for h in soup.find_all("h1")],
                "h2": [self.clean_text(h.text) for h in soup.find_all("h2")],
                "h3": [self.clean_text(h.text) for h in soup.find_all("h3")]
            },
            "paragraphs": [
                self.clean_text(p.text) for p in soup.find_all("p")
                if not p.find_parent("footer") and len(self.clean_text(p.text)) > 20
            ],
            "lists": self.extract_lists(soup),
            "faq": self.extract_faq(soup),
            "call_to_actions": self.extract_ctas(soup)
        }

    def get_links(self, soup: BeautifulSoup, current_url: str, domain: str) -> List[str]:
        links = set()
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            if href.startswith('#'):
                continue
            full_url = urljoin(current_url, href).split('#')[0]
            if self.is_valid_url(full_url, domain):
                links.add(full_url)
        return list(links)

    def scrape_site(self, base_url: str, max_pages: int = 100, max_workers: int = 20) -> List[Dict]:
        self.visited.clear()
        scraped_pages = []
        domain = urlparse(base_url).netloc
        queue = [base_url]

        def scrape_and_extract(url: str):
            try:
                print(f"🔍 Scraping: {url}")
                response = requests.get(url, headers=self.headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                page_data = self.extract_page_data(url, soup)
                links = self.get_links(soup, url, domain)
                return {"url": url, "data": page_data, "links": links}
            except Exception as e:
                print(f"⚠️ Error scraping {url}: {e}")
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            while queue and len(self.visited) < max_pages:
                urls_to_fetch = []
                while queue and len(urls_to_fetch) < max_workers and len(self.visited) + len(urls_to_fetch) < max_pages:
                    url = queue.pop(0).split('#')[0]
                    if url not in self.visited:
                        urls_to_fetch.append(url)
                        self.visited.add(url)

                futures = [executor.submit(scrape_and_extract, url) for url in urls_to_fetch]
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        scraped_pages.append(result["data"])
                        for link in result["links"]:
                            if len(self.visited) + len(queue) < max_pages and link not in self.visited and link not in queue:
                                queue.append(link)

        return scraped_pages

    def scrape_website(self, state: ResearchState) -> ResearchState:
        try:
            company_url = state.get("company_name", "").strip()
            if not company_url:
                state['error'] = "No company_name provided"
                return state
            if not company_url.startswith(('http://', 'https://')):
                company_url = "https://" + company_url

            pages = self.scrape_site(company_url, max_pages=100, max_workers=20)
            os.makedirs("output", exist_ok=True)
            with open("output/pages_with_content.json", "w", encoding="utf-8") as f:
                json.dump(pages, f, indent=2, ensure_ascii=False)
            print(f"📝 Saved detailed per-page content to output/pages_with_content.json")
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
                    "all_call_to_actions": []
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

            for key in compiled["compiled_content"]:
                if key != "all_faq":
                    compiled["compiled_content"][key] = list(dict.fromkeys(compiled["compiled_content"][key]))

            seen = set()
            unique_faqs = []
            for faq in compiled["compiled_content"]["all_faq"]:
                key = (faq.get("question", ""), faq.get("answer", ""))
                if key not in seen:
                    seen.add(key)
                    unique_faqs.append(faq)
            compiled["compiled_content"]["all_faq"] = unique_faqs

            os.makedirs("output", exist_ok=True)
            with open("output/compiled_scraped_data.json", "w", encoding="utf-8") as f:
                json.dump(compiled, f, indent=2, ensure_ascii=False)

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
            }

            print(f"✅ Compiled data from {len(pages)} pages saved to output/compiled_scraped_data.json")
            return state

        except Exception as e:
            state["error"] = f"Scraping failed: {str(e)}"
            return state
