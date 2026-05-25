import re
from url_utils import make_absolute, get_domain, normalize

class LinkExtractor:
    def __init__(self):
        self.pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href=["\'](.*?)["\']', re.IGNORECASE)

    def extract(self, html: str, base_url: str, target_domains: set) -> list[str]:
        found_links = self.pattern.findall(html)
        clean_links = []
        for link in found_links:
            full_url = make_absolute(base_url, link)
            try:
                normalized_url = normalize(full_url)
                if get_domain(full_url) in target_domains:
                    clean_links.append(normalized_url)
            except Exception:
                continue
        return clean_links