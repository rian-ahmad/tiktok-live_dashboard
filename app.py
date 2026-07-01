import queue
import threading
import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ScraperTikTokLive import TikTokLiveScraper

def init_state():
    """Menginisialisasi session state untuk menyimpan data aplikasi."""
    if 'data_queue' not in st.session_state:
        st.session_state.data_queue = queue.Queue()
    if 'scraper' not in st.session_state:
        st.session_state.scraper = None
    if 'scraper_thread' not in st.session_state:
        st.session_state.scraper_thread = None
    if 'is_running' not in st.session_state:
        st.session_state.is_running = False
    if 'target_username' not in st.session_state:
        st.session_state.target_username = ''
    
    # Penyimpanan data untuk visualisasi
    if 'viewer_data' not in st.session_state:
        st.session_state.viewer_data = []
    if 'like_data' not in st.session_state:
        st.session_state.like_data = []
    if 'share_data' not in st.session_state:
        st.session_state.share_data = []
    if 'comment_data' not in st.session_state:
        st.session_state.comment_data = []
    if 'comment_count_data' not in st.session_state:
        st.session_state.comment_count_data = []
    if 'logs' not in st.session_state:
        st.session_state.logs = []

def start_scraper(target: str):
    """Memulai thread scraper."""
    if not target:
        st.error('Masukkan username TikTok terlebih dahulu.')
        return

    if st.session_state.get('is_running'):
        st.warning('Scraper sudah berjalan. Klik Stop terlebih dahulu.')
        return
    
    # Reset data sebelumnya
    st.session_state.viewer_data = []
    st.session_state.like_data = []
    st.session_state.share_data = []
    st.session_state.comment_data = []
    st.session_state.comment_count_data = []
    st.session_state.logs = []
    st.session_state.data_queue = queue.Queue()

    scraper = TikTokLiveScraper(target=target, data_queue=st.session_state.data_queue, duration=3600, delay=15)
    thread = threading.Thread(target=scraper.start, daemon=True)

    st.session_state.scraper = scraper
    st.session_state.scraper_thread = thread
    st.session_state.target_username = target
    st.session_state.is_running = True
    
    thread.start()
    st.rerun()

def stop_scraper():
    """Menghentikan thread scraper."""
    if st.session_state.get('is_running'):
        st.session_state.is_running = False
        scraper = st.session_state.scraper
        if scraper:
            scraper.stop()
        time.sleep(2)
        st.rerun()

def drain_queue():
    """Mengambil data dari queue dan memperbarui session state."""
    while not st.session_state.data_queue.empty():
        try:
            item = st.session_state.data_queue.get_nowait()
            item_type = item.get('type')
            ts = item.get('datetime', datetime.now())

            if item_type == 'viewer':
                st.session_state.viewer_data.append({'datetime': ts, 'value': item.get('value', 0)})
            elif item_type == 'like':
                st.session_state.like_data.append({'datetime': ts, 'value': item.get('value', 0)})
            elif item_type == 'share':
                st.session_state.share_data.append({'datetime': ts, 'value': item.get('value', 0)})
            elif item_type == 'comment':
                st.session_state.comment_data.append(item)
                st.session_state.comment_count_data.append({
                    'datetime': ts,
                    'value': len(st.session_state.comment_data)
                })
            elif item_type == 'log':
                log_message = item.get('message', '')
                st.session_state.logs.append(f"{ts.strftime('%H:%M:%S')} -> {log_message}")
        except queue.Empty:
            break

    st.session_state.viewer_data = st.session_state.viewer_data[-500:]
    st.session_state.like_data = st.session_state.like_data[-500:]
    st.session_state.share_data = st.session_state.share_data[-500:]
    st.session_state.comment_count_data = st.session_state.comment_count_data[-500:]
    st.session_state.logs = st.session_state.logs[-100:]

def plot_metric(data, title, yaxis_title, color):
    """Membuat chart Plotly untuk metrik."""
    if not data:
        fig = go.Figure()
    else:
        df = pd.DataFrame(data)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['value'], mode='lines', name=yaxis_title, line=dict(color=color)))
    
    fig.update_layout(
        title=title,
        xaxis_title="Waktu",
        yaxis_title=yaxis_title,
        height=300,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    return fig

def main():
    """Fungsi utama untuk menjalankan aplikasi Streamlit."""
    st.set_page_config(layout="wide", page_title="TikTok Live Analytics")
    init_state()

    st.title(f"Dashboard Analitik TikTok Live: @{st.session_state.get('target_username', '')}")

    with st.sidebar:
        st.header('Kontrol Scraper')
        target = st.text_input(
            'Username TikTok (unique_id)',
            value=st.session_state.get('target_username', ''),
            key='target_username_input'
        )
        target = (target or '').strip()

        col1, col2 = st.columns(2)
        with col1:
            if st.button('Start', type='primary', width='stretch'):
                start_scraper(target.strip())
        with col2:
            if st.button('Stop', width='stretch'):
                stop_scraper()

        st.markdown("---")
        st.markdown("##### Log Aktivitas")
        if st.session_state.logs:
            log_text = "\n".join(reversed(st.session_state.logs))
            st.text_area("Logs", value=log_text, height=400, disabled=True, key="logs_textarea")
        else:
            st.text("Belum ada log.")

    if not st.session_state.get('is_running'):
        st.info("Masukkan username TikTok di sidebar dan klik 'Start' untuk memulai pemantauan.")
        return

    drain_queue()
    
    latest_viewer = st.session_state.viewer_data[-1]['value'] if st.session_state.viewer_data else 0
    latest_like = st.session_state.like_data[-1]['value'] if st.session_state.like_data else 0
    latest_share = st.session_state.share_data[-1]['value'] if st.session_state.share_data else 0

    kpi_cols = st.columns(4)
    kpi_cols[0].metric('Views', f"👁️ {latest_viewer}")
    kpi_cols[1].metric('Likes', f"❤️ {latest_like}")
    kpi_cols[2].metric('Comments', f"💬 {len(st.session_state.comment_data)}")
    kpi_cols[3].metric('Shares', f"🔗 {latest_share}")
    
    st.markdown("---")

    st.subheader("Tren Metrik")
    st.html("<hr>")

    plot_cols = st.columns(2)

    with plot_cols[0]:
        fig_viewer = plot_metric(st.session_state.viewer_data, "Views", "Jumlah", 'cyan')
        st.plotly_chart(fig_viewer, width='stretch')

        fig_comment = plot_metric(st.session_state.comment_count_data, "Comments", "Jumlah", 'green')
        st.plotly_chart(fig_comment, width='stretch')

    with plot_cols[1]:
        fig_like = plot_metric(st.session_state.like_data, "Likes", "Jumlah", 'magenta')
        st.plotly_chart(fig_like, width='stretch')

        fig_share = plot_metric(st.session_state.share_data, "Shares", "Jumlah", 'gold')
        st.plotly_chart(fig_share, width='stretch')

    st.markdown("---")
    st.subheader("Komentar Terbaru")
    st.html("<hr>")
    if st.session_state.comment_data:
        trimmed_comments = st.session_state.comment_data[-10:]
        for comment in reversed(trimmed_comments):
            st.markdown(f"**{comment['nickname']}**: {comment['komentar']}")
    else:
        st.text("Belum ada komentar.")


    time.sleep(1)
    st.rerun()


if __name__ == '__main__':
    main()
