import requests
from dataclasses import dataclass
from typing import Optional

@dataclass
class ResponseData:
    html: str
    status_code: int
    url: str
    error: Optional[str] = None
    last_modified: Optional[str] = None

class Downloader:
    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Compatible; MyPythonCrawler/1.0)'
        }

    def fetch(self, url: str, last_modified: str = None) -> ResponseData:
        try:
            headers = self.headers.copy()
            if last_modified:
                headers['If-Modified-Since'] = last_modified

            response = requests.get(
                url,
                timeout=self.timeout,
                headers=headers,
                stream=True,
                allow_redirects=True
            )

            if response.status_code == 304:
                return ResponseData("", 304, url)

            server_date = response.headers.get('Last-Modified', response.headers.get('Date'))

            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                return ResponseData("", response.status_code, url, error="Not HTML", last_modified=server_date)

            return ResponseData(response.text, response.status_code, response.url, last_modified=server_date)

        except requests.exceptions.TooManyRedirects:
            return ResponseData("", 300, url, error="Too many redirects (>5)")
        except requests.exceptions.Timeout:
            return ResponseData("", 0, url, error="TIMEOUT")
        except Exception as e:
            return ResponseData("", 0, url, error=str(e))