"""
Streamlit World Clock Dashboard + Telegram /check command
File: streamlit_world_clock_bot.py

Features:
- Streamlit dashboard that shows multiple timezones (big main clock + grid of other clocks)
- Choose built-in cities or add custom timezone (IANA tz name) or custom city name
- Optional auto-refresh (uses streamlit-autorefresh if installed) with fallback manual Refresh button
- Telegram bot integration (python-telegram-bot). Handles /check to reply current times for configured zones

How to run:
1) Install dependencies:
   pip install streamlit pytz python-telegram-bot==13.15 tzdata
   # optional auto-refresh dependency:
   pip install streamlit-autorefresh

2) Set TELEGRAM_TOKEN environment variable with your bot token:
   export TELEGRAM_TOKEN="123456:ABC-DEF..."   # linux/mac
   set TELEGRAM_TOKEN=123456:ABC-DEF...         # windows

3) Run streamlit app:
   streamlit run streamlit_world_clock_bot.py

Notes:
- For Telegram the script will start a polling updater in a background thread; ensure the process can run continuously.
- If you wish to disable the Telegram part, set TELEGRAM_TOKEN to empty or run with --no-telegram

"""

import os
import threading
import time
from datetime import datetime
from typing import List, Dict

import pytz
import streamlit as st

# Telegram imports (optional)
try:
    from telegram import Update
    from telegram.ext import Updater, CommandHandler, CallbackContext
    TELEGRAM_AVAILABLE = True
except Exception:
    TELEGRAM_AVAILABLE = False

# --- Configuration ---
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


def build_times_dict(timezones: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    out = {}
    for label, tz in timezones.items():
        try:
            dt = get_time_for_tz(tz)
            out[label] = {"time": format_time(dt), "date": format_date(dt), "iso": dt.isoformat()}
        except Exception as e:
            out[label] = {"time": "Invalid TZ", "date": str(e), "iso": ""}
    return out

# --- Telegram bot: command handlers ---

def start_telegram_bot(token: str, tracked_timezones: Dict[str, str]):
    if not TELEGRAM_AVAILABLE:
        st.warning("python-telegram-bot not available. Telegram features disabled.")
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

    def start_cmd(update: Update, context: CallbackContext):
        update.message.reply_text("World Clock Bot active. Use /check to get the current times.")

    dispatcher.add_handler(CommandHandler("check", check_command))
    dispatcher.add_handler(CommandHandler("start", start_cmd))

    # run polling in background thread so Streamlit UI remains responsive
    def polling():
        updater.start_polling()
        updater.idle()

    t = threading.Thread(target=polling, daemon=True)
    t.start()
    return updater

# --- Streamlit UI ---

def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    # Sidebar controls
    st.sidebar.header("Settings")

    # Choose which cities/timezones to show
    available = list(DEFAULT_CITIES.keys())
    default_selection = list(DEFAULT_CITIES.keys())
    selection = st.sidebar.multiselect("Select cities to show", options=available, default=default_selection)

    # Add custom timezone entries
    st.sidebar.markdown("---")
    custom_label = st.sidebar.text_input("Custom city label (optional)")
    custom_tz = st.sidebar.text_input("Custom IANA timezone (e.g. Europe/Berlin)")
    add_btn = st.sidebar.button("Add custom timezone")

    # Auto-refresh option
    st.sidebar.markdown("---")
    st.sidebar.write("Auto-refresh options")
    auto_refresh_enabled = st.sidebar.checkbox("Enable auto-refresh (uses streamlit-autorefresh if available)", value=True)
    refresh_seconds = st.sidebar.number_input("Refresh every (seconds)", min_value=1, max_value=3600, value=1)

    # Telegram config
    st.sidebar.markdown("---")
    st.sidebar.header("Telegram integration")
    token_env = os.getenv("TELEGRAM_TOKEN", "")
    token = st.sidebar.text_input("Telegram Bot Token", value=token_env, type="password")
    start_telegram = st.sidebar.button("Start/Restart Telegram bot")
    no_telegram = st.sidebar.checkbox("Disable Telegram features", value=(token == ""))

    # allow adding custom timezone
    if add_btn and custom_tz.strip() != "":
        try:
            pytz.timezone(custom_tz.strip())
            key = custom_label.strip() or custom_tz.strip()
            DEFAULT_CITIES[key] = custom_tz.strip()
            st.sidebar.success(f"Added {key} -> {custom_tz}")
        except Exception:
            st.sidebar.error("Invalid timezone. Use IANA timezone names (e.g. Europe/Berlin)")

    # Build timezones to display
    timezones_to_display = {k: DEFAULT_CITIES[k] for k in selection}

    # Telegram start
    if start_telegram and not no_telegram:
        if token.strip() == "":
            st.sidebar.error("Provide TELEGRAM_TOKEN to start the bot.")
        else:
            st.sidebar.info("Starting Telegram bot (polling)...")
            start_telegram_bot(token.strip(), timezones_to_display)

    # Optionally start automatically if TELEGRAM_TOKEN env var exists and not disabled
    if token_env and not no_telegram and token.strip() == "":
        # start with env token
        token = token_env
        start_telegram_bot(token, timezones_to_display)

    # Build times
    times = build_times_dict(timezones_to_display)

    # Attempt to auto-refresh using streamlit-autorefresh if installed
    did_autorefresh = False
    if auto_refresh_enabled:
        try:
            # streamlit-autorefresh is an optional package that provides st_autorefresh
            from streamlit_autorefresh import st_autorefresh

            st_autorefresh(interval=refresh_seconds * 1000, key="world_clock_autorefresh")
            did_autorefresh = True
        except Exception:
            # package not available; fall back to manual refresh button below
            did_autorefresh = False

    # Layout: big clock + grid
    cols = st.columns([2, 1])
    main_col = cols[0]
    side_col = cols[1]

    # Show big clock for the first selected city (or UTC fallback)
    if len(times) > 0:
        main_label = list(times.keys())[0]
        main_info = times[main_label]
    else:
        main_label = "UTC"
        main_info = build_times_dict({"UTC": "UTC"})["UTC"]

    with main_col:
        st.markdown(f"<div style='font-size:140px; font-weight:700; line-height:0.9'>{main_info['time']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:20px; color:gray'>{main_label} — {main_info['date']}</div>", unsafe_allow_html=True)

    # Right column: list current times
    with side_col:
        st.subheader("Current times")
        for label, info in times.items():
            st.markdown(f"**{label}** — {info['time']}  ")

    st.markdown("---")
    st.subheader("All locations")

    # Grid display
    grid_cols = st.columns(4)
    idx = 0
    for label, info in times.items():
        with grid_cols[idx % 4]:
            st.markdown(f"<div style='padding:12px; border-radius:8px; background:#f5f5f5'>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:28px; font-weight:600'>{label}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:22px'>{info['time']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:12px; color:gray'>{info['date']}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        idx += 1

    st.markdown("---")
    # Manual refresh fallback
    if not did_autorefresh:
        if st.button("Refresh"):
            st.experimental_rerun()

    # Expose a quick /check response text box so user can copy-paste or test
    st.info("Telegram command /check will reply with the current times for configured cities when Telegram bot is running.")
    st.text_area("Sample /check response (preview)", value="\n".join([f"{k}: {v['time']} ({v['date']})" for k, v in times.items()]), height=200)


if __name__ == '__main__':
    main()
