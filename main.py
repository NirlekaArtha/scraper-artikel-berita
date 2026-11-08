#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
Script utama (main.py) untuk menjalankan scraping berita dari 5 portal berita:
1. tirto.id       -> output/tirto.jsonl
2. kompas.com     -> output/kompas.jsonl
3. detik.com      -> output/detik.jsonl
4. cnnindonesia   -> output/cnn.jsonl
5. tempo.co       -> output/tempo.jsonl (khusus versi Non-Plus / Gratis)

Setiap modul portal berita disimpan terpisah di dalam folder `scrapers/`
dan memiliki file output JSON Lines (.jsonl) masing-masing agar tidak bercampur.
"""

__author__ = "Nirleka"
__copyright__ = "Copyright (C) 2026 Nirleka"
__license__ = "GPL-3.0-or-later"
__version__ = "1.0.0"

import argparse
import os
import sys
from datetime import date, datetime
from typing import List, Tuple

from scrapers.tirto import scrape_tirto
from scrapers.kompas import scrape_kompas
from scrapers.detik import scrape_detik
from scrapers.cnn import scrape_cnn
from scrapers.tempo import scrape_tempo

PORTALS_CONFIG = {
    "1": {
        "key": "tirto",
        "name": "tirto.id",
        "func": scrape_tirto,
        "output": "output/tirto.jsonl",
    },
    "2": {
        "key": "kompas",
        "name": "kompas.com",
        "func": scrape_kompas,
        "output": "output/kompas.jsonl",
    },
    "3": {
        "key": "detik",
        "name": "detik.com",
        "func": scrape_detik,
        "output": "output/detik.jsonl",
    },
    "4": {
        "key": "cnn",
        "name": "cnnindonesia.com",
        "func": scrape_cnn,
        "output": "output/cnn.jsonl",
    },
    "5": {
        "key": "tempo",
        "name": "tempo.co (Non-Plus)",
        "func": scrape_tempo,
        "output": "output/tempo.jsonl",
    },
}


def parse_date_input(date_str: str) -> date:
    """Mengubah string input tanggal (YYYY-MM-DD atau DD-MM-YYYY) menjadi objek datetime.date."""
    s = date_str.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        f"Format tanggal '{date_str}' tidak dikenali. Gunakan format YYYY-MM-DD (contoh: 2026-11-01)."
    )


def prompt_portal_selection() -> List[dict]:
    """Meminta input dari pengguna mengenai portal berita mana saja yang ingin di-scrape."""
    print("=" * 65)
    print("         PROGRAM SCRAPING DATA BERITA 5 PORTAL INDONESIA         ")
    print("=" * 65)
    print("Daftar Portal Berita Tersedia:")
    for num, info in PORTALS_CONFIG.items():
        print(f"  [{num}] {info['name']:<22} -> {info['output']}")
    print("  [semua / all] Scrape kelima portal berita sekaligus")
    print("-" * 65)

    while True:
        raw = input(
            "Masukkan pilihan portal (misal: 'semua', '1,2,5', atau 'tirto,kompas'): "
        ).strip().lower()
        if not raw:
            print("  [!] Pilihan tidak boleh kosong.")
            continue

        if raw in ("semua", "all", "0", "*"):
            return list(PORTALS_CONFIG.values())

        tokens = [t.strip() for t in raw.replace(" ", ",").split(",") if t.strip()]
        selected = []
        seen_keys = set()

        for tok in tokens:
            if tok in PORTALS_CONFIG:
                cfg = PORTALS_CONFIG[tok]
                if cfg["key"] not in seen_keys:
                    selected.append(cfg)
                    seen_keys.add(cfg["key"])
            else:
                # Cek pencocokan berdasarkan nama atau key portal
                matched = False
                for cfg in PORTALS_CONFIG.values():
                    if tok in cfg["key"] or tok in cfg["name"].lower():
                        if cfg["key"] not in seen_keys:
                            selected.append(cfg)
                            seen_keys.add(cfg["key"])
                        matched = True
                        break
                if not matched:
                    print(f"  [!] Portal '{tok}' tidak dikenali.")
                    selected = []
                    break

        if selected:
            return selected
        print("  [!] Silakan masukkan nomor (1-5), nama portal, atau ketik 'semua'.")


def prompt_max_articles() -> int:
    """Meminta input jumlah berita per portal yang ingin di-scrape."""
    while True:
        raw = input("Masukkan jumlah berita per portal yang ingin di-scrape (contoh: 10): ").strip()
        try:
            val = int(raw)
            if val > 0:
                return val
            print("  [!] Jumlah berita harus lebih dari 0.")
        except ValueError:
            print("  [!] Masukkan angka bulat yang valid.")


def prompt_date_range() -> Tuple[date, date]:
    """Meminta input rentang waktu berita diupload (tanggal mulai s/d tanggal akhir)."""
    today_str = date.today().strftime("%Y-%m-%d")
    print(f"\nMasukkan rentang waktu berita diupload (format YYYY-MM-DD, hari ini: {today_str})")

    while True:
        raw_start = input(f"  Tanggal mulai (YYYY-MM-DD) [default: {today_str}]: ").strip()
        if not raw_start:
            start_d = date.today()
            break
        try:
            start_d = parse_date_input(raw_start)
            break
        except ValueError as e:
            print(f"  [!] {e}")

    while True:
        raw_end = input(f"  Tanggal akhir (YYYY-MM-DD) [default: {today_str}]: ").strip()
        if not raw_end:
            end_d = date.today()
            break
        try:
            end_d = parse_date_input(raw_end)
            break
        except ValueError as e:
            print(f"  [!] {e}")

    if start_d > end_d:
        start_d, end_d = end_d, start_d

    return start_d, end_d


def prompt_delay() -> float:
    """Meminta input jeda antar request (opsional, default 1.5 detik)."""
    while True:
        raw = input("Jeda antar request dalam detik [default: 1.5]: ").strip()
        if not raw:
            return 1.5
        try:
            val = float(raw)
            if val >= 0.5:
                return val
            print("  [!] Untuk menghormati server dan robots.txt, gunakan jeda minimal 0.5 detik.")
        except ValueError:
            print("  [!] Masukkan angka desimal/bulat yang valid (contoh: 1.5).")


def main():
    parser = argparse.ArgumentParser(
        description="Scraper berita dari 5 portal Indonesia (Tirto, Kompas, Detik, CNN, Tempo Non-Plus)."
    )
    parser.add_argument(
        "--portals",
        type=str,
        help="Daftar portal dipisah koma (misal: 'semua' atau 'tirto,kompas,detik'). Jika kosong, akan ditanyakan secara interaktif.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Jumlah berita yang ingin di-scrape per portal.",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Tanggal awal berita diupload (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="Tanggal akhir berita diupload (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Jeda waktu antar request dalam detik (default: 1.5).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Folder penyimpanan file JSONL (default: output/).",
    )

    args = parser.parse_args()

    # 1. Pilih portal
    if args.portals:
        raw = args.portals.strip().lower()
        if raw in ("semua", "all", "*"):
            selected_portals = list(PORTALS_CONFIG.values())
        else:
            tokens = [t.strip() for t in raw.replace(" ", ",").split(",") if t.strip()]
            selected_portals = []
            seen_keys = set()
            for tok in tokens:
                if tok in PORTALS_CONFIG:
                    cfg = PORTALS_CONFIG[tok]
                    if cfg["key"] not in seen_keys:
                        selected_portals.append(cfg)
                        seen_keys.add(cfg["key"])
                else:
                    for cfg in PORTALS_CONFIG.values():
                        if tok in cfg["key"] or tok in cfg["name"].lower():
                            if cfg["key"] not in seen_keys:
                                selected_portals.append(cfg)
                                seen_keys.add(cfg["key"])
                            break
            if not selected_portals:
                print(f"[!] Tidak ada portal valid dari argumen --portals '{args.portals}'")
                sys.exit(1)
    else:
        selected_portals = prompt_portal_selection()

    # 2. Jumlah berita
    if args.limit is not None and args.limit > 0:
        max_articles = args.limit
    else:
        max_articles = prompt_max_articles()

    # 3. Rentang waktu berita diupload
    if args.start_date and args.end_date:
        start_date = parse_date_input(args.start_date)
        end_date = parse_date_input(args.end_date)
        if start_date > end_date:
            start_date, end_date = end_date, start_date
    else:
        start_date, end_date = prompt_date_range()

    # 4. Jeda antar request
    if args.delay is not None:
        delay = max(0.5, args.delay)
    elif args.portals and args.limit and args.start_date and args.end_date:
        delay = 1.5
    else:
        delay = prompt_delay()

    os.makedirs(args.output_dir, exist_ok=True)

    print("\n" + "=" * 65)
    print("RINGKASAN KONFIGURASI SCRAPING:")
    print(f"  - Portal dipilih : {', '.join(p['name'] for p in selected_portals)}")
    print(f"  - Target berita  : {max_articles} berita / portal")
    print(f"  - Rentang tanggal: {start_date} s/d {end_date}")
    print(f"  - Jeda request   : {delay} detik (mematuhi robots.txt)")
    print("=" * 65)

    summary = {}
    for portal_cfg in selected_portals:
        out_filename = os.path.basename(portal_cfg["output"])
        out_path = os.path.join(args.output_dir, out_filename)
        try:
            count = portal_cfg["func"](
                max_articles=max_articles,
                start_date=start_date,
                end_date=end_date,
                output_file=out_path,
                delay=delay,
            )
            summary[portal_cfg["name"]] = (count, out_path)
        except KeyboardInterrupt:
            print(f"\n[!] Scraping dihentikan pengguna pada portal {portal_cfg['name']}.")
            break
        except Exception as e:
            print(f"\n[Error] Terjadi kesalahan saat scraping {portal_cfg['name']}: {e}")
            summary[portal_cfg["name"]] = (0, out_path)

    print("\n" + "=" * 65)
    print("                 HASIL AKHIR SCRAPING BERITA                     ")
    print("=" * 65)
    for pname, (cnt, fpath) in summary.items():
        print(f"  - {pname:<22}: {cnt} berita baru disimpan -> {fpath}")
    print("=" * 65)


if __name__ == "__main__":
    main()
