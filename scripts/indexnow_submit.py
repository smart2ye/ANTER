#!/usr/bin/env python3
"""يرسل URLs جديدة إلى IndexNow (Bing + Yandex + Seznam + Naver).

الاستخدام:
    python3 scripts/indexnow_submit.py https://anter-1.onrender.com/p/xxx
    python3 scripts/indexnow_submit.py --sitemap  # كل الروابط من sitemap

يُستدعى يدويًا أو من GitHub Action بعد كل نشر.
"""
import argparse
import json
import sys
import urllib.request
import urllib.error

INDEXNOW_KEY = "d5a1393ec6a04f07aaacd9561975b833"
HOST = "anter-1.onrender.com"
KEY_LOCATION = f"https://{HOST}/{INDEXNOW_KEY}.txt"
ENDPOINT = "https://api.indexnow.org/indexnow"


def submit(urls):
    if not urls:
        print("لا URLs لإرسالها.")
        return
    payload = {
        "host": HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls[:10000],  # حد IndexNow = 10,000
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"HTTP {resp.status} — أُرسل {len(urls)} رابط.")
    except urllib.error.HTTPError as e:
        print(f"خطأ HTTP {e.code}: {e.read()[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"فشل: {type(e).__name__}: {e}")
        sys.exit(1)


def urls_from_sitemap():
    """يجلب كل روابط sitemap.xml."""
    sitemap_url = f"https://{HOST}/sitemap.xml"
    try:
        with urllib.request.urlopen(sitemap_url, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"فشل تحميل sitemap: {e}")
        return []
    import re
    return re.findall(r"<loc>([^<]+)</loc>", content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs="*", help="روابط لإرسالها")
    parser.add_argument("--sitemap", action="store_true",
                        help="أرسل كل روابط sitemap")
    args = parser.parse_args()

    if args.sitemap:
        urls = urls_from_sitemap()
        print(f"عدد الروابط من sitemap: {len(urls)}")
    else:
        urls = args.urls

    if not urls:
        parser.print_help()
        sys.exit(1)

    submit(urls)


if __name__ == "__main__":
    main()
