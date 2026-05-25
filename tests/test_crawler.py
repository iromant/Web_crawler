import pytest
import os
from unittest.mock import MagicMock, patch

from url_utils import normalize, get_domain, make_absolute, is_valid
from downloader import Downloader, ResponseData
from link_extractor import LinkExtractor
from crawler import Crawler

def test_normalize_url():
    assert normalize("youtube.com/") == "https://youtube.com"
    assert normalize("https://example.com/") == "https://example.com"
    assert normalize("http://test.com/page/") == "http://test.com/page"
    assert normalize("https://example.com/page#section") == "https://example.com/page"
    assert normalize("wiki.org") == "https://wiki.org"


def test_get_domain():
    assert get_domain("https://www.youtube.com/watch?v=123") == "youtube.com"
    assert get_domain("http://wikipedia.org/wiki/Main") == "wikipedia.org"
    assert get_domain("https://ru.wikipedia.org") == "ru.wikipedia.org"


def test_make_absolute():
    assert make_absolute("https://example.com/blog", "/about") == "https://example.com/about"
    assert make_absolute("https://example.com/page", "http://other.com") == "http://other.com"


def test_is_valid():
    assert is_valid("https://example.com") is True
    assert is_valid("javascript:void(0)") is False
    assert is_valid("mailto:info@test.com") is False


def test_link_extractor():
    extractor = LinkExtractor()
    html_content = """
        <html>
            <body>
                <a href="/about">Внутренняя</a>
                <a href="https://youtube.com/watch">Video</a>
            </body>
        </html>
    """
    target_domains = {"youtube.com"}
    base_url = "https://youtube.com"

    extracted = extractor.extract(html_content, base_url, target_domains)
    assert "https://youtube.com/about" in extracted
    assert "https://youtube.com/watch" in extracted


def test_downloader_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {'Content-Type': 'text/html', 'Last-Modified': 'Mon, 25 May 2026 GMT'}
    mock_response.text = "<html>Hello</html>"

    with patch('requests.get', return_value=mock_response):
        downloader = Downloader()
        result = downloader.fetch("https://example.com")
        assert result.status_code == 200
        assert result.html == "<html>Hello</html>"


def test_downloader_not_modified():
    mock_response = MagicMock()
    mock_response.status_code = 304

    with patch('requests.get', return_value=mock_response):
        downloader = Downloader()
        result = downloader.fetch("https://example.com", last_modified="Mon, 25 May 2026 GMT")
        assert result.status_code == 304


def test_crawler_filters():
    crawler = Crawler(start_urls=["https://example.com"], allow_filters=["works"], block_filters=["bad-word"])
    assert crawler._is_match_filters("https://example.com/howyoutubeworks") is True
    assert crawler._is_match_filters("https://example.com/works/bad-word") is False
    assert crawler._is_match_filters("https://example.com/regular-page") is False


def test_crawler_can_fetch_robots_exception():
    crawler = Crawler(start_urls=["https://broken-robots.com"])
    with patch('urllib.robotparser.RobotFileParser.read', side_effect=Exception("Error")):
        assert crawler._can_fetch("https://broken-robots.com/any-page") is True


def test_crawler_cache_invalidation_on_new_domain():
    mock_old_queue = [["https://youtube.com/watch", 1]]
    with patch('os.path.exists', return_value=True), \
            patch('crawler.Crawler._load_json', return_value=mock_old_queue), \
            patch('os.remove') as mock_remove:
        crawler = Crawler(start_urls=["wikipedia.org"])
        assert mock_remove.call_count >= 1
        assert crawler.queue[0][0] == "https://wikipedia.org"


def test_crawler_resume_same_domain():
    mock_saved_queue = [["https://example.com/cached-page", 1]]
    mock_saved_dates = {"https://example.com": "some_date"}
    mock_saved_graph = {"https://example.com": []}

    def mock_load(filename):
        if "queue" in filename: return mock_saved_queue
        if "dates" in filename: return mock_saved_dates
        if "graph" in filename: return mock_saved_graph
        return None

    with patch('os.path.exists', return_value=True), \
            patch('crawler.Crawler._load_json', side_effect=mock_load), \
            patch('os.remove'):

        crawler = Crawler(start_urls=["https://example.com"])
        assert crawler.page_dates == mock_saved_dates
        assert crawler.graph == mock_saved_graph
        assert crawler.queue[0][0] == "https://example.com/cached-page"


def test_crawler_worker_304_and_error():
    mock_304 = ResponseData(html="", status_code=304, url="https://example.com/page1")
    mock_err = ResponseData(html="", status_code=0, url="https://example.com/page2", error="TIMEOUT")

    with patch('downloader.Downloader.fetch', side_effect=[mock_304, mock_err]), \
            patch('crawler.Crawler._can_fetch', return_value=True), \
            patch('crawler.Crawler._load_json', return_value=None), \
            patch('crawler.Crawler._save_json'):
        crawler = Crawler(start_urls=["https://example.com/page1", "https://example.com/page2"], max_pages=5)
        crawler.graph["https://example.com/page1"] = ["https://example.com/subpage-from-cache"]

        crawler.run(max_workers=1, max_depth=2)
        assert crawler.counter == 1


def test_crawler_full_run_integration():
    mock_resp_main = MagicMock()
    mock_resp_main.status_code = 200
    mock_resp_main.html = '<a href="https://example.com/about">About Link</a>'
    mock_resp_main.error = None
    mock_resp_main.last_modified = "Mon, 25 May 2026 GMT"
    mock_resp_main.url = "https://example.com"

    mock_resp_about = MagicMock()
    mock_resp_about.status_code = 200
    mock_resp_about.html = '<html>Welcome</html>'
    mock_resp_about.error = None
    mock_resp_about.last_modified = "Mon, 25 May 2026 GMT"
    mock_resp_about.url = "https://example.com/about"

    with patch('downloader.Downloader.fetch', side_effect=[mock_resp_main, mock_resp_about]), \
            patch('crawler.Crawler._can_fetch', return_value=True), \
            patch('crawler.Crawler._load_json', return_value=None), \
            patch('crawler.Crawler._save_json'), \
            patch('os.path.exists', return_value=False):
        crawler = Crawler(start_urls=["https://example.com"], max_pages=5)
        crawler.run(max_workers=2, max_depth=2)

        assert crawler.counter == 2
        assert "https://example.com/about" in crawler.page_dates
        assert "https://example.com/about" in crawler.graph["https://example.com"]