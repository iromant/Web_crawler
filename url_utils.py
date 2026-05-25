from urllib.parse import urlparse, urljoin


def normalize(url: str) -> str:
    url = url.strip().lower()
    if '#' in url:
        url = url.split('#')[0]
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    parsed = urlparse(url)
    path = parsed.path
    if path == '/':
        url = f"{parsed.scheme}://{parsed.netloc}"
    elif path.endswith('/'):
        url = url.rstrip('/')

    return url


def get_domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith('www.'):
        return netloc[4:]
    return netloc


def make_absolute(base_url: str, path: str) -> str:
    return urljoin(base_url, path)


def is_valid(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.netloc and parsed.scheme in ('http', 'https'))