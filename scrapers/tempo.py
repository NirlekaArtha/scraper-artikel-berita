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
Modul scraper khusus untuk portal berita Tempo.co (versi non-Plus / Gratis).
Output disimpan secara terpisah ke dalam file JSONL tersendiri (output/tempo.jsonl).
Mematuhi robots.txt dan memberikan jeda antar request.
"""

import email.utils
import hashlib
import re
import time
from datetime import date, timedelta
from typing import Dict, Optional, Tuple
from bs4 import BeautifulSoup

from .utils import (
    PoliteRequester,
    append_to_jsonl,
    build_article_record,
    load_existing_urls,
    parse_indonesian_date,
)

PORTAL_NAME = "tempo.co"
DEFAULT_OUTPUT_FILE = "output/tempo.jsonl"

DEFAULT_BASE_API_KEY = "81463481-162f-4225-bca9-458e32ff0732"


def _extract_html_text(raw_html: str) -> str:
    """Membersihkan tag HTML dari konten berita Tempo.co menjadi teks bersih."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "lxml")
    for bad in soup.select("script, style, .baca-juga, blockquote"):
        bad.decompose()

    paragraphs = []
    for p in soup.find_all("p"):
        txt = p.get_text(" ", strip=True)
        if not txt:
            continue
        if re.match(r"^(baca juga|pilihan editor|simak juga)\s*:?", txt, re.I):
            continue
        paragraphs.append(txt)

    if paragraphs:
        return "\n\n".join(paragraphs)
    return soup.get_text("\n\n", strip=True)


def _init_tempo_session(requester: PoliteRequester) -> Tuple[str, int]:
    """
    Mengambil halaman /indeks Tempo.co untuk menyamakan waktu server (mencegah selisih jam lokal)
    dan mengambil baseApiKey terbaru jika berubah.
    """
    base_key = DEFAULT_BASE_API_KEY
    time_offset = 0

    resp = requester.get("https://www.tempo.co/indeks")
    if resp and resp.status_code == 200:
        m_key = re.search(r'baseApiKey\s*:\s*"([^"]+)"', resp.text)
        if m_key:
            base_key = m_key.group(1)

        date_hdr = resp.headers.get("Date")
        if date_hdr:
            try:
                server_ts = int(email.utils.parsedate_to_datetime(date_hdr).timestamp())
                time_offset = server_ts - int(time.time())
            except Exception:
                pass

    return base_key, time_offset


def _build_tempo_headers(base_key: str, time_offset: int) -> Dict[str, str]:
    """Membentuk header autentikasi publik untuk endpoint /api/gateway Tempo.co."""
    req_ts = int(time.time()) + time_offset
    token = hashlib.sha256(f"{base_key}{req_ts}".encode("utf-8")).hexdigest()
    return {
        "X-Platform-Application": "desktop",
        "X-Tempo-Token": token,
        "X-Request-Time": str(req_ts),
        "Referer": "https://www.tempo.co/indeks",
    }


def _parse_tempo_html_fallback(html: str, url: str) -> Optional[dict]:
    """Fallback parser langsung dari HTML halaman artikel Tempo.co."""
    soup = BeautifulSoup(html, "lxml")
    # Pastikan bukan artikel Tempo Plus (berbayar)
    if soup.find(string=re.compile(r"Berlangganan Tempo\+|Artikel ini khusus pelanggan", re.I)):
        return None

    title_el = soup.find("h1") or soup.find("meta", property="og:title")
    if not title_el:
        return None
    title = (
        title_el.get("content", "")
        if title_el.name == "meta"
        else title_el.get_text(" ", strip=True)
    )

    pub_date_str = ""
    meta_pub = soup.find("meta", property="article:published_time")
    if meta_pub and meta_pub.get("content"):
        parsed = parse_indonesian_date(meta_pub["content"])
        if parsed:
            pub_date_str = parsed[1]

    paragraphs = []
    for p in soup.select("article p"):
        txt = p.get_text(" ", strip=True)
        if not txt or re.match(r"^(baca juga|pilihan editor)\s*:?", txt, re.I):
            continue
        paragraphs.append(txt)

    content_text = "\n\n".join(paragraphs)
    if not content_text.strip():
        return None

    return build_article_record(
        portal=PORTAL_NAME,
        title=title,
        published_date=pub_date_str,
        content=content_text,
        url=url,
    )


