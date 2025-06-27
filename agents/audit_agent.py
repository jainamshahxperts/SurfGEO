import os
import json
import requests
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin
from langchain_core.pydantic_v1 import BaseModel, Field
import google.generativeai as genai
from dotenv import load_dotenv

# === Load environment ===
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# === Gemini Flash 2.0 Model ===
model = genai.GenerativeModel("gemini-2.0-flash")

# === Site Visibility Auditor ===
class SiteVisibilityAuditor:
    def __init__(self, base_url: str):
        self.base_url = base_url if base_url.startswith("http") else "https://" + base_url

    def fetch_url(self, path: str) -> str:
        try:
            res = requests.get(urljoin(self.base_url, path), timeout=10)
            if res.status_code == 200:
                return res.text.strip()
        except Exception:
            pass
        return ""

    def analyze_robots_txt(self, raw_text: str) -> dict:
        rules = {
            "found": bool(raw_text),
            "user_agents": set(),
            "disallow_rules": [],
            "allow_rules": [],
            "crawl_delays": {},
            "sitemaps": []
        }

        current_user_agent = None
        for line in raw_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("user-agent:"):
                current_user_agent = line.split(":", 1)[1].strip()
                rules["user_agents"].add(current_user_agent)
            elif line.lower().startswith("disallow:") and current_user_agent:
                rules["disallow_rules"].append([current_user_agent, line.split(":", 1)[1].strip()])
            elif line.lower().startswith("allow:") and current_user_agent:
                rules["allow_rules"].append([current_user_agent, line.split(":", 1)[1].strip()])
            elif line.lower().startswith("crawl-delay:") and current_user_agent:
                try:
                    delay = float(line.split(":", 1)[1].strip())
                    rules["crawl_delays"][current_user_agent] = delay
                except ValueError:
                    pass
            elif line.lower().startswith("sitemap:"):
                rules["sitemaps"].append(line.split(":", 1)[1].strip())

        rules["user_agents"] = list(rules["user_agents"])
        return rules

    def recommend_robots_txt(self, raw_text: str) -> str:
        prompt = f"""
You are an SEO expert. Here is a robots.txt file:
{raw_text}

Reply with either:
- "No changes required. The site is crawlable and accessible."
- Or give suggestions to fix issues (e.g., remove Disallow: /, add sitemap, reduce crawl delay)
"""
        return model.generate_content(prompt).text.strip()

    def audit_robots_txt(self):
        raw = self.fetch_url("/robots.txt")
        if not raw:
            return {
                "found": False,
                "recommendation": "robots.txt not found. Consider creating one.",
                "analysis": {}
            }

        analysis = self.analyze_robots_txt(raw)
        has_block = any(path == "/" for agent, path in analysis["disallow_rules"])
        recommendation = self.recommend_robots_txt(raw) if has_block else "No changes required. The site is crawlable and accessible."

        return {
            "found": True,
            "recommendation": recommendation,
            "analysis": analysis
        }

    def audit_llms_txt(self):
        text = self.fetch_url("/llms.txt")
        expected_fields = {
            "OpenAI": "User-Agent: GPTBot\nDisallow:",
            "Anthropic": "User-Agent: ClaudeBot\nDisallow:",
            "Google": "User-Agent: Google-Extended\nDisallow:",
            "CommonCrawl": "User-Agent: CCBot\nDisallow:"
        }

        found_bots, suggestions = {}, []
        for name, snippet in expected_fields.items():
            ua = snippet.split("\n")[0].split(":")[1].strip()
            if ua.lower() in text.lower():
                found_bots[name] = True
            else:
                found_bots[name] = False
                suggestions.append(f"Add {name} support: \n{snippet}")

        return {
            "found": bool(text),
            "present_user_agents": [k for k, v in found_bots.items() if v],
            "missing_user_agents": [k for k, v in found_bots.items() if not v],
            "suggestions": suggestions or ["No changes required."]
        }

    def is_valid_sitemap(self, text: str) -> bool:
        try:
            root = ET.fromstring(text)
            return root.tag.endswith("urlset") or root.tag.endswith("sitemapindex")
        except ET.ParseError:
            return False

    def audit_sitemap(self):
        sitemap_text = self.fetch_url("/sitemap.xml")
        robots_text = self.fetch_url("/robots.txt")

        found = bool(sitemap_text)
        valid = self.is_valid_sitemap(sitemap_text) if found else False
        declared = "sitemap" in robots_text.lower()

        suggestions = []
        if not found:
            suggestions.append("sitemap.xml not found.")
        elif not valid:
            suggestions.append("sitemap.xml is malformed.")
        if found and not declared:
            suggestions.append("Add sitemap URL to robots.txt.")

        return {
            "found": found,
            "valid_xml": valid,
            "declared_in_robots": declared,
            "suggestions": suggestions or ["No changes required."]
        }

    def full_audit(self):
        return {
            "robots_txt": self.audit_robots_txt(),
            "llms_txt": self.audit_llms_txt(),
            "sitemap_xml": self.audit_sitemap()
        }

# === Content Audit Function ===
def content_audit_gemini(site_metrics, blog_data):
    sample_blogs = blog_data.get("all_blogs", [])[:3]

    prompt = f"""
You are an SEO and content strategist.

Given:
- site metrics
- sample blog content

Analyze issues in FAQ usage and blog content quality. Respond only in this JSON format:

{{
  "faq_insights": {{
    "issues": [...],
    "recommendations": [...]
  }},
  "blog_optimization": {{
    "issues": [...],
    "recommendations": [...]
  }}
}}

SITE METRICS:
{json.dumps(site_metrics, indent=2)}

BLOG SAMPLE:
{json.dumps(sample_blogs, indent=2)}
"""

    try:
        raw_output = model.generate_content(prompt).text.strip()
        if raw_output.startswith("```json"):
            raw_output = raw_output.replace("```json", "").replace("```", "").strip()
        return json.loads(raw_output)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON from Gemini", "raw": raw_output}


# === Pydantic State Model ===
class AuditAgentState(BaseModel):
    company_name: str = Field(description="The name of the company.")
    website_content: Dict[str, Any] = Field(description="The scraped content of the company's website.")

# === Main Audit Agent ===
class AuditAgent:
    def run_audit(self, state: Dict[str, Any]) -> Dict[str, Any]:
        print("inside")
        company_name = state["company_name"]

        site_metrics = state["scraped_summary"]
        blog_list = state["website_content"]["compiled_content"]["all_blogs"]
        blog_data = {"all_blogs": blog_list}

        if not company_name:
            state["error"] = "Missing company name, website content, or BASE_URL for audit."
            return state
        site_auditor = SiteVisibilityAuditor(company_name)
        technical_audit_report = site_auditor.full_audit()
        content_audit_report = content_audit_gemini(site_metrics, blog_data)

        state["audit_report"] = {
            "technical_seo_audit": technical_audit_report,
            "content_audit": content_audit_report
        }
        print("---AUDIT complete---")
        with open("output/audit_report.json", "w") as f:
            json.dump(state["audit_report"], f, indent=4)
        return state


# === LangGraph Node Callable ===
def run_audit_node(state: Dict[str, Any]) -> Dict[str, Any]:
    print("---RUNNING AUDIT AGENT---")
    agent = AuditAgent()
    return agent.run_audit(state)
