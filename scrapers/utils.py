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
Modul utilitas bersama untuk scraping portal berita.
Menangani pengecekan robots.txt, rate limiting (jeda request),
mekanisme retry otomatis, pembersihan teks berita, penghitungan kata,
dan penyimpanan JSON Lines (.jsonl).
"""

import json
import os
import re
import time
import urllib.parse
import urllib.robotparser
from datetime import datetime, date
from typing import Dict, Optional, Set, Tuple
import requests
from curl_cffi import requests as crequests

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


class RobotsChecker:
    """Mengelola dan memeriksa aturan robots.txt untuk setiap domain."""

    def __init__(self, user_agent: str = "*"):
        self.user_agent = user_agent
        self._parsers: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}

    def _get_parser(self, base_url: str) -> Optional[urllib.robotparser.RobotFileParser]:
        parsed = urllib.parse.urlparse(base_url)
        domain_key = f"{parsed.scheme}://{parsed.netloc}"
        if domain_key in self._parsers:
            return self._parsers[domain_key]

        robots_url = f"{domain_key}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            # Gunakan curl_cffi agar tidak terblokir Cloudflare saat mengambil robots.txt
            resp = crequests.get(
                robots_url,
                impersonate="chrome124",
                headers={"User-Agent": DEFAULT_USER_AGENT},
                timeout=30,
            )
            if resp.status_code == 200 and resp.text:
                rp.parse(resp.text.splitlines())
                self._parsers[domain_key] = rp
            else:
                self._parsers[domain_key] = None
        except Exception:
            self._parsers[domain_key] = None

        return self._parsers[domain_key]

    def can_fetch(self, url: str) -> bool:
        """Memeriksa apakah URL diizinkan oleh robots.txt untuk User-Agent '*'."""
        rp = self._get_parser(url)
        if rp is None:
            return True
        try:
            # Cek terhadap '*' maupun user_agent spesifik
            return rp.can_fetch("*", url) and rp.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def get_crawl_delay(self, url: str, default_delay: float = 1.5) -> float:
        """Mengambil Crawl-delay dari robots.txt jika tersedia, atau gunakan default_delay."""
        rp = self._get_parser(url)
        if rp is not None:
            try:
                delay = rp.crawl_delay("*") or rp.crawl_delay(self.user_agent)
                if delay is not None:
                    return max(float(delay), default_delay)
            except Exception:
                pass
        return default_delay


class PoliteRequester:
    """
    HTTP client yang mematuhi robots.txt dan memberikan jeda antar request (rate limiting).
    Mendukung requests standar maupun curl_cffi (untuk portal dengan proteksi Cloudflare).
    Mendukung mekanisme retry otomatis hingga 5 kali percobaan jika terjadi timeout atau gangguan jaringan.
    """

    def __init__(
        self,
        delay: float = 1.5,
        use_impersonate: bool = False,
        max_retries: int = 5,
        default_timeout: int = 15,
    ):
        self.default_delay = delay
        self.use_impersonate = use_impersonate
        self.max_retries = max_retries
        self.default_timeout = default_timeout
        self.robots = RobotsChecker(user_agent="*")
        self._last_request_time: float = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        self.csession = crequests.Session(impersonate="chrome124")
        self.csession.headers.update(
            {
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

    def _wait_polite(self, url: str):
        delay = self.robots.get_crawl_delay(url, self.default_delay)
        elapsed = time.time() - self._last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        check_robots: bool = True,
        max_retries: Optional[int] = None,
    ):
        """Melakukan HTTP GET dengan pengecekan robots.txt, jeda sopan, dan retry otomatis jika gagal."""
        full_url = url
        if params:
            query_str = urllib.parse.urlencode(params)
            sep = "&" if "?" in url else "?"
            full_url = f"{url}{sep}{query_str}"

        if check_robots and not self.robots.can_fetch(full_url):
            print(f"  [robots.txt] Dilarang mengakses URL: {full_url}")
            return None

        actual_timeout = timeout if timeout is not None else self.default_timeout
        retries_limit = max_retries if max_retries is not None else self.max_retries

        for attempt in range(1, retries_limit + 1):
            self._wait_polite(full_url)
            self._last_request_time = time.time()

            try:
                if self.use_impersonate:
                    resp = self.csession.get(url, headers=headers, params=params, timeout=actual_timeout)
                else:
                    resp = self.session.get(url, headers=headers, params=params, timeout=actual_timeout)

                # Cek apakah server mengembalikan rate limit (429) atau server error sementara (500, 502, 503, 504)
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < retries_limit:
                        backoff = 2 * attempt
                        print(f"  [HTTP {resp.status_code}] Percobaan {attempt}/{retries_limit} gagal untuk {full_url}. Menunggu {backoff} detik...")
                        time.sleep(backoff)
                        continue
                return resp
            except Exception as e:
                if attempt < retries_limit:
                    backoff = 2 * attempt
                    print(f"  [Retry {attempt}/{retries_limit}] Gagal mengakses {full_url} ({e}). Mencoba lagi dalam {backoff} detik...")
                    time.sleep(backoff)
                else:
                    print(f"  [Error Request] Gagal mengakses {full_url} setelah {retries_limit} percobaan: {e}")
                    return None

        return None


def clean_article_text(text: str) -> str:
    """Membersihkan teks berita dari spasi berlebih dan karakter tak perlu."""
    if not text:
        return ""
    # Hilangkan baris "Baca juga:" yang sering terselip di tengah paragraf
    lines = []
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        if re.match(r"^(baca juga|lihat juga|simak juga|pilihan editor|berita terkait)\s*:?", line_clean, re.I):
            continue
        lines.append(line_clean)
    cleaned = "\n\n".join(lines)
    # Normalisasi spasi horizontal berlebih
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def count_words(text: str) -> int:
    """Menghitung jumlah kata dari teks isi berita."""
    if not text:
        return 0
    words = re.findall(r"\b\w+\b", text)
    return len(words)


def build_article_record(
    portal: str,
    title: str,
    published_date: str,
    content: str,
    url: str,
) -> Dict[str, object]:
    """
    Membentuk dictionary data berita sesuai spesifikasi output JSONL:
    - nama_portal_berita
    - judul
    - tanggal_terbit
    - isi_berita
    - jumlah_kata
    - url
    """
    cleaned_content = clean_article_text(content)
    word_count = count_words(cleaned_content)
    return {
        "nama_portal_berita": portal,
        "judul": title.strip() if title else "",
        "tanggal_terbit": published_date.strip() if published_date else "",
        "isi_berita": cleaned_content,
        "jumlah_kata": word_count,
        "url": url.strip() if url else "",
    }


def load_existing_urls(filepath: str) -> Set[str]:
    """Membaca URL yang sudah pernah disimpan di file JSONL agar tidak duplikat."""
    urls: Set[str] = set()
    if not os.path.exists(filepath):
        return urls
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "url" in data and data["url"]:
                        urls.add(data["url"])
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return urls


def append_to_jsonl(filepath: str, record: Dict[str, object]) -> None:
    """Menyimpan satu baris data berita ke dalam file JSON Lines (.jsonl)."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


