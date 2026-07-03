"""Modul untuk scraping data real-time dari siaran langsung TikTok.

Modul ini mendefinisikan kelas `TikTokLiveScraper` yang bertanggung jawab untuk
terhubung ke sesi live TikTok, mendengarkan berbagai event (misalnya, komentar,
suka, hadiah, pembaruan penonton), dan mengirimkan data yang dikumpulkan
ke antrean untuk diproses oleh aplikasi Streamlit utama. Ini juga mencakup
logika untuk mengelola koneksi, durasi scraping, dan penanganan event
secara asinkron.
"""
import asyncio
from datetime import datetime
from TikTokLive.client.logger import LogLevel
from TikTokLive.events import ConnectEvent, CommentEvent, LikeEvent, SocialEvent, RoomUserSeqEvent, GiftEvent, DisconnectEvent
from TikTokLive import TikTokLiveClient

class TikTokLiveScraper:
    """Mengikis data real-time dari siaran langsung TikTok.

    Kelas ini bertanggung jawab untuk terhubung ke user TikTok target,
    mendengarkan berbagai event (misalnya, komentar, suka, hadiah,
    dan pembaruan jumlah penonton). Data yang dikumpulkan kemudian
    ditempatkan ke dalam antrean (queue) agar dapat diakses dan
    ditampilkan oleh aplikasi Streamlit utama.

    Attributes:
        target (str): ID unik (username) dari user TikTok yang akan di-scrape.
        data_queue (queue.Queue): Objek antrean yang digunakan untuk
            mentransmisikan data real-time ke thread utama Streamlit.
        duration (int): Durasi maksimum (dalam detik) untuk menjalankan
            scraper jika user target sedang live. Defaultnya 600 detik.
        delay (int): Jeda (dalam detik) antar pemeriksaan untuk menentukan
            apakah user target sedang live. Defaultnya 10 detik.
        client (TikTokLiveClient): Instance dari klien TikTok Live.
        is_running (bool): Bendera yang menunjukkan apakah scraper sedang berjalan.
        loop (asyncio.BaseEventLoop): Event loop asyncio yang digunakan oleh scraper.
    """
    def __init__(self, target, data_queue, duration=600, delay=10):
        """Menginisialisasi objek TikTokLiveScraper.

        Args:
            target (str): ID unik (username) dari user TikTok yang akan di-scrape.
            data_queue (queue.Queue): Antrean yang dibagikan dari thread Streamlit
                untuk transmisi data real-time.
            duration (int, optional): Durasi maksimum (dalam detik) untuk menjalankan
                scraper jika target sedang live. Defaultnya 600 detik (10 menit).
            delay (int, optional): Jeda (dalam detik) antar pemeriksaan untuk melihat
                apakah user target sedang live. Defaultnya 10 detik.

        Raises:
            ValueError: Jika `target` (unique_id) tidak ditentukan.
        """
        self.target = target
        self.data_queue = data_queue
        self.duration = duration
        self.delay = delay
        
        if not self.target:
            raise ValueError("Target username (unique_id) harus ditentukan.")
        
        self.client = TikTokLiveClient(unique_id=self.target)
        self.is_running = False
        self.loop = None
        self.client.logger.setLevel(LogLevel.INFO.value)

        self._register_events()

    async def _stopper(self):
        """Tugas latar belakang untuk menghentikan scraper setelah durasi tertentu.

        Ini adalah coroutine yang berjalan di latar belakang dan secara berkala
        memeriksa status `is_running`. Jika scraper masih berjalan setelah
        `self.duration` detik, ia akan memutus koneksi klien TikTok Live.
        """
        for _ in range(int(self.duration)):
            if not self.is_running:
                # self._log("Stopper dihentikan lebih awal karena sinyal stop.")
                self.data_queue.put({
                    'type': 'logs',
                    'datetime': datetime.now(),
                    'message': "Menghentikan..."
                })
                break

            await asyncio.sleep(1)

        if self.is_running and self.client.connected:
            self.data_queue.put({
                'type': 'logs',
                'datetime': datetime.now(),
                'message': "Memutuskan koneksi..."
            })

            await self.client.disconnect()
        self._register_events()
    
    def _normalize_gift_quantity(self, event):
        """Menormalisasi kuantitas hadiah dari event hadiah.

        Mencoba mengekstrak kuantitas hadiah dari berbagai atribut event hadiah.
        Jika tidak dapat mengekstrak kuantitas yang valid, defaultnya adalah 1.

        Args:
            event: Objek event hadiah yang diterima dari TikTok Live.

        Returns:
            int: Kuantitas hadiah yang dinormalisasi.
        """
        for attr in ("repeat_count", "gift", "diamond_count", "combo_count"):
            value = getattr(event, attr, None)
            if value is None:
                continue
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                return parsed
        return 1

    def _register_events(self):
        """Mendaftarkan event listener untuk berbagai event TikTok Live.

        Metode ini mengaitkan fungsi-fungsi penanganan (handler) asinkron
        dengan event-event spesifik dari pustaka `TikTokLive`. Listener ini
        bertanggung jawab untuk memproses data yang masuk (misalnya, koneksi,
        pembaruan penonton, suka, komentar, share, hadiah) dan memasukkannya
        ke dalam `data_queue` untuk diproses lebih lanjut.
        """
        @self.client.on(ConnectEvent)
        async def on_connect(event: ConnectEvent):
            """Menangani ConnectEvent saat scraper berhasil terhubung ke TikTok Live.

            Mencatat koneksi yang berhasil dan memulai tugas latar belakang
            `_stopper` untuk mengelola durasi scraper, memastikan koneksi
            terputus setelah waktu yang ditentukan.

            Args:
                event (ConnectEvent): Objek event koneksi.
            """
            self.data_queue.put({
                'type': 'logs',
                'datetime': datetime.now(),
                'message': f"Berhasil terhubung ke @{event.unique_id}!"
            })
            asyncio.create_task(self._stopper())

        @self.client.on(DisconnectEvent)
        async def on_disconnect(event: DisconnectEvent):
            """Menangani DisconnectEvent saat koneksi TikTok Live terputus.

            Mencatat pesan log yang menunjukkan bahwa scraper telah terputus
            dari sesi TikTok Live target.

            Args:
                event (DisconnectEvent): Objek event pemutusan koneksi.
            """
            
            self.data_queue.put({
                'type': 'logs',
                'datetime': datetime.now(),
                'message': f"Terputus dari TikTok live: {self.target}"
            })
            
        @self.client.on(RoomUserSeqEvent)
        async def on_viewer_update(event: RoomUserSeqEvent) -> None:
            """Menangani RoomUserSeqEvent, yang memberikan pembaruan jumlah penonton.

            Mengekstrak jumlah penonton terbaru dari event dan memasukkannya
            sebagai metrik `viewer` ke dalam `data_queue`.

            Args:
                event (RoomUserSeqEvent): Objek event urutan user di room.
            """
            self.data_queue.put({
                'type': 'viewer',
                'datetime': datetime.now(),
                'value': getattr(event, 'total_user', 0)
            })

        @self.client.on(LikeEvent)
        async def on_like(event: LikeEvent) -> None:
            """Menangani LikeEvent, yang dipicu saat user mengirim 'like'.

            Mengekstrak total jumlah 'like' dari event dan memasukkannya
            sebagai metrik `like` ke dalam `data_queue`.

            Args:
                event (LikeEvent): Objek event like.
            """
            self.data_queue.put({
                'type': 'like',
                'datetime': datetime.now(),
                'value': getattr(event, 'total', 0)
            })

        @self.client.on(CommentEvent)
        async def on_comment(event: CommentEvent) -> None:
            """Menangani CommentEvent, yang dipicu saat user mengirim komentar.

            Mengekstrak detail komentar (nama panggilan, username, teks komentar)
            dan memasukkannya sebagai data `comment` ke dalam `data_queue`.

            Args:
                event (CommentEvent): Objek event komentar.
            """
            
            self.data_queue.put({
                'type': 'comment',
                'datetime': datetime.now(),
                'nickname': getattr(event.user_info, 'nick_name', getattr(event.user_info, 'nickname', '')),
                'username': getattr(event.user_info, 'unique_id', ''),
                'komentar': getattr(event, 'comment', '')
            })

        @self.client.on(SocialEvent)
        async def on_share(event: SocialEvent) -> None:
            """Menangani SocialEvent, khususnya saat menunjukkan tindakan 'share'.

            Mengekstrak jumlah 'share' dari event (jika relevan) dan memasukkannya
            sebagai metrik `share` ke dalam `data_queue`.

            Args:
                event (SocialEvent): Objek event sosial.
            """
            if "share" in getattr(event, 'display_type', '').lower() or getattr(event, 'share_count', 0) > 0:
                self.data_queue.put({
                    'type': 'share',
                    'datetime': datetime.now(),
                    'value': getattr(event, 'share_count', 0)
                })

        @self.client.on(GiftEvent)
        async def on_gift(event: GiftEvent) -> None:
            """Menangani GiftEvent, yang dipicu saat user mengirim hadiah.

            Menormalisasi kuantitas hadiah, mengekstrak detail hadiah (nama, pengirim),
            dan memasukkannya sebagai data `gift` ke dalam `data_queue`.

            Args:
                event (GiftEvent): Objek event hadiah.
            """
            gift_quantity = self._normalize_gift_quantity(event)

            self.data_queue.put({
                'type': 'gift',
                'datetime': datetime.now(),
                'value': gift_quantity,
                'gift_name': getattr(event, 'gift_name', None),
                'nickname': getattr(getattr(event, 'user', None), 'nick_name', None),
            })


    async def check_loop(self):
        """Secara terus-menerus memeriksa apakah user TikTok target sedang live.

        Coroutin ini akan terus berjalan selama `self.is_running` bernilai True.
        Jika user target sedang live, scraper akan mencoba terhubung ke siaran
        dan menghentikan loop pemeriksaan. Jika tidak live, scraper akan
        menunggu selama `self.delay` detik sebelum memeriksa lagi. Setiap
        event penting atau error akan dicatat ke `data_queue`.
        """
        while self.is_running:
            try:
                if await self.client.is_live():
                    self.client.logger.info(f'{self.target} sedang live! Menghubungkan...')
                    self.data_queue.put({
                        'type': 'logs',
                        'datetime': datetime.now(),
                        'message': f"{self.target} sedang live! Menghubungkan..."
                    })
                    await self.client.connect()
                    break
                
                self.client.logger.info(f'{self.target} sedang tidak live. Mencoba lagi dalam {self.delay} detik.')
                self.data_queue.put({
                    'type': 'logs',
                    'datetime': datetime.now(),
                    'message': f"{self.target} sedang tidak live. Mencoba lagi dalam {self.delay} detik."
                })
                
                for _ in range(int(self.delay)):
                    if not self.is_running:
                        break
                    await asyncio.sleep(1)

            except Exception as e:
                self.client.logger.warning(f"Error di check_loop: {e}")
                self.data_queue.put({
                    'type': 'logs',
                    'datetime': datetime.now(),
                    'message': f"{e}"
                })
                for _ in range(int(self.delay)):
                    if not self.is_running:
                        break
                    await asyncio.sleep(1)


    def start(self):
        """Memulai proses scraping TikTok Live.

        Metode ini mengatur flag `is_running` menjadi True, membuat
        event loop asyncio baru, dan menjalankan `check_loop` hingga
        selesai. Setiap pengecualian yang terjadi selama eksekusi loop
        akan dicatat.
        """
        self.is_running = True
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.check_loop())
        except Exception as e:
            self.client.logger.error(f"Scraper error: {e}")

        finally:
            if self.loop.is_running():
                self.loop.close()

    def stop(self):
        """Memberi sinyal agar scraper berhenti.

        Metode ini dipanggil dari thread utama (Streamlit) untuk
        menghentikan proses scraping. Ini mengatur flag `is_running`
        menjadi False dan mencoba memutuskan koneksi klien TikTok Live
        jika masih terhubung.
        """
        if not self.is_running:
            return

        self.is_running = False
        self.client.logger.info("Scraping mulai berhenti. Menutup koneksi..")

        if self.loop and self.loop.is_running():
            if self.client.connected:
                asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)
                