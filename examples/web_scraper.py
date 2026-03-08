"""
Realistic production example: Web scraping pipeline.

This simulates a typical scraping workflow with:
- Requests for HTTP
- BeautifulSoup for HTML parsing
- JSON/CSV output
"""

import requests
from bs4 import BeautifulSoup
import json
import csv
import io
from datetime import datetime
from urllib.parse import urljoin, urlparse

# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class WebScraper:
    """A simple, production-style web scraper."""

    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "envcore-demo/1.0 (https://github.com/janbremec/envcore)",
        })
        self.results: list[dict] = []

    def fetch(self, url: str) -> BeautifulSoup | None:
        """Fetch and parse a URL."""
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as e:
            print(f"  Error fetching {url}: {e}")
            return None

    def extract_links(self, soup: BeautifulSoup) -> list[dict]:
        """Extract all links from a page."""
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(self.base_url, href)
            links.append({
                "text": a.get_text(strip=True)[:100],
                "url": full_url,
                "domain": urlparse(full_url).netloc,
            })
        return links

    def extract_headings(self, soup: BeautifulSoup) -> list[dict]:
        """Extract all headings from a page."""
        headings = []
        for level in range(1, 7):
            for h in soup.find_all(f"h{level}"):
                headings.append({
                    "level": level,
                    "text": h.get_text(strip=True)[:200],
                })
        return headings

    def scrape(self, url: str) -> dict:
        """Scrape a single page and return structured data."""
        print(f"  Scraping: {url}")
        soup = self.fetch(url)
        if soup is None:
            return {"url": url, "error": "Failed to fetch"}

        title = soup.title.string.strip() if soup.title else "No title"
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag:
            meta_desc = meta_tag.get("content", "")

        result = {
            "url": url,
            "title": title,
            "meta_description": meta_desc,
            "headings": self.extract_headings(soup),
            "links_count": len(soup.find_all("a", href=True)),
            "images_count": len(soup.find_all("img")),
            "scraped_at": datetime.utcnow().isoformat(),
        }
        self.results.append(result)
        return result

    def to_json(self) -> str:
        return json.dumps(self.results, indent=2)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

print("Web Scraper Demo")
print("=" * 40)

scraper = WebScraper("https://example.com")

# Scrape example.com (a safe, always-available test page)
result = scraper.scrape("https://example.com")

print(f"\n  Title: {result.get('title', 'N/A')}")
print(f"  Links: {result.get('links_count', 0)}")
print(f"  Images: {result.get('images_count', 0)}")
print(f"  Headings: {len(result.get('headings', []))}")

print(f"\nScraped {len(scraper.results)} page(s)")
print("Done!")
