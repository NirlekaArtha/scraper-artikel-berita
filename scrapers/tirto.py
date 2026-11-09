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
Modul scraper khusus untuk portal berita Tirto.id.
Output disimpan secara terpisah ke dalam file JSONL tersendiri (output/tirto.jsonl).
Mematuhi robots.txt dan memberikan jeda antar request.
"""

import re
from datetime import date, datetime, timedelta
from typing import Optional, Tuple
from bs4 import BeautifulSoup

from .utils import (
    PoliteRequester,
    append_to_jsonl,
    build_article_record,
    load_existing_urls,
    parse_indonesian_date,
)

PORTAL_NAME = "tirto.id"
DEFAULT_OUTPUT_FILE = "output/tirto.jsonl"


def _parse_card_approx_date(ts_text: str, img_src: str = "") -> Optional[date]:
    """
    Memperkirakan tanggal terbit artikel dari teks kartu indeks Tirto.id
    (misal '3 jam lalu', 'Kamis, 5 Nov', 'Selasa, 23 Des 2025') atau path gambar YYYY/MM/DD.
    Digunakan untuk mengoptimalkan pencarian halaman pada rentang tanggal.
    """
    today = date.today()
    s = (ts_text or "").strip().lower()

    if "menit" in s or "jam" in s or "detik" in s or "baru saja" in s:
        return today
    if "kemarin" in s:
        return today - timedelta(days=1)
    m_hari = re.search(r"(\d+)\s+hari\s+lalu", s)
    if m_hari:
        return today - timedelta(days=int(m_hari.group(1)))

    # Jika ada tahun lengkap: "Selasa, 23 Des 2025"
    parsed = parse_indonesian_date(s)
    if parsed:
        return parsed[0]

    # Jika hanya tanggal dan bulan tanpa tahun: "Kamis, 5 Nov"
    m_no_yr = re.search(r"(\d{1,2})\s+([a-zA-Z]+)", s)
    if m_no_yr:
        parsed_with_yr = parse_indonesian_date(f"{m_no_yr.group(1)} {m_no_yr.group(2)} {today.year}")
        if parsed_with_yr:
            d = parsed_with_yr[0]
            if d > today + timedelta(days=2):
                d = date(today.year - 1, d.month, d.day)
            return d

    # Fallback dari URL thumbnail gambar jika tidak ada tahun
    m_img = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", img_src or "")
    if m_img:
        try:
            return date(int(m_img.group(1)), int(m_img.group(2)), int(m_img.group(3)))
        except ValueError:
            pass

    return None


def _parse_tirto_article(html: str, url: str) -> Tuple[Optional[dict], Optional[date]]:
    """
    Mengekstrak judul, tanggal terbit, dan isi berita dari halaman artikel Tirto.id.
    Mengembalikan tuple (record_dict, pub_date_obj).
    """
    soup = BeautifulSoup(html, "lxml")

    # 1. Judul
    title_el = (
        soup.find("h1", class_="article-title")
        or soup.find("h1")
        or soup.find("meta", property="og:title")
    )
    if not title_el:
        return None, None
    title = (
        title_el.get("content", "")
        if title_el.name == "meta"
        else title_el.get_text(" ", strip=True)
    )

    # 2. Tanggal terbit
    pub_date_obj: Optional[date] = None
    pub_date_str = ""

    # Cari teks "Terbit DD Mon YYYY HH:MM WIB" di dalam .byline atau .article-meta
    meta_div = soup.find("div", class_="article-meta") or soup.find("header", class_="article-header")
    if meta_div:
        meta_text = meta_div.get_text(" ", strip=True)
        m_terbit = re.search(r"Terbit\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4}(?:\s+\d{1,2}:\d{2})?)", meta_text, re.I)
        if m_terbit:
            parsed = parse_indonesian_date(m_terbit.group(1))
            if parsed:
                pub_date_obj, pub_date_str = parsed

    # Fallback ke meta article:published_time atau article:modified_time
    if not pub_date_obj:
        for prop in ("article:published_time", "article:modified_time", "datePublished"):
            m_tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if m_tag and m_tag.get("content"):
                parsed = parse_indonesian_date(m_tag["content"])
                if parsed:
                    pub_date_obj, pub_date_str = parsed
                    break

    # 3. Isi berita
    # Tirto menggunakan satu atau beberapa div.content-text-editor di dalam <article>
    article_tag = soup.find("article") or soup
    editors = article_tag.find_all("div", class_="content-text-editor")

    paragraphs = []
    for ed in editors:
        for bad in ed.select("script, style, .baca-juga, blockquote"):
            bad.decompose()
        for p in ed.find_all("p"):
            txt = p.get_text(" ", strip=True)
            if not txt:
                continue
            if re.match(
                r"^(baca juga|baca juga artikel terkait|reporter:|penulis:|editor:|tirto\.id\s*-\s*flash news)",
                txt,
                re.I,
            ):
                continue
            paragraphs.append(txt)

    content_text = "\n\n".join(paragraphs)
    # Bersihkan prefix "tirto.id - " di awal artikel jika ada
    content_text = re.sub(r"^tirto\.id\s*[-–—]\s*", "", content_text, flags=re.I)

    if not content_text.strip():
        return None, pub_date_obj

    record = build_article_record(
        portal=PORTAL_NAME,
        title=title,
        published_date=pub_date_str,
        content=content_text,
        url=url,
    )
    return record, pub_date_obj


def _find_starting_page(requester: PoliteRequester, target_end_date: date) -> int:
    """
    Mencari halaman awal di indeks Tirto.id (/q/latest-news-D5ie?page=N)
    yang mendekati target_end_date jika pengguna meminta tanggal masa lalu,
    sehingga tidak perlu menelusuri halaman satu per satu dari hari ini.
    """
    today = date.today()
    if target_end_date >= today - timedelta(days=2):
        return 1

    # Estimasi kasar: ~30 artikel per halaman, sekitar 3-5 halaman per hari
    low = 1
    high = min(2500, max(20, (today - target_end_date).days * 5))

    best_page = 1
    for _ in range(7):
        if low > high:
            break
        mid = (low + high) // 2
        url = f"https://tirto.id/q/latest-news-D5ie?page={mid}"
        resp = requester.get(url)
        if not resp or resp.status_code != 200:
            high = mid - 1
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.find_all("div", class_="list-card")
        if not cards:
            high = mid - 1
            continue
        ts_el = cards[0].find(class_="list-card-timestamp")
        img_el = cards[0].find("img")
        card_date = _parse_card_approx_date(
            ts_el.get_text(strip=True) if ts_el else "",
            img_el.get("src", "") if img_el else "",
        )
        if not card_date:
            break
        if card_date > target_end_date:
            best_page = mid
            low = mid + 1
        else:
            high = mid - 1

    return max(1, best_page)


def scrape_tirto(
    max_articles: int,
    start_date: date,
    end_date: date,
    output_file: str = DEFAULT_OUTPUT_FILE,
    delay: float = 1.5,
) -> int:
    """
    Menjalankan scraping berita Tirto.id pada rentang tanggal [start_date, end_date].
    Menyimpan hasil ke output_file dalam format JSON Lines (.jsonl).
    Mengembalikan jumlah artikel yang berhasil diambil.
    """
    # Gunakan impersonate agar tidak direset oleh Cloudflare Tirto.id
    requester = PoliteRequester(delay=delay, use_impersonate=True)
    seen_urls = load_existing_urls(output_file)
    collected = 0

    print(f"\n[{PORTAL_NAME}] Memulai scraping (target: {max_articles} berita, rentang: {start_date} s/d {end_date})")
    print(f"[{PORTAL_NAME}] File output: {output_file}")

    page = _find_starting_page(requester, end_date)
    consecutive_older_articles = 0

    while collected < max_articles:
        index_url = f"https://tirto.id/q/latest-news-D5ie?page={page}"
        resp = requester.get(index_url)
        if not resp or resp.status_code != 200:
            break

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.find_all("div", class_="list-card")
        if not cards:
            break

        for card in cards:
            if collected >= max_articles:
                break

            a_tag = card.find("a", class_="ulink") or card.find("a", href=True)
            if not a_tag or not a_tag.get("href"):
                continue

            art_url = a_tag["href"].split("?")[0].strip()
            if not art_url.startswith("https://tirto.id/"):
                continue
            if art_url in seen_urls:
                continue

            # Cek perkiraan tanggal dari kartu indeks sebelum request artikel penuh
            ts_el = card.find(class_="list-card-timestamp")
            img_el = card.find("img")
            approx_date = _parse_card_approx_date(
                ts_el.get_text(strip=True) if ts_el else "",
                img_el.get("src", "") if img_el else "",
            )
            if approx_date:
                if approx_date > end_date + timedelta(days=1):
                    continue
                if approx_date < start_date - timedelta(days=1):
                    consecutive_older_articles += 1
                    if consecutive_older_articles >= 15:
                        break
                    continue

            art_resp = requester.get(art_url)
            if not art_resp or art_resp.status_code != 200:
                continue

            record, pub_date_obj = _parse_tirto_article(art_resp.text, art_url)
            if not record or record["jumlah_kata"] <= 20:
                continue

            if pub_date_obj:
                if pub_date_obj > end_date:
                    continue
                if pub_date_obj < start_date:
                    consecutive_older_articles += 1
                    if consecutive_older_articles >= 15:
                        break
                    continue
                consecutive_older_articles = 0

            append_to_jsonl(output_file, record)
            seen_urls.add(art_url)
            collected += 1
            print(
                f"  [{PORTAL_NAME}] ({collected}/{max_articles}) "
                f"{record['tanggal_terbit']} | {record['judul'][:60]}... ({record['jumlah_kata']} kata)"
            )

        if consecutive_older_articles >= 15:
            break
        page += 1

    print(f"[{PORTAL_NAME}] Selesai. Total berita baru tersimpan: {collected} -> {output_file}")
    return collected