def scrape_tempo(
    max_articles: int,
    start_date: date,
    end_date: date,
    output_file: str = DEFAULT_OUTPUT_FILE,
    delay: float = 1.5,
) -> int:
    """
    Menjalankan scraping berita Tempo.co (khusus versi non-Plus / access=FREE)
    pada rentang tanggal [start_date, end_date].
    Menyimpan hasil ke output_file dalam format JSON Lines (.jsonl).
    Mengembalikan jumlah artikel yang berhasil diambil.
    """
    # Gunakan curl_cffi impersonate agar dapat melewati Cloudflare Tempo.co
    requester = PoliteRequester(delay=delay, use_impersonate=True)
    seen_urls = load_existing_urls(output_file)
    collected = 0

    print(f"\n[{PORTAL_NAME}] Memulai scraping versi Non-Plus/FREE (target: {max_articles} berita, rentang: {start_date} s/d {end_date})")
    print(f"[{PORTAL_NAME}] File output: {output_file}")

    base_key, time_offset = _init_tempo_session(requester)

    start_str = start_date.strftime("%Y-%m-%d")
    # Tambahkan 1 hari pada end_date parameter API agar mencakup hingga pukul 23:59:59 di end_date
    end_plus_one_str = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")

    page = 1
    page_size = 20

    while collected < max_articles:
        params = {
            "status": "published",
            "access": "FREE",  # Hanya mengambil versi Non-Plus (gratis)
            "order_published_at": "DESC",
            "page_size": str(page_size),
            "page": str(page),
            "start_date": start_str,
            "end_date": end_plus_one_str,
        }
        headers = _build_tempo_headers(base_key, time_offset)
        resp = requester.get(
            "https://www.tempo.co/api/gateway/articles",
            headers=headers,
            params=params,
        )
        if not resp or resp.status_code != 200:
            break

        try:
            payload = resp.json()
        except Exception:
            break

        articles_data = payload.get("data") or []
        if not articles_data:
            break

        for item in articles_data:
            if collected >= max_articles:
                break

            # Pastikan access adalah FREE (bukan VIP / Tempo Plus)
            access_type = str(item.get("access", "")).upper()
            if access_type and access_type != "FREE":
                continue

            canonical = (item.get("canonical_url") or "").lstrip("/")
            if not canonical:
                continue
            art_url = (
                canonical
                if canonical.startswith("http")
                else f"https://www.tempo.co/{canonical}"
            )
            # Lewati foto/video jika bukan artikel berita teks
            if "/foto/" in art_url or "/video/" in art_url:
                continue
            if art_url in seen_urls:
                continue

            # Periksa tanggal terbit terhadap rentang [start_date, end_date]
            raw_pub = item.get("published_at") or ""
            parsed_pub = parse_indonesian_date(raw_pub)
            if parsed_pub:
                pub_d, pub_str = parsed_pub
                if pub_d < start_date or pub_d > end_date:
                    continue
            else:
                pub_str = raw_pub

            title = item.get("title_digital") or item.get("title_seo") or ""
            raw_content = item.get("content") or ""

            # Jika content di daftar artikel belum lengkap, ambil dari endpoint detail
            if not raw_content or len(raw_content) < 100:
                art_id = item.get("id")
                if art_id:
                    detail_headers = _build_tempo_headers(base_key, time_offset)
                    detail_resp = requester.get(
                        f"https://www.tempo.co/api/gateway/articles/{art_id}/detail",
                        headers=detail_headers,
                    )
                    if detail_resp and detail_resp.status_code == 200:
                        try:
                            detail_data = detail_resp.json().get("data") or {}
                            raw_content = detail_data.get("content") or raw_content
                            title = detail_data.get("title_digital") or title
                        except Exception:
                            pass

            content_text = _extract_html_text(raw_content)

            # Jika masih kosong, fallback ke scraping halaman HTML artikel langsung
            if not content_text.strip():
                html_resp = requester.get(art_url)
                if html_resp and html_resp.status_code == 200:
                    record = _parse_tempo_html_fallback(html_resp.text, art_url)
                else:
                    record = None
            else:
                record = build_article_record(
                    portal=PORTAL_NAME,
                    title=title,
                    published_date=pub_str,
                    content=content_text,
                    url=art_url,
                )

            if record and record["jumlah_kata"] > 20:
                append_to_jsonl(output_file, record)
                seen_urls.add(art_url)
                collected += 1
                print(
                    f"  [{PORTAL_NAME}] ({collected}/{max_articles}) "
                    f"{record['tanggal_terbit']} | {record['judul'][:60]}... ({record['jumlah_kata']} kata)"
                )

        if len(articles_data) < page_size:
            break
        page += 1

    print(f"[{PORTAL_NAME}] Selesai. Total berita baru tersimpan: {collected} -> {output_file}")
    return collected
