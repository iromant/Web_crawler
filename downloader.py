import requests
from dataclasses import dataclass
from typing import Optional

@dataclass
class ResponseData:
    html: str
    status_code: int
    url: str
    error: Optional[str] = None
class Downloader:
    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Compatible; MyPythonCrawler/1.0)'
        }

    def fetch(self, url: str) -> ResponseData:
        try:
            response = requests.get(
                url,
                timeout=self.timeout,
                headers=self.headers,
                stream=True
            )
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                return ResponseData("", response.status_code, url, error="Not HTML")
            html_content = response.text
            return ResponseData(html_content, response.status_code, response.url)
        except requests.exceptions.Timeout:
            return ResponseData("", 0, url, error="Timeout")
        except Exception as e:
            return ResponseData("", 0, url, error=str(e))