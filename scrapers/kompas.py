"""
Script Scraping Data Berita 5 Portal Indonesia
(Tirto.id, Kompas.com, Detik.com, CNN Indonesia, Tempo.co Non-Plus)

Copyright (C) 2026 Nirleka <nirlekaarthamevira@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Deskripsi:
Modul scraper khusus untuk portal berita Kompas.com.
Output disimpan secara terpisah ke dalam file JSONL tersendiri (output/kompas.jsonl).
Mematuhi robots.txt dan memberikan jeda antar request.
"""

from datetime import date, timedelta
from typing import Optional
from bs4 import BeautifulSoup

from .utils import (
    PoliteRequester,
    append_to_jsonl,
    build_article_record,
    load_existing_urls,
    parse_indonesian_date,
)

PORTAL_NAME = "kompas.com"
DEFAULT_OUTPUT_FILE = "output/kompas.jsonl"


def _parse_kompas_article(html: str, url: str) -> Optional[dict]:
    """Mengekstrak judul, tanggal terbit, dan isi berita dari halaman artikel Kompas.com."""
    soup = BeautifulSoup(html, "lxml")

    # 1. Judul
    title_el = (
        soup.find("h1", class_="read__title")
        or soup.find("h1")
        or soup.find("meta", property="og:title")
    )
    if not title_el:
        return None
    title = (
        title_el.get("content", "")
        if title_el.name == "meta"
        else title_el.get_text(" ", strip=True)
    )

    # 2. Tanggal terbit
    pub_date_str = ""
    meta_pub = (
        soup.find("meta", property="article:published_time")
        or soup.find("meta", attrs={"name": "content_PublishedDate"})
    )
    if meta_pub and meta_pub.get("content"):
        parsed = parse_indonesian_date(meta_pub["content"])
        if parsed:
            pub_date_str = parsed[1]

    if not pub_date_str:
        read_time = soup.find("div", class_="read__time")
        if read_time:
            raw_time = read_time.get_text(" ", strip=True)
            parsed = parse_indonesian_date(raw_time)
            pub_date_str = parsed[1] if parsed else raw_time

    # 3. Isi berita
    content_div = soup.find("div", class_="read__content") or soup.find("div", class_="article__content")
    if not content_div:
        return None

    # Hapus elemen non-berita di dalam konten
    for bad in content_div.select(
        "script, style, .inner-link-baca-juga, .ads-on-body, .kompasidRec, blockquote, .read__bacajuga"
    ):
        bad.decompose()

    paragraphs = []
    for p in content_div.find_all("p"):
        txt = p.get_text(" ", strip=True)
        if not txt:
            continue
        if txt.lower().startswith(("baca juga:", "simak juga:", "dapatkan update")):
            continue
        paragraphs.append(txt)

    content_text = "\n\n".join(paragraphs) if paragraphs else content_div.get_text("\n\n", strip=True)
    if not content_text.strip():
        return None

    return build_article_record(
        portal=PORTAL_NAME,
        title=title,
        published_date=pub_date_str,
        content=content_text,
        url=url,
    )


def scrape_kompas(
    max_articles: int,
    start_date: date,
    end_date: date,
    output_file: str = DEFAULT_OUTPUT_FILE,
    delay: float = 1.5,
) -> int:
    """
    Menjalankan scraping berita Kompas.com pada rentang tanggal [start_date, end_date].
    Menyimpan hasil ke output_file dalam format JSON Lines (.jsonl).
    Mengembalikan jumlah artikel yang berhasil diambil.
    """
    requester = PoliteRequester(delay=delay)
    seen_urls = load_existing_urls(output_file)
    collected = 0

    print(f"\n[{PORTAL_NAME}] Memulai scraping (target: {max_articles} berita, rentang: {start_date} s/d {end_date})")
    print(f"[{PORTAL_NAME}] File output: {output_file}")

    current_date = end_date
    while current_date >= start_date and collected < max_articles:
        date_str = current_date.strftime("%Y-%m-%d")
        page = 1

        while collected < max_articles:
            index_url = f"https://indeks.kompas.com/?site=all&date={date_str}&page={page}"
            resp = requester.get(index_url)
            if not resp or resp.status_code != 200:
                break

            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select(".articleItem, .article__list")
            if not items:
                break

            new_links_on_page = 0
            for item in items:
                if collected >= max_articles:
                    break
                a_tag = item.find("a", class_="article-link") or item.find("a", href=True)
                if not a_tag or not a_tag.get("href"):
                    continue

                art_url = a_tag["href"].split("?")[0].strip()
                # Pastikan bukan halaman video/komentar yang dilarang
                if "/komentar/" in art_url or "/copy/" in art_url:
                    continue
                if art_url in seen_urls:
                    continue

                new_links_on_page += 1
                # Gunakan ?page=all agar seluruh halaman artikel termuat sekaligus (diizinkan robots.txt)
                fetch_url = f"{art_url}?page=all"
                art_resp = requester.get(fetch_url)
                if not art_resp or art_resp.status_code != 200:
                    continue

                record = _parse_kompas_article(art_resp.text, art_url)
                if record and record["jumlah_kata"] > 20:
                    append_to_jsonl(output_file, record)
                    seen_urls.add(art_url)
                    collected += 1
                    print(
                        f"  [{PORTAL_NAME}] ({collected}/{max_articles}) "
                        f"{record['tanggal_terbit']} | {record['judul'][:60]}... ({record['jumlah_kata']} kata)"
                    )

            if new_links_on_page == 0:
                break
            page += 1

        current_date -= timedelta(days=1)

    print(f"[{PORTAL_NAME}] Selesai. Total berita baru tersimpan: {collected} -> {output_file}")
    return collected
