#!/bin/bash
# TUI Audio Course Player launcher.
# Playback requires only mpv. The venv interpreter is preferred because it
# provides numpy/pydub for the waveform visualization; if absent, the player
# still works via the system python3 (waveform disabled for compressed files).
cd "$(dirname "$0")"

if [ -x "$HOME/venv_hsk/bin/python" ]; then
    exec "$HOME/venv_hsk/bin/python" tui_audio_course_player.py "$@"
else
    echo "venv_hsk non trovato: uso python3 di sistema (waveform limitato)" >&2
    exec python3 tui_audio_course_player.py "$@"
fi
