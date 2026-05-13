import collections
import json
import networkx as nx
import matplotlib.pyplot as plt
import os
import time
import random
import threading

from urllib.robotparser import RobotFileParser
from url_utils import normalize, get_domain
from downloader import Downloader
from link_extractor import LinkExtractor
from concurrent.futures import ThreadPoolExecutor


def visualize():
    try:
        with open("link_graph.json", "r", encoding='utf-8') as f:
            data = json.load(f)

    except FileNotFoundError:
        print("Ошибка: Файл link_graph.json не найден.")
        return

    G = nx.DiGraph()

    for source, targets in data.items():
        for target in targets:
            G.add_edge(source, target)

    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, k=0.3)
    nx.draw_networkx_nodes(G, pos, node_size=500, node_color='skyblue', alpha=0.8)
    nx.draw_networkx_edges(G, pos, width=1.0, alpha=0.5, edge_color='gray', arrows=True)
    labels = {node: node.split('/')[-1] if node.split('/')[-1] else node.split('/')[-2] for node in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=8)

    plt.title("Визуализация структуры ссылок сайта")
    plt.axis('off')
    plt.show()


class Crawler:
    def __init__(self, start_urls: list[str], max_depth: int = 2, max_pages: int = 10,
                 allow_filters: list = None, block_filters: list = None):
        self.start_urls = [normalize(url) for url in start_urls]
        self.target_domains = {get_domain(url) for url in self.start_urls}

        self.max_depth = max_depth
        self.max_pages = max_pages

        self.queue = collections.deque([(url, 0) for url in self.start_urls])
        self.visited = set(self.start_urls)

        self.downloader = Downloader()
        self.extractor = LinkExtractor()

        self.counter = 0
        self.robots_cache = {}
        self.page_dates = {}
        self.graph = {}

        self.lock = threading.Lock()

        self.db_file = "cache_dates.json"
        self.queue_file = "queue_cache.json"
        self.graph_file = "link_graph.json"

        self.allow_filters = allow_filters or []
        self.block_filters = block_filters or []

        self.page_dates = self._load_dates()
        saved_queue = self._load_json(self.queue_file)

        if saved_queue:
            first_url = saved_queue[0][0]

            if get_domain(first_url) in self.target_domains:
                self.queue = collections.deque([tuple(x) for x in saved_queue])
                self.visited = {x[0] for x in saved_queue}
            else:
                self.queue = collections.deque([(url, 0) for url in self.start_urls])
                self.visited = set(self.start_urls)
        else:
            self.queue = collections.deque([(url, 0) for url in self.start_urls])
            self.visited = set(self.start_urls)
    def _load_json(self, file_path) -> list | dict:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding='utf-8') as f:
                return json.load(f)
        return [] if "queue" in file_path else {}

    def _load_dates(self) -> dict:
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _can_fetch(self, url: str) -> bool:
        domain = get_domain(url)
        with self.lock:
            if domain not in self.robots_cache:
                rp = RobotFileParser()
                rp.set_url(f"https://{domain}/robots.txt")
                try:
                    rp.read()
                    self.robots_cache[domain] = rp
                except:
                    return True
            return self.robots_cache[domain].can_fetch(self.downloader.headers["User-Agent"], url)

    def _save_json(self, file_path, data):
        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _save_graph(self):
        with open(self.graph_file, 'w', encoding='utf-8') as f:
            json.dump(self.graph, f, indent=4, ensure_ascii=False)

    def _should_follow(self, url: str) -> bool:
        for block in self.block_filters:
            if block in url:
                return False
        if self.allow_filters:
            return any(allow in url for allow in self.allow_filters)
        return True

    def run(self, max_workers: int = 8):
        is_hunting = len(self.allow_filters) > 0
        effective_depth = 999 if is_hunting else self.max_depth
        print(f"Запуск на доменах: {self.target_domains}")
        print(f"Режим: {'ОХОТА' if is_hunting else 'КАРТА'}")

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                while True:
                    with self.lock:
                        if self.counter >= self.max_pages:
                            break
                        if not self.queue:
                            if threading.active_count() > 1:
                                time.sleep(0.5)
                                continue
                            else:
                                break
                        current_url, depth = self.queue.popleft()
                    executor.submit(self._process_task, current_url, depth, effective_depth)
        except KeyboardInterrupt:
            print("\nПрерывание... Сохранение данных.")
        finally:
            self._save_json(self.db_file, self.page_dates)
            self._save_json(self.queue_file, list(self.queue))
            self._save_graph()
        print(f"Завершено. Страниц: {self.counter}")

    def _process_task(self, url: str, depth: int, max_d: int):
        with self.lock:
            if self.counter >= self.max_pages:
                return

        time.sleep(random.uniform(1, 2))

        if not self._can_fetch(url):
            with self.lock:
                print(f"[-] Доступ запрещен robots.txt: {url}")
            return

        with self.lock:
            last_mod = self.page_dates.get(url)

        response = self.downloader.fetch(url, last_mod)

        if response.status_code == 304 and depth < max_d:
            response = self.downloader.fetch(url, None)

        if response.error:
            with self.lock:
                print(f"[!] Ошибка сети: {url} -> {response.error}")
            return

        if response.status_code not in [200, 304]:
            with self.lock:
                print(f"[-] Пропущено: {url} (Статус: {response.status_code})")
            return

        with self.lock:
            if self.counter >= self.max_pages:
                return

            is_target = self._should_follow(url) or depth == 0

            if is_target:
                self.counter += 1
                current_num = self.counter
                status_text = "OK" if response.status_code == 200 else "304 Not Modified"
                print(f"[{current_num}] {url} (Глубина: {depth}) - {status_text} (Целевая)")

                if response.status_code == 200:
                    self.page_dates[url] = response.last_modified or "visited_no_date"

        if depth < max_d and response.status_code == 200 and response.html:
            new_links = self.extractor.extract(response.html, url, self.target_domains)

            with self.lock:
                self.graph[url] = list(set(new_links))

                if self.counter < self.max_pages:
                    for link in new_links:
                        if link not in self.visited:
                            self.visited.add(link)
                            self.queue.append((link, depth + 1))

if __name__ == "__main__":
    raw_input = input("Введите стартовые URL через запятую: ")
    user_urls = [u.strip() for u in raw_input.split(",") if u.strip()]
    if user_urls:
        try:
            user_depth = int(input("Введите макс. глубину: "))
            user_pages = int(input("Введите лимит страниц: "))
            a_input = input("Искать только ссылки с (через запятую): ")
            user_allows = [x.strip() for x in a_input.split(",") if x.strip()]
            b_input = input("Игнорировать ссылки с (через запятую): ")
            user_blocks = [x.strip() for x in b_input.split(",") if x.strip()]

            my_crawler = Crawler(user_urls, user_depth, user_pages, user_allows, user_blocks)
            my_crawler.run()
            #visualize()
        except ValueError:
            print("Ошибка ввода.")
