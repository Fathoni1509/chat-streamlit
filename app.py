import streamlit as st
import pika, threading, json
from datetime import datetime

RABBIT_URL = "amqps://txnuaima:P82-IuzP7j0lY1H0xG_f1w2lRudjUy4t@vulture.rmq.cloudamqp.com/txnuaima"
QUEUE_NAME = "chat_queue"

# Input username
if "username" not in st.session_state:
    st.session_state["username"] = st.text_input("Masukkan nama Anda:")

# Setup koneksi (sekali aja)
if "connection" not in st.session_state:
    params = pika.URLParameters(RABBIT_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    st.session_state["channel"] = channel

# Tempat simpan pesan
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Callback untuk pesan masuk
def callback(ch, method, properties, body):
    data = json.loads(body.decode())
    st.session_state["messages"].append(f"📩 [{data['timestamp']}] {data['sender']}: {data['text']}")

# Jalankan consumer di thread
def start_consumer():
    consumer_connection = pika.BlockingConnection(pika.URLParameters(RABBIT_URL))
    consumer_channel = consumer_connection.channel()
    consumer_channel.queue_declare(queue=QUEUE_NAME, durable=True)
    consumer_channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback, auto_ack=True)
    consumer_channel.start_consuming()

if "consumer_thread" not in st.session_state:
    t = threading.Thread(target=start_consumer, daemon=True)
    t.start()
    st.session_state["consumer_thread"] = t

# Input pesan
msg = st.text_input("Ketik pesan:")
if st.button("Kirim"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {"sender": st.session_state["username"], "text": msg, "timestamp": timestamp}
    st.session_state["channel"].basic_publish(exchange="", routing_key=QUEUE_NAME, body=json.dumps(data))
    st.session_state["messages"].append(f"📤 [{timestamp}] {st.session_state['username']}: {msg}")

# Tampilkan pesan
for m in st.session_state["messages"]:
    st.write(m)


