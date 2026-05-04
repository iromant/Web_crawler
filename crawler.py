import collections
from url_utils import normalize, get_domain
from downloader import Downloader
from link_extractor import LinkExtractor


class Crawler:
    def __init__(self, start_url: str, max_depth: int = 2, max_pages: int = 10):
        self.start_url = normalize(start_url)
        self.target_domain = get_domain(self.start_url)
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.queue = collections.deque([(self.start_url, 0)])
        self.visited = {self.start_url}
        self.downloader = Downloader()
        self.extractor = LinkExtractor()
        self.counter = 0
    def run(self):
        print(f"Запуск краулера на домене: {self.target_domain}")
        while self.queue and self.counter < self.max_pages:
            current_url, depth = self.queue.popleft()
            self._process_task(current_url, depth)
        print(f"Работа завершена. Всего страниц: {self.counter}")
    def _process_task(self, url: str, depth: int):
        self.counter += 1
        response = self.downloader.fetch(url)
        if response.error:
            print(f"[{self.counter}] Ошибка на {url}: {response.error}")
            return
        print(f"[{self.counter}] {url} (Глубина: {depth}) - OK")
        if depth < self.max_depth:
            new_links = self.extractor.extract(response.html, url, self.target_domain)
            for link in new_links:
                if link not in self.visited:
                    self.visited.add(link)
                    self.queue.append((link, depth + 1))


if __name__ == "__main__":
    user_url = input("Введите стартовый URL (например, youtube.com): ")
    try:
        user_depth = int(input("Введите максимальную глубину: "))
        user_pages = int(input("Введите лимит страниц: "))
    except ValueError:
        print("Ошибка: Глубина и лимит страниц должны быть целыми числами")
        print("Будут использованы значения по умолчанию: глубина 2, страниц 10.")
        user_depth = 2
        user_pages = 10
    my_crawler = Crawler(user_url, max_depth=user_depth, max_pages=user_pages)
    my_crawler.run()