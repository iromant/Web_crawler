import os
import json
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

from url_utils import normalize, get_domain
from downloader import Downloader
from link_extractor import LinkExtractor


class Crawler:
    def __init__(self, start_urls, max_pages=50, allow_filters=None, block_filters=None):
        self.start_urls = start_urls
        self.max_pages = max_pages
        self.allow_filters = allow_filters or []
        self.block_filters = block_filters or []

        self.queue_file = "queue_cache.json"
        self.dates_file = "page_dates.json"
        self.graph_file = "graph.json"

        self.downloader = Downloader()
        self.extractor = LinkExtractor()

        self.lock = threading.Lock()
        self.counter = 0
        self.visited = set()
        self.queue = []
        self.page_dates = {}
        self.graph = {}

        if not self.start_urls:
            return

        normalized_start = normalize(self.start_urls[0])
        current_domain = get_domain(normalized_start)
        self.target_domains = {current_domain} if current_domain else set()

        old_queue = self._load_json(self.queue_file)
        if old_queue and len(old_queue) > 0:
            normalized_old = normalize(old_queue[0][0])
            old_domain = get_domain(normalized_old)

            if current_domain != old_domain or not current_domain:
                print("[Кэш] Обнаружен новый домен. Очищаем старые артефакты...")
                self._clear_cache()
                self._init_fresh_start()
            else:
                self.queue = old_queue
                self.page_dates = self._load_json(self.dates_file) or {}
                self.graph = self._load_json(self.graph_file) or {}
                for url, _ in self.queue:
                    self.visited.add(url)
                for url in self.page_dates:
                    self.visited.add(url)
        else:
            self._clear_cache()
            self._init_fresh_start()

    def _init_fresh_start(self):
        for url in self.start_urls:
            norm_url = normalize(url)
            if norm_url:
                self.queue.append([norm_url, 0])
                self.visited.add(norm_url)

    def _clear_cache(self):
        for f in [self.queue_file, self.dates_file, self.graph_file]:
            if os.path.exists(f):
                os.remove(f)
        self.queue = []
        self.page_dates = {}
        self.graph = {}
        self.visited = set()

    def _load_json(self, filename):
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _save_json(self, data, filename):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def _is_match_filters(self, url):
        if self.block_filters:
            if any(re_f in url for re_f in self.block_filters):
                return False
        if self.allow_filters:
            return any(re_f in url for re_f in self.allow_filters)
        return True

    def _can_fetch(self, url):
        return True

    def _worker(self, q, max_d):
        while True:
            try:
                url, depth = q.get(timeout=2)
            except queue.Empty:
                return

            with self.lock:
                if self.counter >= self.max_pages:
                    q.task_done()
                    continue

            if not self._can_fetch(url) or not self._is_match_filters(url):
                q.task_done()
                continue

            last_mod = self.page_dates.get(url)
            response = self.downloader.fetch(url, last_modified=last_mod)

            with self.lock:
                if response.status_code == 200:
                    self.counter += 1
                    print(f"[{self.counter}] {url} (Глубина: {depth}) - OK (200)")
                    if response.last_modified:
                        self.page_dates[url] = response.last_modified
                elif response.status_code == 304:
                    self.counter += 1
                    print(f"[{self.counter}] {url} (Глубина: {depth}) - OK (304 Not Modified)")
                else:
                    err_msg = response.error if response.error else f"HTTP {response.status_code}"
                    print(f"[{self.counter + 1}] {url} (Глубина: {depth}) - ERROR: {err_msg}")
                    q.task_done()
                    continue

            if depth < max_d and response.status_code == 200 and response.html:
                new_links = self.extractor.extract(response.html, response.url, self.target_domains)

                with self.lock:
                    if url not in self.graph:
                        self.graph[url] = []

                    for link in new_links:
                        if link not in self.graph[url]:
                            self.graph[url].append(link)

                        if link not in self.visited:
                            self.visited.add(link)
                            self.queue.append([link, depth + 1])
                            q.put((link, depth + 1))

            q.task_done()

    def run(self, max_workers=5, max_depth=3):
        print(f"\n[Запуск] Домены: {self.target_domains} | Потоков: {max_workers}")

        task_queue = queue.Queue()
        for url, depth in self.queue:
            task_queue.put((url, depth))

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for _ in range(max_workers):
                    executor.submit(self._worker, task_queue, max_depth)
                task_queue.join()
        except KeyboardInterrupt:
            print("\n[Остановка] Процесс прерван пользователем. Сохраняем состояние...")

        with self.lock:
            remaining_queue = []
            while not task_queue.empty():
                remaining_queue.append(task_queue.get())

            for item in self.queue:
                if item not in remaining_queue and item[0] not in self.page_dates:
                    pass

            self._save_json(self.queue, self.queue_file)
            self._save_json(self.page_dates, self.dates_file)
            self._save_json(self.graph, self.graph_file)

        print("[Завершено] База данных структуры сайта обновлена.")
        print("\n=== ФИНАЛЬНЫЙ ОТЧЕТ ФИЛЬТРАЦИИ ===")
        for idx, url in enumerate(self.page_dates, 1):
            print(f"[{idx}] {url} - OK")
        print("\n[Готово] Работа завершена успешно.")