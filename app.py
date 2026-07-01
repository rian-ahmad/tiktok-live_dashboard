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
    if 'gift_data' not in st.session_state:
        st.session_state.gift_data = []
    if 'gift_count_data' not in st.session_state:
        st.session_state.gift_count_data = []
    if 'logs' not in st.session_state:
        st.session_state.logs = []

def start_scraper(target: str, duration: int=60):
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
    st.session_state.gift_data = []
    st.session_state.gift_count_data = []
    st.session_state.logs = []
    st.session_state.data_queue = queue.Queue()

    scraper = TikTokLiveScraper(target=target, data_queue=st.session_state.data_queue, duration=duration, delay=15)
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
        scraper = st.session_state.scraper
        if scraper:
            scraper.stop()
        
        time.sleep(1.5) 

        st.session_state.is_running = False
        drain_queue()
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
            elif item_type == 'gift':
                gift_quantity = max(int(item.get('value', 1) or 1), 1)
                st.session_state.gift_data.append({**item, 'value': gift_quantity})

                total_gifts = sum(
                    max(int(entry.get('value', 1) or 1), 1)
                    for entry in st.session_state.gift_data
                )

                st.session_state.gift_count_data.append({
                    'datetime': ts,
                    'value': total_gifts
                })
            elif item_type == 'logs':
                st.session_state.logs.append({'datetime': ts, 'message': item.get('message', '')})
        except queue.Empty:
            break

    st.session_state.viewer_data = st.session_state.viewer_data[-500:]
    st.session_state.like_data = st.session_state.like_data[-500:]
    st.session_state.share_data = st.session_state.share_data[-500:]
    st.session_state.comment_data = st.session_state.comment_data[-100:]
    st.session_state.comment_count_data = st.session_state.comment_count_data[-500:]
    st.session_state.gift_data = st.session_state.gift_data[-500:]
    st.session_state.gift_count_data = st.session_state.gift_count_data[-500:]
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

@st.fragment(run_every=1)
def render_realtime():

    if st.session_state.get('is_running'):
        drain_queue()

    latest_viewer = st.session_state.viewer_data[-1]['value'] if st.session_state.viewer_data else 0
    latest_like = st.session_state.like_data[-1]['value'] if st.session_state.like_data else 0
    latest_share = st.session_state.share_data[-1]['value'] if st.session_state.share_data else 0
    latest_gift_count = st.session_state.gift_count_data[-1]['value'] if st.session_state.gift_count_data else 0


    kpi_cols = st.columns(5)
    kpi_cols[0].metric('Views', f"👁️ {latest_viewer}")
    kpi_cols[1].metric('Likes', f"❤️ {latest_like}")
    kpi_cols[2].metric('Comments', f"💬 {len(st.session_state.comment_data)}")
    kpi_cols[3].metric('Shares', f"🔗 {latest_share}")
    kpi_cols[4].metric('Gifts', f"🎁 {latest_gift_count}")


    col_1, col_2 = st.columns([3, 1])
    with col_1:
        st.subheader("Tren Metrik", divider=True)

        plot_cols = st.columns(2)

        with plot_cols[0]:
            fig_viewer = plot_metric(st.session_state.viewer_data, "Views", "Jumlah", 'cyan')
            st.plotly_chart(fig_viewer, width='stretch')

            fig_comment = plot_metric(st.session_state.comment_count_data, "Comments", "Jumlah", 'green')
            st.plotly_chart(fig_comment, width='stretch')

            fig_gift = plot_metric(st.session_state.gift_count_data, "Gifts", "Jumlah", 'red')
            st.plotly_chart(fig_gift, width='stretch')

        with plot_cols[1]:
            fig_like = plot_metric(st.session_state.like_data, "Likes", "Jumlah", 'magenta')
            st.plotly_chart(fig_like, width='stretch')

            fig_share = plot_metric(st.session_state.share_data, "Shares", "Jumlah", 'gold')
            st.plotly_chart(fig_share, width='stretch')

    with col_2:
        st.subheader("Komentar", divider=True)
        if st.session_state.comment_data:
            trimmed_comments = st.session_state.comment_data[-20:]
            for comment in reversed(trimmed_comments):
                st.markdown(f"**{comment['nickname']}**: {comment['komentar']}")
        else:
            st.markdown("Belum ada komentar.")
    
    st.divider()
    with st.bottom:
        with st.expander("Lihat Log Aktivitas"):
            if st.session_state.logs:
                log_entries = st.session_state.logs
                formatted_messages = [f"{log['datetime'].strftime('%H:%M:%S')} -> {log['message']}" for log in reversed(log_entries)]
                log_string = "\n".join(formatted_messages)
                st.code(log_string, language="text")
            else:
                st.code("Belum ada log.", language="text", width="content")


def main():
    """Fungsi utama untuk menjalankan aplikasi Streamlit."""
    st.set_page_config(layout="wide", page_title="TikTok Live Analytics")
    init_state()

    st.title(f"Dashboard Analitik TikTok Live: @{st.session_state.get('target_username', '')}")
    st.divider()

    with st.sidebar:
        st.header('Kontrol Scraper', divider=True)
        target = st.text_input(
            'Username TikTok (unique_id)',
            value=st.session_state.get('target_username', ''),
            key='target_username_input'
        )
        duration = st.number_input(
            'Durasi Scraper (detik)',
            min_value=10,
            value=600,
            step=10,
            key='duration_input'
        )

        target = (target or '').strip()
        duration = int(duration)

        col1, col2 = st.columns(2)
        with col1:
            if st.button('Start', type='primary', width='stretch'):
                start_scraper(target.strip(), duration)
        with col2:
            if st.button('Stop', width='stretch'):
                stop_scraper()
        
        if st.session_state.get('is_running'):
            st.success(f"Memantau @{st.session_state.target_username}...")
        else:
            st.info("Scraper tidak berjalan.")

    if not st.session_state.get('target_username'):
        st.info("Masukkan username TikTok di sidebar dan klik 'Start' untuk memulai pemantauan.")
        return

    render_realtime()


if __name__ == '__main__':
    main()
