from urllib.parse import urlparse, urljoin
def normalize(url: str) -> str:
    url = url.strip().lower()
    if '#' in url:
        url = url.split('#')[0]
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url
def get_domain(url: str) -> str:
    return urlparse(url).netloc
def make_absolute(base_url: str, path: str) -> str:
    return urljoin(base_url, path)
def is_valid(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.netloc and parsed.scheme in ('http', 'https'))