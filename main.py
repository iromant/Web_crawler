import sys
import argparse
from crawler import Crawler

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Многопоточный веб-краулер для построения графа связей сайта.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('urls', nargs='?', default=None)
    parser.add_argument('-d', '--max-depth', type=int, default=3)
    parser.add_argument('-p', '--max-pages', type=int, default=50)
    parser.add_argument('-w', '--workers', type=int, default=5)
    parser.add_argument('--allow', type=str, default="")
    parser.add_argument('--block', type=str, default="")
    return parser.parse_args()

def interactive_input():
    print("=== Веб-краулер ===")
    urls_raw = input("Введите стартовые URL через запятую: ").strip()
    if not urls_raw:
        print("[!] Ошибка: Не указаны стартовые URL.")
        sys.exit(1)

    try:
        max_depth = int(input("Введите макс. глубину [3]: ") or 3)
        max_pages = int(input("Введите лимит страниц [50]: ") or 50)
        workers = int(input("Введите количество потоков [5]: ") or 5)
    except ValueError:
        print("[!] Ошибка: Параметры глубины, лимита страниц и потоков должны быть числами.")
        sys.exit(1)

    allow_raw = input("Искать только ссылки с (через запятую): ").strip()
    block_raw = input("Игнорировать ссылки с (через запятую): ").strip()

    return {
        "urls": [u.strip() for u in urls_raw.split(",") if u.strip()],
        "max_depth": max_depth,
        "max_pages": max_pages,
        "workers": workers,
        "allow": [a.strip() for a in allow_raw.split(",") if a.strip()],
        "block": [b.strip() for b in block_raw.split(",") if b.strip()]
    }

def main():
    args = parse_arguments()

    if args.urls:
        start_urls = [u.strip() for u in args.urls.split(",") if u.strip()]
        allow_filters = [a.strip() for a in args.allow.split(",") if a.strip()]
        block_filters = [b.strip() for b in args.block.split(",") if b.strip()]
        config = {
            "urls": start_urls,
            "max_depth": args.max_depth,
            "max_pages": args.max_pages,
            "workers": args.workers,
            "allow": allow_filters,
            "block": block_filters
        }
    else:
        config = interactive_input()

    try:
        crawler = Crawler(
            start_urls=config["urls"],
            max_pages=config["max_pages"],
            allow_filters=config["allow"],
            block_filters=config["block"]
        )

        crawler.run(max_workers=config["workers"], max_depth=config["max_depth"])
    except Exception as e:
        print(f"\n[Критическая ошибка]: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()