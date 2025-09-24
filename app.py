# app.py
import os
import pika
import streamlit as st
import threading
import time

# =====================
# Konfigurasi AMQP
# =====================
AMQP_URL = os.getenv("AMQP_URL")

if not AMQP_URL:
    st.error("AMQP_URL tidak ditemukan. Pastikan sudah diset di Railway Variables.")
    st.stop()

params = pika.URLParameters(AMQP_URL)

# Pastikan queue ada
def get_channel():
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue="chat_room", durable=True)
    return connection, channel

# =====================
# Global Chat State
# =====================
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# =====================
# Listener Thread
# =====================
def listen_messages():
    while True:
        try:
            connection, channel = get_channel()

            def callback(ch, method, properties, body):
                msg = body.decode()
                if msg not in st.session_state["messages"]:
                    st.session_state["messages"].append(msg)

            channel.basic_consume(
                queue="chat_room",
                on_message_callback=callback,
                auto_ack=True
            )
            channel.start_consuming()
        except Exception as e:
            print("Listener error:", e)
            time.sleep(5)  # retry kalau error

# Jalankan listener hanya sekali
if "listener_started" not in st.session_state:
    threading.Thread(target=listen_messages, daemon=True).start()
    st.session_state["listener_started"] = True

# =====================
# Streamlit UI
# =====================
st.title("💬 Chat Room (AMQP + Streamlit)")

# Auto refresh setiap 2 detik
st_autorefresh = st.experimental_rerun if hasattr(st, "experimental_rerun") else None
st_autorefresh = st.autorefresh if hasattr(st, "autorefresh") else None

st_autorefresh = st_autorefresh or st.autorefresh
st_autorefresh(interval=2000, key="refresh_chat")

# Input nama pengguna (sekali di awal)
if "username" not in st.session_state:
    st.session_state["username"] = st.text_input("Masukkan nama Anda:")

# Jika sudah ada nama
if st.session_state["username"]:
    with st.form("chat_form", clear_on_submit=True):
        message = st.text_input("Ketik pesan Anda:")
        submitted = st.form_submit_button("Kirim")
        if submitted and message:
            full_msg = f"{st.session_state['username']}: {message}"
            try:
                _, channel = get_channel()
                channel.basic_publish(
                    exchange="",
                    routing_key="chat_room",
                    body=full_msg.encode()
                )
                channel.close()
            except Exception as e:
                st.error(f"Gagal mengirim pesan: {e}")

# =====================
# Tampilkan Chat
# =====================
st.subheader("📜 Chat Room")
for msg in st.session_state["messages"]:
    st.write(msg)
