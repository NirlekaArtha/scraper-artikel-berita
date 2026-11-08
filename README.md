# Indonesian News Scraper (5 Portal Berita)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python: 3.8+](https://img.shields.io/badge/python-3.8+-brightgreen.svg)](https://www.python.org/)
[![Format: JSONL](https://img.shields.io/badge/output-JSONL-orange.svg)](#format-data-output)

Aplikasi scraper artikel berita otomatis berbasis Python yang dirancang untuk mengumpulkan korpus data teks berita berbahasa Indonesia dari 5 portal berita nasional terpopuler secara terstruktur dan terstandarisasi. Proyek ini sangat cocok untuk kebutuhan riset akademik, skripsi, pemrosesan bahasa alami (NLP), *text mining*, maupun analisis sentimen.

---

## 📑 Daftar Isi

- [Daftar Portal yang Didukung](#-daftar-portal-yang-didukung)
- [Fitur Utama](#-fitur-utama)
- [Struktur Proyek](#-struktur-proyek)
- [Prasyarat Sistem](#-prasyarat-sistem)
- [Instalasi](#-instalasi)
- [Cara Penggunaan](#-cara-penggunaan)
  - [1. Mode Interaktif (Wizard)](#1-mode-interaktif-wizard)
  - [2. Mode Command Line Interface (CLI)](#2-mode-command-line-interface-cli)
- [Format Data Output](#-format-data-output)
- [Etika Scraping (Politeness & Robots.txt)](#-etika-scraping-politeness--robotstxt)
- [Lisensi & Hak Cipta](#-lisensi--hak-cipta)

---

## 🌐 Daftar Portal yang Didukung

| No | Portal Berita | Domain | Karakteristik / Penanganan Khusus | File Output Default |
|:--:|:---|:---|:---|:---|
| 1 | **Tirto.id** | `tirto.id` | Penelusuran arsip tanggal, bypass Cloudflare via TLS impersonation | `output/tirto.jsonl` |
| 2 | **Kompas.com** | `kompas.com` | Penelusuran kanal indeks tanggal & paginasi berita | `output/kompas.jsonl` |
| 3 | **Detik.com** | `detik.com` | Penelusuran indeks berita per tanggal & penanganan multi-halaman | `output/detik.jsonl` |
| 4 | **CNN Indonesia** | `cnnindonesia.com` | Penelusuran indeks per tanggal & ekstraksi artikel bersih | `output/cnn.jsonl` |
| 5 | **Tempo.co** | `tempo.co` | Khusus artikel **Non-Plus** (gratis/terbuka), otomatis menyaring konten berbayar | `output/tempo.jsonl` |

---

## ✨ Fitur Utama

- **Multi-Portal Scraping**: Mengambil berita dari satu atau kelima portal sekaligus dalam satu sesi eksekusi.
- **Filter Berdasarkan Rentang Tanggal**: Dapat menentukan rentang tanggal upload berita (`start_date` sampai `end_date`).
- **Batasan Jumlah Berita**: Mengatur kuota target artikel per portal agar proses pengumpulan data terukur.
- **Deduplikasi Otomatis**: Memeriksa URL yang telah tersimpan di file output sebelumnya sehingga tidak terjadi duplikasi data saat script dijalankan berulang kali.
- **Pembersihan Konten Otomatis**: Membuang teks pengganggu seperti "Baca Juga", "Simak Video di atas", caption foto, dan tag iklan serta menghitung jumlah kata (`jumlah_kata`) secara otomatis.
- **Pencegahan Blokir & Rate Limiting**:
  - Pengecekan otomatis aturan `robots.txt` pada setiap domain portal.
  - Delay request yang dapat disesuaikan (default: 1.5 detik per request).
  - Integrasi dengan `curl_cffi` untuk TLS fingerprint impersonation (mengatasi proteksi Cloudflare).
- **Format Output JSON Lines (`.jsonl`)**: Format standar data sains dan *machine learning*, di mana setiap baris mewakili 1 dokumen artikel JSON mandiri.
- **Dukungan Interaktif & CLI**: Dilengkapi antarmuka interaktif yang ramah pengguna serta opsi argumen command line flags lengkap untuk otomasi skrip (cron/background).

---

## 📁 Struktur Proyek

```text
.
├── LICENSE                 # Berkas Lisensi Resmi GNU General Public License v3 (GPLv3)
├── README.md                # Dokumentasi petunjuk penggunaan proyek
├── requirements.txt         # Daftar pustaka / dependensi Python
├── main.py                  # Skrip utama (CLI & Interactive runner)
├── output/                  # Direktori penyimpanan hasil scraping (.jsonl)
│   ├── tirto.jsonl
│   ├── kompas.jsonl
│   ├── detik.jsonl
│   ├── cnn.jsonl
│   └── tempo.jsonl
└── scrapers/                # Modul scraper masing-masing portal
    ├── __init__.py
    ├── utils.py             # Utilitas bersama (robots.txt, delay, cleaner, JSONL writer)
    ├── cnn.py
    ├── detik.py
    ├── kompas.py
    ├── tempo.py
    └── tirto.py
```

---

## 💻 Prasyarat Sistem

- **Python**: Versi 3.8 ke atas (disarankan Python 3.10+)
- **Sistem Operasi**: Linux, macOS, atau Windows
- Koneksi internet aktif

---

## 🚀 Instalasi

1. **Clone atau Unduh Repositori**:
   ```bash
   git clone <URL_REPOSITORY_ANDA>
   cd "script scraping"
   ```

2. **Buat dan Aktifkan Virtual Environment** (disarankan):
   ```bash
   # Di Linux / macOS:
   python3 -m venv venv
   source venv/bin/activate

   # Di Windows (PowerShell):
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install Dependensi**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 📖 Cara Penggunaan

### 1. Mode Interaktif (Wizard)

Jika dijalankan tanpa argumen, program akan menampilkan panduan interaktif langkah demi langkah:

```bash
python main.py
```

Alur pertanyaan interaktif:
1. **Pilih portal**: Masukkan nomor portal (misal `1,2`), nama (misal `kompas,detik`), atau ketik `semua`.
2. **Target berita**: Masukkan jumlah berita yang ingin diambil per portal (contoh: `20`).
3. **Rentang tanggal**: Masukkan tanggal awal dan tanggal akhir berita (format `YYYY-MM-DD`, contoh: `2026-11-01` sampai `2026-11-08`).
4. **Jeda request**: Tentukan jeda waktu antar pemanggilan request (default: `1.5` detik).

---

### 2. Mode Command Line Interface (CLI)

Program dapat dijalankan secara langsung dengan memberikan parameter argumen untuk keperluan otomatisasi:

```bash
python main.py [OPSI]
```

#### Daftar Opsi Argumen:

| Parameter | Tipe | Default | Keterangan |
|:---|:---:|:---:|:---|
| `--portals` | String | `None` (Interaktif) | Daftar portal dipisahkan tanda koma (contoh: `semua`, `tirto,kompas`, atau `1,3,4`) |
| `--limit` | Integer | `None` (Interaktif) | Jumlah target artikel per portal (contoh: `50`) |
| `--start-date` | String | `None` (Interaktif) | Tanggal mulai terbit (format `YYYY-MM-DD`, contoh: `2026-11-01`) |
| `--end-date` | String | `None` (Interaktif) | Tanggal akhir terbit (format `YYYY-MM-DD`, contoh: `2026-11-08`) |
| `--delay` | Float | `1.5` | Waktu jeda antar request dalam detik (minimal `0.5`) |
| `--output-dir` | String | `output` | Lokasi folder penyimpanan file `.jsonl` |

#### Contoh Perintah:

- **Scrape semua portal berita untuk rentang tanggal tertentu (masing-masing 30 artikel):**
  ```bash
  python main.py --portals semua --limit 30 --start-date 2026-11-01 --end-date 2026-11-08
  ```

- **Scrape hanya Kompas dan Detik dengan jeda 2 detik:**
  ```bash
  python main.py --portals kompas,detik --limit 50 --start-date 2026-11-05 --end-date 2026-11-07 --delay 2.0
  ```

- **Scrape dengan lokasi output kustom:**
  ```bash
  python main.py --portals tirto --limit 10 --start-date 2026-11-01 --end-date 2026-11-01 --output-dir data_skripsi
  ```

---

## 📊 Format Data Output

Data disimpan dalam format **JSON Lines (`.jsonl`)**, di mana tiap baris adalah satu objek JSON lengkap dengan skema sebagai berikut:

```json
{
  "nama_portal_berita": "kompas.com",
  "judul": "Judul Artikel Berita Terkait",
  "tanggal_terbit": "2026-11-08 14:30:00",
  "isi_berita": "Paragraf lengkap isi berita yang telah dibersihkan dari tag HTML dan teks pengganggu...",
  "jumlah_kata": 425,
  "url": "https://www.kompas.com/..."
}
```

### Membaca Data Output di Python / Pandas:

```python
import pandas as pd

# Membaca berkas JSONL ke DataFrame Pandas
df = pd.read_json("output/kompas.jsonl", lines=True)
print(df.head())
print(f"Total berita berhasil dikumpulkan: {len(df)}")
```

---

## 🛡️ Etika Scraping (Politeness & Robots.txt)

Skrip ini dibangun dengan menerapkan prinsip *ethical web scraping*:
1. **Pengecekan Robots.txt**: Skrip memeriksa file `robots.txt` pada portal target untuk memastikan URL path diizinkan untuk di-crawl.
2. **Rate Limiting**: Disertakan waktu jeda (*crawl delay*) antar request (minimal 0.5 detik, rekomendasi 1.5 - 3 detik) untuk meminimalisir beban pada server media terkait.
3. **Penyimpanan Selektif**: Mengabaikan konten artikel berbayar/premium (seperti Tempo Plus) dan hanya mengumpulkan konten yang dipublikasikan secara terbuka untuk publik.
4. **Tujuan**: Data ditujukan untuk penggunaan penelitian, pendidikan, dan analisis non-komersial.

---

## ⚖️ Lisensi & Hak Cipta

Proyek ini dilisensikan di bawah **[GNU General Public License v3.0 (GPLv3)](LICENSE)**.

```text
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
```
