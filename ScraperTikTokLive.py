import asyncio
import logging
from datetime import datetime
from TikTokLive import TikTokLiveClient
from TikTokLive.client.logger import LogLevel
from TikTokLive.events import ConnectEvent, CommentEvent, LikeEvent, SocialEvent, RoomUserSeqEvent

class QueueLogHandler(logging.Handler):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        msg = self.format(record)
        self.queue.put({
            'type': 'log',
            'datetime': datetime.fromtimestamp(record.created),
            'message': msg
        })

class TikTokLiveScraper:
    def __init__(self, target, data_queue, duration=600, delay=10):
        """
        Menginisialisasi TikTokLiveScraper di memori.

        Args:
            target (str): ID unik dari user TikTok yang akan di-scrap.
            data_queue (queue.Queue): antrian yang dishare dari thread Streamlit
                                      untuk transmisi data real-time.
            duration (int, opsional): Durasi maksimum (dalam detik) untuk menjalankan
                                       scraper jika target sedang live.
                                       Defaultnya adalah 600 detik (10 menit).
            delay (int, opsional): Jeda (dalam detik) antar pemeriksaan untuk melihat
                                    apakah user target sedang live. Defaultnya 10 detik.

        Raises:
            ValueError: Jika nama user target (unique_id) tidak ditentukan.
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
        
        # Konfigurasi logging untuk dikirim ke queue
        log_handler = QueueLogHandler(self.data_queue)
        formatter = logging.Formatter('%(message)s')
        log_handler.setFormatter(formatter)
        self.client.logger.addHandler(log_handler)
        self.client.logger.setLevel(LogLevel.INFO.value)
        self.client.logger.propagate = False

        self._register_events()

    def _register_events(self):
        """
        Mendaftarkan event listener untuk berbagai event TikTok Live.
        Listener ini memproses data yang masuk (koneksi, pembaruan penonton, like,
        komentar, share) dan memasukkannya ke dalam antrian data bersama.
        """
        @self.client.on(ConnectEvent)
        async def on_connect(event: ConnectEvent):
            """
            Menangani ConnectEvent, yang dipicu saat scraper berhasil terhubung
            ke TikTok Live. Ini mencatat koneksi dan mengelola durasi
            scraper, memutuskan koneksi setelah waktu yang ditentukan jika masih berjalan.

            Args:
                event (ConnectEvent): Objek event koneksi.
            """
            self.client.logger.info(f"Terhubung ke @{event.unique_id}!")
            for _ in range(int(self.duration)):
                if not self.is_running:
                    break
                await asyncio.sleep(1)
            
            if self.is_running and self.client.connected:
                await self.client.disconnect()

        @self.client.on(RoomUserSeqEvent)
        async def on_viewer_update(event: RoomUserSeqEvent) -> None:
            """
            Menangani RoomUserSeqEvent, yang memberikan pembaruan jumlah penonton.
            Memasukkan metrik penonton ke dalam antrian data.

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
            """
            Menangani LikeEvent, yang dipicu saat user mengirim like.
            Memasukkan metrik like ke dalam antrian data.

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
            """
            Menangani CommentEvent, yang dipicu saat user mengirim komentar.
            Memasukkan data komentar ke dalam antrian data.

            Args:
                event (CommentEvent): Objek event komentar.
            """
            user = self.target
            self.data_queue.put({
                'type': 'comment',
                'datetime': datetime.now(),
                'nickname': getattr(event.user, 'nick_name'),
                'username': getattr(event.user, 'unique_id', ''),
                'komentar': getattr(event, 'comment', '')
            })

        @self.client.on(SocialEvent)
        async def on_share(event: SocialEvent) -> None:
            """
            Menangani SocialEvent, khususnya saat event tersebut menunjukkan tindakan share.
            Memasukkan metrik share ke dalam antrian data.

            Args:
                event (SocialEvent): Objek event sosial.
            """
            if "share" in getattr(event, 'display_type', '').lower() or getattr(event, 'share_count', 0) > 0:
                self.data_queue.put({
                    'type': 'share',
                    'datetime': datetime.now(),
                    'value': getattr(event, 'share_count', 0)
                })

    async def check_loop(self):
        """
        Secara terus-menerus memeriksa apakah user TikTok target sedang live.
        Jika live, ia terhubung ke siaran dan menghentikan loop. Jika tidak live,
        ia menunggu jeda yang ditentukan sebelum memeriksa lagi. Loop ini
        berjalan selama `is_running` bernilai True.
        """
        while self.is_running:
            try:
                if await self.client.is_live():
                    self.client.logger.info(f'{self.target} sedang live! Menghubungkan...')
                    await self.client.connect()
                    self.client.logger.info(f'Tersammbung ke siaran TikTok: {self.target}')
                    break
                
                self.client.logger.info(f'{self.target} sedang tidak live. Mencoba lagi dalam {self.delay} detik.')
                for _ in range(int(self.delay)):
                    if not self.is_running:
                        break
                    await asyncio.sleep(1)
            except Exception as e:
                self.client.logger.error(f"Error di check_loop: {e}")
                # Tambahkan jeda sebelum mencoba lagi untuk menghindari spamming jika ada error koneksi
                for _ in range(int(self.delay)):
                    if not self.is_running:
                        break
                    await asyncio.sleep(1)


    def start(self):
        """
        Memulai scraper TikTok Live.
        Ini mengatur level logger, menyetel flag berjalan ke `True`, membuat
        event loop asyncio baru, dan menjalankan `check_loop` hingga selesai.
        Setiap pengecualian selama eksekusi loop akan dicatat.
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
        """
        Menghentikan scraper TikTok Live.
        Menyetel flag `is_running` ke `False` untuk menghentikan `check_loop`.
        Jika scraper terhubung ke siaran langsung, ia akan terputus secara aman.
        """
        self.is_running = False
        if self.loop and self.loop.is_running():
            if self.client.connected:
                asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)
            
            # Beri waktu untuk loop event untuk memproses pemutusan
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.client.logger.info(f"Terputus dari siaran TikTok: {self.target}")
            self.loop.close()
            self.loop = None