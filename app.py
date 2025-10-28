"""
Streamlit World Clock Dashboard + Telegram /check command + Alarm feature
File: streamlit_world_clock_bot.py

Features:
- Streamlit dashboard that shows multiple timezones (big main clock + grid of other clocks)
- Choose built-in cities or add custom timezone (IANA tz name) or custom city name
- Optional auto-refresh (uses streamlit-autorefresh if installed) with fallback manual Refresh button
- Telegram bot integration (python-telegram-bot). Handles /check to reply current times for configured zones
- Alarm system: users can set alarms per timezone; when alarm time is reached, app plays a beep sound and highlights alarm.

How to run:
1) Install dependencies:
   pip install streamlit pytz python-telegram-bot==13.15 tzdata simpleaudio
   # optional auto-refresh dependency:
   pip install streamlit-autorefresh

2) Set TELEGRAM_TOKEN environment variable with your bot token:
   export TELEGRAM_TOKEN="123456:ABC-DEF..."   # linux/mac
   set TELEGRAM_TOKEN=123456:ABC-DEF...         # windows

3) Run streamlit app:
   streamlit run streamlit_world_clock_bot.py
"""

import os
import threading
import time
from datetime import datetime
import pytz
import streamlit as st

# optional for playing beep
try:
    import simpleaudio as sa
    SIMPLEAUDIO_AVAILABLE = True
except Exception:
    SIMPLEAUDIO_AVAILABLE = False

# Telegram imports (optional)
try:
    from telegram import Update
    from telegram.ext import Updater, CommandHandler, CallbackContext
    TELEGRAM_AVAILABLE = True
except Exception:
    TELEGRAM_AVAILABLE = False

DEFAULT_CITIES = {
    "WIB (Jakarta)": "Asia/Jakarta",
    "Tokyo": "Asia/Tokyo",
    "New York": "America/New_York",
    "Sydney": "Australia/Sydney",
    "London": "Europe/London",
    "UTC": "UTC",
}

APP_TITLE = "World Clock Dashboard"

# --- Utility functions ---

def get_time_for_tz(tz_name: str) -> datetime:
    tz = pytz.timezone(tz_name)
    return datetime.now(tz)

def format_time(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S")

def format_date(dt: datetime) -> str:
    return dt.strftime("%A, %d %B %Y")

def build_times_dict(timezones):
    out = {}
    for label, tz in timezones.items():
        try:
            dt = get_time_for_tz(tz)
            out[label] = {"time": format_time(dt), "date": format_date(dt)}
        except Exception as e:
            out[label] = {"time": "Invalid TZ", "date": str(e)}
    return out

# --- Alarm logic ---
ALARMS = []  # list of dicts: {label, timezone, time_str}

def play_beep():
    if not SIMPLEAUDIO_AVAILABLE:
        print("Beep!")
        return
    import numpy as np
    fs = 44100
    f = 880.0
    duration = 0.5
    samples = (np.sin(2 * np.pi * np.arange(fs * duration) * f / fs)).astype(np.float32)
    sa.play_buffer((samples * 32767).astype(np.int16), 1, 2, fs)

def check_alarms():
    triggered = []
    for alarm in ALARMS:
        dt_now = get_time_for_tz(alarm["timezone"])
        current_hm = dt_now.strftime("%H:%M")
        if current_hm == alarm["time_str"]:
            triggered.append(alarm)
    return triggered

# --- Telegram bot ---

def start_telegram_bot(token: str, tracked_timezones):
    if not TELEGRAM_AVAILABLE:
        st.warning("python-telegram-bot not available. Telegram disabled.")
        return None

    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher

    def check_command(update: Update, context: CallbackContext):
        times = build_times_dict(tracked_timezones)
        lines = [f"World Clock — {APP_TITLE}"]
        for label, info in times.items():
            lines.append(f"{label}: {info['time']} ({info['date']})")
        text = "\n".join(lines)
        update.message.reply_text(text)

    dispatcher.add_handler(CommandHandler("check", check_command))

    def polling():
        updater.start_polling()
        updater.idle()

    threading.Thread(target=polling, daemon=True).start()
    return updater

# --- Streamlit UI ---

def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    selection = st.sidebar.multiselect("Select cities to show", options=list(DEFAULT_CITIES.keys()), default=list(DEFAULT_CITIES.keys()))

    custom_label = st.sidebar.text_input("Custom city label")
    custom_tz = st.sidebar.text_input("Custom timezone (e.g. Europe/Berlin)")
    if st.sidebar.button("Add timezone"):
        try:
            pytz.timezone(custom_tz)
            DEFAULT_CITIES[custom_label or custom_tz] = custom_tz
            st.sidebar.success(f"Added {custom_label}")
        except Exception:
            st.sidebar.error("Invalid timezone")

    # Alarm settings
    st.sidebar.header("Alarm settings")
    alarm_city = st.sidebar.selectbox("Select timezone for alarm", options=list(DEFAULT_CITIES.keys()))
    alarm_time = st.sidebar.text_input("Set alarm (HH:MM, 24h format)")
    if st.sidebar.button("Add Alarm") and alarm_time:
        ALARMS.append({"label": alarm_city, "timezone": DEFAULT_CITIES[alarm_city], "time_str": alarm_time})
        st.sidebar.success(f"Alarm set for {alarm_city} at {alarm_time}")

    st.sidebar.write("Active alarms:")
    for a in ALARMS:
        st.sidebar.text(f"{a['label']} @ {a['time_str']}")

    # Telegram
    token = os.getenv("TELEGRAM_TOKEN", "")
    if token and st.sidebar.button("Start Telegram Bot"):
        start_telegram_bot(token, {k: DEFAULT_CITIES[k] for k in selection})

    times = build_times_dict({k: DEFAULT_CITIES[k] for k in selection})

    triggered = check_alarms()
    if triggered:
        for alarm in triggered:
            st.error(f"⏰ Alarm for {alarm['label']} ({alarm['time_str']})!")
            play_beep()

    cols = st.columns(4)
    idx = 0
    for label, info in times.items():
        with cols[idx % 4]:
            st.markdown(f"<div style='padding:12px; border-radius:8px; background:#f5f5f5'>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:28px; font-weight:600'>{label}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:22px'>{info['time']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:12px; color:gray'>{info['date']}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        idx += 1

    if st.button("Refresh"):
        st.experimental_rerun()

if __name__ == '__main__':
    main()