INDONESIAN_MONTHS = {
    "januari": 1, "jan": 1,
    "februari": 2, "feb": 2,
    "maret": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "agustus": 8, "agu": 8, "agt": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11,
    "desember": 12, "des": 12, "dec": 12,
}


def parse_indonesian_date(date_str: str) -> Optional[Tuple[date, str]]:
    """
    Mengubah berbagai format string tanggal Indonesia/ISO menjadi (datetime.date, formatted_string).
    Contoh format yang didukung:
    - '2026-11-08T20:01:00+07:00' atau '2026-11-08 20:01:00'
    - '2026/11/08 23:02:37'
    - 'Minggu, 08 Nov 2026 09:41 WIB'
    - 'Terbit 8 Nov 2026 20:01 WIB'
    - 'Kompas.com, 8 November 2026, 23:16 WIB'
    """
    if not date_str:
        return None
    s = date_str.strip()

    # 1. Coba format ISO YYYY-MM-DD atau YYYY/MM/DD
    m_iso = re.search(
        r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[T\s]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        s,
    )
    if m_iso:
        yr, mo, dy = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        hh = int(m_iso.group(4)) if m_iso.group(4) else 0
        mm = int(m_iso.group(5)) if m_iso.group(5) else 0
        ss = int(m_iso.group(6)) if m_iso.group(6) else 0
        try:
            d = date(yr, mo, dy)
            fmt = f"{yr:04d}-{mo:02d}-{dy:02d} {hh:02d}:{mm:02d}:{ss:02d}"
            return d, fmt
        except ValueError:
            pass

    # 2. Coba format tanggal Indonesia: DD <NamaBulan> YYYY [HH:MM]
    m_id = re.search(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})(?:[\s,]+(\d{1,2})[:.](\d{2}))?",
        s,
    )
    if m_id:
        dy = int(m_id.group(1))
        mo_name = m_id.group(2).lower()
        yr = int(m_id.group(3))
        hh = int(m_id.group(4)) if m_id.group(4) else 0
        mm = int(m_id.group(5)) if m_id.group(5) else 0
        mo = INDONESIAN_MONTHS.get(mo_name)
        if mo:
            try:
                d = date(yr, mo, dy)
                fmt = f"{yr:04d}-{mo:02d}-{dy:02d} {hh:02d}:{mm:02d}:00"
                return d, fmt
            except ValueError:
                pass

    return None
