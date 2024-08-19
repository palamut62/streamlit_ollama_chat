import os
import json
import sqlite3
from datetime import datetime
import subprocess

import streamlit as st
from groq import Groq

# streamlit page configuration
st.set_page_config(
    page_title="LLAMA 3.1. Chat",
    page_icon="🦙",
    layout="wide"
)

working_dir = os.path.dirname(os.path.abspath(__file__))
config_data = json.load(open(".streamlit/config.json"))

GROQ_API_KEY = config_data["GROQ_API_KEY"]

# save the api key to environment variable
os.environ["GROQ_API_KEY"] = GROQ_API_KEY

client = Groq()
st.sidebar.title("🦙 LLAMA Chat")

# Function to initialize the database
def initialize_database():
    db_path = 'chat_history.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Check if tables exist
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name='chats' OR name='chat_summaries')")
    existing_tables = c.fetchall()

    if len(existing_tables) < 2:
        # Create tables if they don't exist
        c.execute('''CREATE TABLE IF NOT EXISTS chats
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      chat_id TEXT,
                      role TEXT,
                      content TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

        c.execute('''CREATE TABLE IF NOT EXISTS chat_summaries
                     (chat_id TEXT PRIMARY KEY,
                      summary TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

        conn.commit()
        st.info("Database initialized successfully.")
    else:
        st.info("Database already exists. Using existing database.")

    return conn, c


# Initialize the database
conn, c = initialize_database()


# # Ollama'nın çalışıp çalışmadığını kontrol eden ve gerekirse başlatan fonksiyon
# def check_and_run_ollama():
#     try:
#         # Ollama'nın çalışıp çalışmadığını kontrol et
#         result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ollama.exe"], capture_output=True, text=True)
#         if "ollama.exe" not in result.stdout:
#             # Ollama çalışmıyorsa, başlat
#             subprocess.Popen(["ollama", "app.exe"], shell=True)
#             st.success("Ollama otomatik olarak başlatıldı.")
#         else:
#             st.info("Ollama zaten çalışıyor.")
#     except FileNotFoundError:
#         st.error("Ollama bulunamadı. Lütfen yüklü olduğundan ve PATH'te olduğundan emin olun.")
#     except Exception as e:
#         st.error(f"Ollama kontrol edilirken bir hata oluştu: {e}")
#
#
# # Ollama'yı otomatik olarak kontrol et ve gerekirse başlat
# check_and_run_ollama()


# Function to save message to database
def save_message(chat_id, role, content):
    c.execute("INSERT INTO chats (chat_id, role, content) VALUES (?, ?, ?)",
              (chat_id, role, content))
    conn.commit()


# Function to load chat history from database
def load_chat_history(chat_id):
    c.execute("SELECT role, content FROM chats WHERE chat_id = ? ORDER BY timestamp", (chat_id,))
    return [{"role": role, "content": content} for role, content in c.fetchall()]


# Function to delete a chat
def delete_chat(chat_id):
    c.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
    c.execute("DELETE FROM chat_summaries WHERE chat_id = ?", (chat_id,))
    conn.commit()


# Function to generate and save chat summary
def generate_and_save_summary(chat_id, first_message):
    summary_prompt = f"Summarize this message in 5 words or less: {first_message}"
    summary_messages = [
        {"role": "system", "content": "You are a helpful assistant that summarizes text briefly."},
        {"role": "user", "content": summary_prompt}
    ]
    summary_response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=summary_messages
    )
    summary = summary_response.choices[0].message.content.strip()

    c.execute("INSERT OR REPLACE INTO chat_summaries (chat_id, summary) VALUES (?, ?)",
              (chat_id, summary))
    conn.commit()
    return summary


# Function to get chat summary
def get_chat_summary(chat_id):
    c.execute("SELECT summary FROM chat_summaries WHERE chat_id = ?", (chat_id,))
    result = c.fetchone()
    if result:
        return result[0]
    else:
        # If summary doesn't exist, generate it from the first message
        c.execute("SELECT content FROM chats WHERE chat_id = ? AND role = 'user' ORDER BY timestamp LIMIT 1",
                  (chat_id,))
        first_message = c.fetchone()
        if first_message:
            return generate_and_save_summary(chat_id, first_message[0])
        return "No summary available"


# Function to get all chat IDs
def get_all_chat_ids():
    c.execute("SELECT DISTINCT chat_id FROM chats ORDER BY timestamp DESC")
    return [row[0] for row in c.fetchall()]


# Sidebar

# New chat button
if st.sidebar.button("New Chat"):
    new_chat_id = datetime.now().strftime("%Y%m%d%H%M%S")
    st.session_state.current_chat_id = new_chat_id
    st.session_state.chat_history = []
    st.rerun()

# Main chat area
st.title("🦙 LLAMA 3.1. ChatBot")

# List previous chats
chat_ids = get_all_chat_ids()

for chat_id in chat_ids:
    summary = get_chat_summary(chat_id)
    col1, col2 = st.sidebar.columns([3, 1])
    if col1.button(f"{summary}", key=f"load_{chat_id}"):
        st.session_state.current_chat_id = chat_id
        st.session_state.chat_history = load_chat_history(chat_id)
        st.rerun()
    if col2.button("🗑️", key=f"delete_{chat_id}"):
        delete_chat(chat_id)
        if st.session_state.current_chat_id == chat_id:
            if chat_ids:
                st.session_state.current_chat_id = chat_ids[0]
                st.session_state.chat_history = load_chat_history(chat_ids[0])
            else:
                st.session_state.current_chat_id = datetime.now().strftime("%Y%m%d%H%M%S")
                st.session_state.chat_history = []
        st.rerun()



# Ensure current_chat_id exists
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = datetime.now().strftime("%Y%m%d%H%M%S")

# Ensure chat_history exists
if "chat_history" not in st.session_state:
    st.session_state.chat_history = load_chat_history(st.session_state.current_chat_id)

# Display chat history
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input field for user's message
user_prompt = st.chat_input("Ask LLAMA...")

if user_prompt:
    st.chat_message("user").markdown(user_prompt)
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    save_message(st.session_state.current_chat_id, "user", user_prompt)

    # Generate summary for new chats
    if len(st.session_state.chat_history) == 1:
        generate_and_save_summary(st.session_state.current_chat_id, user_prompt)

    # Send user's message to the LLM and get a response
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        *st.session_state.chat_history
    ]

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages
    )

    assistant_response = response.choices[0].message.content
    st.session_state.chat_history.append({"role": "assistant", "content": assistant_response})
    save_message(st.session_state.current_chat_id, "assistant", assistant_response)

    # Display the LLM's response
    with st.chat_message("assistant"):
        st.markdown(assistant_response)

    # Rerun to update the sidebar
    st.rerun()

# Close the database connection when the app is done
conn.close()

# streamlit run main.py