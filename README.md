# TikTok Live Dashboard

Dokumentasi teknis untuk proyek *TikTok Live Dashboard* — sebuah aplikasi monitoring sederhana
yang memadukan scraper real-time dari TikTok Live dengan antarmuka visual berbasis Streamlit.

Repository ini berisi dua komponen utama:

- `ScraperTikTokLive.py` — modul scraper yang bertanggung jawab terhubung ke TikTok Live,
  mendengarkan event (viewer, like, comment, share) dan mengirimkan data ke sebuah
  `queue.Queue` bersama untuk dikonsumsi oleh antarmuka.
- `app.py` — aplikasi Streamlit yang menjalankan UI, mengelola session state, menampung
  data dari queue, dan merender metrik serta log secara real-time.

## Fitur Utama

- Monitoring real-time: jumlah penonton, likes, shares, dan komentar.
- Logging terpusat via `QueueLogHandler` untuk menyalurkan log dari scraper ke UI.
- Visualisasi metrik interaktif menggunakan Plotly.
- Kontrol start/stop scraper langsung dari sidebar Streamlit.

## Prasyarat

- Python 3.10+ (direkomendasikan 3.12)
- Dependensi tercantum di `requirements.txt`.

Pastikan Anda menjalankan lingkungan virtual sebelum menginstal dependensi:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Struktur & Komponen Teknis

- `ScraperTikTokLive.TikTokLiveScraper`
  - Parameter utama: `target` (unique_id), `data_queue` (shared queue), `duration`, `delay`.
  - Mendaftarkan listener event: `ConnectEvent`, `RoomUserSeqEvent` (viewer),
    `LikeEvent`, `CommentEvent`, `SocialEvent` (share).
  - Event handler menaruh objek sederhana ke `data_queue` dalam format:
    ```json
    { "type": "viewer|like|share|comment|log", "datetime": "ISO", "value": n }
    ```
  - `QueueLogHandler` menyalurkan pesan logger ke queue dengan `type: 'log'`.
  - Menjalankan loop pengecekan `check_loop()` yang memeriksa apakah target sedang live,
    lalu melakukan koneksi dan mendengarkan event selama `duration` detik.

- `app.py` (Streamlit)
  - Menginisialisasi `st.session_state` untuk menyimpan queue, thread scraper, flags, dan
    list metrik: `viewer_data`, `like_data`, `share_data`, `comment_data`.
  - `start_scraper(target)` membuat instance `TikTokLiveScraper` dan menjalankannya
    pada thread daemon terpisah.
  - `drain_queue()` dipanggil pada loop UI untuk mengosongkan `data_queue` dan
    memindahkan entri ke session state untuk visualisasi.
  - Visualisasi menggunakan Plotly (`plot_metric`) dan menampilkan KPI serta log.

## Cara Menjalankan

1. Aktifkan environment dan instal dependensi (lihat bagian *Prasyarat*).
2. Jalankan aplikasi Streamlit:

```powershell
streamlit run app.py
```

3. Buka URL Streamlit yang tertera (biasanya `http://localhost:8501`).
4. Masukkan `Username TikTok (unique_id)` di sidebar lalu klik `Start`.

Catatan: `ScraperTikTokLive` bergantung pada paket `TikTokLive` (atau nama paket
klien TikTok Live yang sesuai). Jika Anda mendapatkan error koneksi atau versi API,
pastikan paket tersebut terinstal dan kompatibel.

## Konfigurasi & Parameter

- `duration` (default di `app.py`: 3600 pada pemanggilan) — batas maksimum
  scraping saat target live (detik).
- `delay` (default: 15) — jeda antar pemeriksaan apakah target sedang live.
- Anda bisa mengubah nilai ini langsung di pemanggilan `TikTokLiveScraper` dalam `app.py`.

## Format Data yang Dikirim ke UI

- Viewer: `{ 'type':'viewer', 'datetime': datetime, 'value': total_user }`
- Like:   `{ 'type':'like', 'datetime': datetime, 'value': total }`
- Share:  `{ 'type':'share', 'datetime': datetime, 'value': share_count }`
- Comment: `{ 'type':'comment', 'datetime': datetime, 'nickname': str, 'username': str, 'komentar': str }`
- Log:    `{ 'type':'log', 'datetime': datetime, 'message': str }`

## Debugging & Troubleshooting

- Jika aplikasi Streamlit tidak menerima data, periksa log Streamlit di terminal.
- Pastikan `requirements.txt` mengandung dependensi untuk `TikTokLive`.
- Jika `TikTokLiveClient.is_live()` selalu `False`, verifikasi `unique_id` target
  dan stabilitas koneksi jaringan.
- Untuk debugging detail pada level event, periksa keluaran logger yang
  dikirim ke sidebar `Logs` pada UI.

## Keamanan & Etika

Gunakan alat ini hanya untuk memantau siaran yang Anda punya izin untuk melacak.
Hindari scraping yang melanggar Terms of Service atau privasi pengguna.

## Pengembangan Selanjutnya (Saran)

- Simpan metrik ke penyimpanan persist untuk analisis historis.
- Tambahkan autentikasi atau rate-limiting jika digunakan multi-user.
- Tambahkan fitur download csv/json.
- Tambah filter komentar (moderasi/keyword) dan notifikasi real-time.
