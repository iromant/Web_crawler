import re
from url_utils import make_absolute, get_domain

class LinkExtractor:
    def __init__(self):
        self.pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href=["\'](.*?)["\']', re.IGNORECASE)
    def extract(self, html: str, base_url: str,target_domain: str ) -> list[str]:
        found_links = self.pattern.findall(html)
        clean_links = []
        for link in found_links:
            full_url = make_absolute(base_url, link)
            if get_domain(full_url) == target_domain:
                clean_links.append(full_url)
        return clean_links
