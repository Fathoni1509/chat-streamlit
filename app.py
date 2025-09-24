# app.py
import os
import json
import time
import threading
from datetime import datetime

import pika
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# =====================
# Config / Env
# =====================
AMQP_URL = os.getenv("AMQP_URL")
QUEUE = "chat_room"

if not AMQP_URL:
    st.error("AMQP_URL tidak ditemukan. Set environment variable AMQP_URL (contoh: amqps://user:pass@host/vhost).")
    st.stop()

params = pika.URLParameters(AMQP_URL)

# =====================
# Helper: buat koneksi & channel
# =====================
def new_connection_channel():
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    # memastikan queue tersedia
    ch.queue_declare(queue=QUEUE, durable=True)
    return conn, ch

# =====================
# Session state init
# =====================
if "messages" not in st.session_state:
    st.session_state["messages"] = []  # menyimpan string pesan (urut)
if "listener_started" not in st.session_state:
    st.session_state["listener_started"] = False

# =====================
# Listener (background thread)
# =====================
def listen_loop():
    """Buat 1 koneksi consumer yang long-lived dan append pesan ke session_state."""
    while True:
        try:
            conn, ch = new_connection_channel()

            def on_message(ch_, method, properties, body):
                try:
                    # menerima JSON jika ada, fallback plain text
                    payload = json.loads(body.decode())
                    sender = payload.get("sender", "")
                    text = payload.get("text", "")
                    ts = payload.get("timestamp", "")
                    pretty = f"📩 [{ts}] {sender}: {text}"
                except Exception:
                    pretty = body.decode()

                # hindari duplikat
                if pretty not in st.session_state["messages"]:
                    st.session_state["messages"].append(pretty)

            ch.basic_consume(queue=QUEUE, on_message_callback=on_message, auto_ack=True)
            ch.start_consuming()  # blocking sampai error / closed
        except Exception as e:
            # kalau error (network, timeout), tunggu lalu retry
            print("Listener error:", e)
            time.sleep(3)
            continue

# start listener hanya sekali per session
if not st.session_state["listener_started"]:
    t = threading.Thread(target=listen_loop, daemon=True)
    t.start()
    st.session_state["listener_started"] = True

# =====================
# Auto refresh UI tiap 2 detik
# =====================
# st_autorefresh mengembalikan counter (tidak perlu dipakai)
st_autorefresh(interval=2000, key="autorefresh")

# =====================
# UI: login & chat
# =====================
st.title("💬 Chat Room (AMQPS + Streamlit)")

# Login sekali
if "username" not in st.session_state or not st.session_state["username"]:
    with st.form("login_form"):
        uname = st.text_input("Masukkan nama Anda:", "")
        ok = st.form_submit_button("Masuk")
        if ok and uname.strip():
            st.session_state["username"] = uname.strip()
            st.experimental_rerun()
    st.stop()

# Chat form
with st.form("chat_form", clear_on_submit=True):
    message = st.text_input("Ketik pesan Anda:")
    send = st.form_submit_button("Kirim")
    if send and message.strip():
        payload = {
            "sender": st.session_state["username"],
            "text": message.strip(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            conn_pub, ch_pub = new_connection_channel()
            ch_pub.basic_publish(exchange="", routing_key=QUEUE, body=json.dumps(payload))
            conn_pub.close()
            # tampilkan di UI pengirim
            st.session_state["messages"].append(f"📤 [{payload['timestamp']}] {payload['sender']}: {payload['text']}")
        except Exception as e:
            st.error(f"Gagal kirim pesan: {e}")

# Chat display
st.subheader("📜 Chat Room")
for msg in st.session_state["messages"]:
    st.write(msg)
