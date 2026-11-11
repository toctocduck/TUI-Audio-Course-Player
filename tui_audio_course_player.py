#!/usr/bin/env python3
"""TUI file explorer and audio player for course materials with waveform
visualization and speed control.

Playback backend: mpv via JSON IPC. Requires the mpv binary (apt install mpv).
Speed changes are applied live without restarting the file, and pitch is
preserved. pydub/pygame are no longer needed for playback; numpy/pydub are
still used optionally for the waveform.

Debug mode: run with --debug (or TUI_DEBUG=1) to write tui_player_debug.log
next to this script.
"""

import os
import sys
import subprocess
import socket
import json
import shutil
import curses
import wave
import struct
import math
import threading
import time
import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Debug logging setup
# ---------------------------------------------------------------------------
DEBUG = ('--debug' in sys.argv) or (os.environ.get('TUI_DEBUG') == '1')
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'tui_player_debug.log')

logger = logging.getLogger('tui_player')
if DEBUG:
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
    )
else:
    logger.addHandler(logging.NullHandler())

def log_exc(context):
    if DEBUG:
        logger.exception(context)

# ---------------------------------------------------------------------------
# Optional dependencies (waveform only, playback no longer needs them)
# ---------------------------------------------------------------------------
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

try:
    import pygame
    PYGAME_AVAILABLE = True
    try:
        pygame.mixer.init()
    except Exception:
        PYGAME_AVAILABLE = False
except ImportError:
    PYGAME_AVAILABLE = False

MPV_PATH = shutil.which('mpv')
MPV_AVAILABLE = MPV_PATH is not None

logger.debug(f"numpy available: {NUMPY_AVAILABLE}")
logger.debug(f"pydub available: {PYDUB_AVAILABLE}")
logger.debug(f"pygame available: {PYGAME_AVAILABLE}")
logger.debug(f"mpv binary: {MPV_PATH}")
logger.debug(f"debug mode: {DEBUG}, log file: {LOG_FILE if DEBUG else '(disabled)'}")

# Supported audio extensions
AUDIO_EXTS = {'.mp3', '.wav', '.ogg', '.flac', '.m4a'}
# Supported document extensions
DOC_EXTS = {'.pdf'}


class AudioWaveform:
    """Class to extract and provide waveform data for visualization."""

    def __init__(self):
        self.waveform_data = None
        self.duration = 0
        self.sample_rate = 0
        self.channels = 1

    def load_wav(self, file_path):
        try:
            with wave.open(file_path, 'rb') as wav_file:
                self.sample_rate = wav_file.getframerate()
                self.channels = wav_file.getnchannels()
                n_frames = wav_file.getnframes()
                self.duration = n_frames / self.sample_rate
                raw_data = wav_file.readframes(n_frames)

                if NUMPY_AVAILABLE:
                    if wav_file.getsampwidth() == 2:
                        dtype = np.int16
                    elif wav_file.getsampwidth() == 4:
                        dtype = np.int32
                    else:
                        dtype = np.int8
                    samples = np.frombuffer(raw_data, dtype=dtype)
                    if self.channels > 1:
                        samples = samples.reshape(-1, self.channels)
                        samples = samples.mean(axis=1)
                    max_val = np.max(np.abs(samples))
                    if max_val > 0:
                        samples = samples.astype(np.float32) / max_val
                    else:
                        samples = np.zeros_like(samples, dtype=np.float32)
                    self.waveform_data = samples
                else:
                    fmt = '<' + str(n_frames * self.channels) + 'h'
                    samples = list(struct.unpack(fmt, raw_data))
                    if self.channels > 1:
                        mono = []
                        for i in range(0, len(samples), self.channels):
                            frame = samples[i:i + self.channels]
                            mono.append(sum(frame) / self.channels)
                        samples = mono
                    max_val = max(abs(s) for s in samples) if samples else 1
                    if max_val > 0:
                        samples = [s / max_val for s in samples]
                    self.waveform_data = samples
            return True
        except Exception as e:
            logger.error(f"Error loading WAV {file_path}: {e}")
            log_exc("load_wav traceback")
            return False

    def load_with_pydub(self, file_path):
        if not PYDUB_AVAILABLE or not NUMPY_AVAILABLE:
            return False
        try:
            audio = AudioSegment.from_file(file_path)
            self.duration = len(audio) / 1000.0
            self.sample_rate = audio.frame_rate
            self.channels = audio.channels
            samples = np.array(audio.get_array_of_samples())
            if self.channels > 1:
                samples = samples.reshape(-1, self.channels)
                samples = samples.mean(axis=1)
            max_val = np.max(np.abs(samples))
            if max_val > 0:
                samples = samples.astype(np.float32) / max_val
            self.waveform_data = samples
            logger.debug(f"pydub waveform loaded: {file_path} dur={self.duration:.2f}s")
            return True
        except Exception as e:
            logger.error(f"Error loading with pydub {file_path}: {e}")
            log_exc("load_with_pydub traceback")
            return False

    def load_audio(self, file_path):
        self.waveform_data = None
        self.duration = 0
        logger.debug(f"load_audio: {file_path}")

        if PYDUB_AVAILABLE and NUMPY_AVAILABLE:
            if self.load_with_pydub(file_path):
                return True

        if file_path.lower().endswith('.wav'):
            if self.load_wav(file_path):
                return True

        # Fallback: ask ffprobe for the duration at least
        try:
            out = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries',
                 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
                 file_path],
                capture_output=True, text=True, timeout=10)
            dur = float(out.stdout.strip())
            self.duration = dur
            self.waveform_data = None
            logger.debug(f"ffprobe duration only: {dur:.2f}s")
            return True
        except Exception as e:
            logger.error(f"ffprobe failed: {e}")
        return False

    def get_rms_values(self, width, window_size=100):
        if self.waveform_data is None or len(self.waveform_data) == 0:
            return [0.0] * width
        samples = self.waveform_data
        segment_length = max(1, len(samples) // width)
        rms_values = []
        for i in range(width):
            start = i * segment_length
            end = min((i + 1) * segment_length, len(samples))
            if start >= len(samples):
                rms_values.append(0.0)
                continue
            segment = samples[start:end]
            if NUMPY_AVAILABLE:
                rms = float(np.sqrt(np.mean(np.array(segment) ** 2)))
            else:
                squares = [s ** 2 for s in segment]
                mean_sq = sum(squares) / len(squares) if squares else 0
                rms = math.sqrt(mean_sq)
            rms_values.append(rms)
        return rms_values


class MpvPlayer:
    """Audio playback via mpv JSON IPC.

    Speed changes are applied live (set_property speed): no restart,
    no pitch change. Pause and stop are real.
    """

    def __init__(self):
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.current_position = 0.0
        self.duration = 0.0
        self.base_duration = 0.0
        self.speed = 1.0

        self._proc = None
        self._sock = None
        self._socket_path = f"/tmp/tui_player_mpv_{os.getpid()}.sock"
        self._lock = threading.Lock()
        self._req_id = 0
        self._responses = {}
        self._resp_events = {}
        self._end_event = threading.Event()
        self._poll_thread = None

    # -- low-level IPC ----------------------------------------------------
    def _send(self, command, wait=True, timeout=1.0):
        if self._sock is None:
            return None
        with self._lock:
            self._req_id += 1
            rid = self._req_id
            ev = threading.Event()
            self._resp_events[rid] = ev
        try:
            self._sock.sendall(
                (json.dumps({"command": command, "request_id": rid}) + "\n").encode())
        except OSError as e:
            logger.error(f"IPC send failed: {e}")
            return None
        if not wait:
            return None
        if not ev.wait(timeout):
            logger.warning(f"IPC timeout for {command}")
            return None
        resp = self._responses.pop(rid, None)
        if resp is None or resp.get("error") != "success":
            logger.warning(f"IPC error for {command}: {resp}")
            return None
        return resp.get("data")

    def _reader(self):
        buf = b""
        try:
            while self._sock is not None:
                data = self._sock.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    if "event" in msg:
                        if msg.get("event") in ("end-file", "idle"):
                            self._end_event.set()
                        continue
                    rid = msg.get("request_id")
                    if rid is not None:
                        self._responses[rid] = msg
                        ev = self._resp_events.pop(rid, None)
                        if ev:
                            ev.set()
        except OSError:
            pass
        logger.debug("IPC reader thread exited")

    # -- public API -------------------------------------------------------
    def play(self, file_path):
        logger.info(f"play requested: {file_path} speed={self.speed}")
        self.stop()
        if not MPV_AVAILABLE:
            logger.error("mpv not found: cannot play")
            return False
        self.current_file = file_path
        self.is_playing = True
        self.is_paused = False
        self.current_position = 0.0
        self._end_event.clear()

        args = [MPV_PATH, '--no-video', '--no-terminal', '--really-quiet',
                '--no-osd-bar', '--audio-pitch-correction=yes',
                f'--input-ipc-server={self._socket_path}',
                f'--speed={self.speed}', str(file_path)]
        logger.debug(f"spawning mpv: {' '.join(args)}")
        try:
            self._proc = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.error(f"mpv spawn failed: {e}")
            self.is_playing = False
            return False

        if not self._connect():
            self.is_playing = False
            return False

        self._poll_thread = threading.Thread(target=self._poll, daemon=True)
        self._poll_thread.start()
        return True

    def _connect(self, timeout=8.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._proc and self._proc.poll() is not None:
                logger.error("mpv exited immediately (bad file or audio device?)")
                return False
            if os.path.exists(self._socket_path):
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.connect(self._socket_path)
                    self._sock = s
                    t = threading.Thread(target=self._reader, daemon=True)
                    t.start()
                    logger.debug("connected to mpv IPC socket")
                    return True
                except OSError:
                    time.sleep(0.05)
            else:
                time.sleep(0.05)
        logger.error("timed out waiting for mpv IPC socket")
        return False

    def _poll(self):
        while self.is_playing:
            if self._end_event.is_set():
                logger.debug("mpv reported end of file")
                break
            if self._proc and self._proc.poll() is not None:
                break
            pos = self._send(["get_property", "playback-time"])
            dur = self._send(["get_property", "duration"])
            paused = self._send(["get_property", "pause"])
            if pos is not None:
                self.current_position = float(pos)
            if dur is not None and dur > 0:
                self.duration = float(dur)
                self.base_duration = self.duration
            if paused is not None:
                self.is_paused = bool(paused)
            time.sleep(0.1)
        was_playing = self.is_playing
        self.is_playing = False
        if was_playing:
            logger.debug("playback thread loop ended")

    def stop(self):
        logger.info(f"stop requested (was playing={self.is_playing}, "
                    f"pos={self.current_position:.2f}s)")
        if self._sock is not None:
            try:
                self._send(["quit"], wait=False)
            except Exception:
                pass
        if self._proc is not None:
            try:
                self._proc.wait(timeout=1.0)
            except Exception:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=1.0)
                except Exception:
                    self._proc.kill()
        self._sock = None
        self._proc = None
        try:
            os.unlink(self._socket_path)
        except OSError:
            pass
        self.is_playing = False
        self.is_paused = False
        self.current_position = 0.0

    def pause(self):
        if not self.is_playing:
            return
        new_paused = not self.is_paused
        ok = self._send(["set_property", "pause", new_paused])
        if ok is not None:
            self.is_paused = new_paused
            logger.info(f"pause toggled: is_paused={self.is_paused}")

    def set_speed(self, speed):
        self.speed = max(0.1, min(2.0, speed))
        logger.info(f"set_speed -> {self.speed} (playing={self.is_playing})")
        if self.is_playing:
            ok = self._send(["set_property", "speed", self.speed])
            if ok is None:
                logger.warning("live speed change failed")

    def get_speed(self):
        return self.speed

    def get_duration(self):
        return self.duration

    def get_position(self):
        return self.current_position

    def shutdown(self):
        self.stop()


class TUIExplorer:
    def __init__(self, start_dir):
        self.start_dir = Path(start_dir).resolve()
        self.current_dir = self.start_dir
        self.cursor = 0
        self.selected_file = None
        self.needs_clear = True

        self.player = MpvPlayer()

        self.waveform = AudioWaveform()
        self.show_waveform = True
        self.waveform_height = 10
        self.progress_height = 2

        self.speed_options = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        self.speed_index = 2

    def get_items(self):
        items = []
        try:
            current_path = Path(self.current_dir) if not isinstance(self.current_dir, Path) else self.current_dir
            for item in current_path.iterdir():
                if item.name.startswith('.'):
                    continue
                items.append(item)
            items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            pass
        return items

    def load_waveform_for_file(self, file_path):
        try:
            if self.waveform.load_audio(str(file_path)):
                return True
        except Exception as e:
            logger.error(f"Error loading waveform {file_path}: {e}")
        return False

    def run(self, stdscr):
        curses.curs_set(0)
        stdscr.keypad(True)
        stdscr.nodelay(True)
        stdscr.clear()

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_RED, -1)
            curses.init_pair(5, curses.COLOR_MAGENTA, -1)
            curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLUE)
            curses.init_pair(7, curses.COLOR_BLUE, -1)
            curses.init_pair(8, curses.COLOR_WHITE, -1)

        while True:
            if self.needs_clear:
                stdscr.clear()
                self.needs_clear = False

            items = self.get_items()
            height, width = stdscr.getmaxyx()

            available_height = height
            if self.show_waveform and height > 15:
                available_height -= self.waveform_height
            available_height -= self.progress_height
            file_list_height = available_height - 3

            header_text = f" TUI Audio Course Player (mpv) - {self.current_dir.name}"
            stdscr.addstr(0, 0, header_text[:width-1].ljust(width), curses.A_REVERSE)

            controls = ("↑↓ Nav  Enter Play  ← Back  p Replay  s Stop  SPACE Pause  "
                        "+/- Speed  w Wave  q Quit")
            stdscr.addstr(1, 0, controls[:width-1].ljust(width), curses.A_DIM)

            if not MPV_AVAILABLE:
                stdscr.addstr(2, 0, " mpv non trovato: installa con 'sudo apt install mpv'".ljust(width),
                              curses.color_pair(4) if curses.has_colors() else curses.A_BOLD)

            start_idx = max(0, self.cursor - (file_list_height - 1))
            for idx, item in enumerate(items[start_idx:start_idx + file_list_height]):
                abs_idx = start_idx + idx
                y = 3 + idx
                if y >= height - 1:
                    break
                is_selected = (abs_idx == self.cursor)
                is_playing_file = (self.player.is_playing and
                                   self.selected_file and
                                   self.selected_file == items[abs_idx])
                prefix = "📁 " if item.is_dir() else "📄 "
                name = item.name
                if item.is_dir():
                    name += "/"
                display_name = (prefix + name)[:width-4]

                attr = 0
                if is_selected:
                    attr = curses.A_REVERSE | curses.color_pair(1)
                elif is_playing_file:
                    attr = curses.color_pair(2)
                elif item.is_dir():
                    attr = curses.color_pair(5)
                stdscr.addstr(y, 0, display_name.ljust(width), attr)

            waveform_start_y = 3 + file_list_height
            if self.show_waveform and height > 15:
                self._draw_waveform(stdscr, width, height, waveform_start_y)

            progress_start_y = height - self.progress_height
            if progress_start_y > 0:
                self._draw_progress_bar(stdscr, width, progress_start_y)
            if progress_start_y > 1:
                self._draw_status_bar(stdscr, width, progress_start_y - 1)

            stdscr.refresh()

            key = stdscr.getch()

            if key == curses.KEY_UP:
                self.cursor = max(0, self.cursor - 1)
            elif key == curses.KEY_DOWN:
                self.cursor = min(len(items) - 1, self.cursor + 1)
            elif key == curses.KEY_ENTER or key == 10:
                if items:
                    selected = items[self.cursor]
                    if selected.is_dir():
                        self.current_dir = selected
                        self.cursor = 0
                        self.waveform.waveform_data = None
                        self.needs_clear = True
                    else:
                        self.selected_file = selected
                        self._open_file(selected)
                        if selected.suffix.lower() in AUDIO_EXTS:
                            self.load_waveform_for_file(selected)
            elif key == curses.KEY_LEFT or key == 27:
                if self.current_dir != self.start_dir:
                    self.current_dir = self.current_dir.parent
                    self.cursor = 0
                    self.waveform.waveform_data = None
                    self.needs_clear = True
                elif key == 27:
                    break
            elif key == ord('p'):
                if items:
                    self.selected_file = items[self.cursor]
                    if self.selected_file.suffix.lower() in AUDIO_EXTS:
                        self._open_file(self.selected_file)
                        self.load_waveform_for_file(self.selected_file)
            elif key == ord('s'):
                self.player.stop()
            elif key == ord(' '):
                self.player.pause()
            elif key == ord('+') or key == ord('='):
                self.speed_index = min(len(self.speed_options) - 1, self.speed_index + 1)
                self.player.set_speed(self.speed_options[self.speed_index])
            elif key == ord('-') or key == ord('_'):
                self.speed_index = max(0, self.speed_index - 1)
                self.player.set_speed(self.speed_options[self.speed_index])
            elif key == ord('w'):
                self.show_waveform = not self.show_waveform
            elif key == ord('q'):
                break
            elif key == ord('h'):
                self.current_dir = self.start_dir
                self.cursor = 0
                self.waveform.waveform_data = None
                self.needs_clear = True

            time.sleep(0.01)

        self.player.shutdown()

    def _draw_waveform(self, stdscr, width, height, start_y):
        waveform_height = self.waveform_height
        if width < 10 or waveform_height < 3:
            return

        if start_y < height:
            stdscr.addstr(start_y, 0, "─" * width, curses.A_DIM)
        if start_y + 1 < height:
            title = " Waveform Visualization "
            stdscr.addstr(start_y + 1, 0, title[:width].ljust(width),
                          curses.color_pair(3) if curses.has_colors() else curses.A_BOLD)

        waveform_y = start_y + 2
        available_height = min(waveform_height - 2, height - waveform_y - 1)

        if self.waveform.waveform_data is not None and len(self.waveform.waveform_data) > 0:
            num_samples = min(width - 4, 500)
            rms_values = self.waveform.get_rms_values(num_samples)
            max_rms = max(rms_values) if rms_values and max(rms_values) > 0 else 1

            bg_attr = curses.color_pair(3) if curses.has_colors() else curses.A_BOLD
            for y in range(available_height):
                for x in range(2, width - 2):
                    if waveform_y + y < height - 1:
                        try:
                            stdscr.addch(waveform_y + y, x, '█', bg_attr)
                        except curses.error:
                            pass

            for x in range(min(width - 4, len(rms_values))):
                bar_height = int(rms_values[x] / max_rms * available_height) if max_rms > 0 else 0
                center = available_height // 2
                bar_top = center - bar_height // 2
                for y in range(bar_height):
                    actual_y = waveform_y + bar_top + y
                    actual_x = 2 + int(x * (width - 4) / num_samples)
                    if actual_y < height - 1 and actual_x < width - 2:
                        try:
                            stdscr.addch(actual_y, actual_x, ' ')
                        except curses.error:
                            pass

            for x in range(2, width - 2):
                if waveform_y + available_height // 2 < height - 1:
                    try:
                        stdscr.addch(waveform_y + available_height // 2, x, '─')
                    except curses.error:
                        pass

            if self.player.is_playing and self.waveform.duration > 0:
                pos_ratio = self.player.current_position / self.waveform.duration
                pos_x = 2 + int(pos_ratio * (width - 4))
                if 0 <= pos_x < width - 2:
                    for y_offset in range(available_height):
                        if waveform_y + y_offset < height - 1:
                            try:
                                stdscr.addch(waveform_y + y_offset, pos_x, '│',
                                             curses.color_pair(4) if curses.has_colors() else curses.A_BOLD)
                            except curses.error:
                                pass
                    if waveform_y + available_height // 2 < height - 1:
                        try:
                            stdscr.addch(waveform_y + available_height // 2, pos_x, '▼',
                                         curses.color_pair(4) if curses.has_colors() else curses.A_BOLD)
                        except curses.error:
                            pass
        else:
            if waveform_y < height - 1:
                msg = " Select an audio file to see waveform "
                stdscr.addstr(waveform_y, 0, msg[:width].center(width), curses.A_DIM)

        if self.waveform.duration > 0 and start_y + waveform_height < height:
            time_markers = []
            step = max(1, int(self.waveform.duration) // 5)
            for sec in range(0, int(self.waveform.duration) + 1, step):
                time_markers.append(f"{sec}s")
            if time_markers:
                for i, marker in enumerate(time_markers):
                    x_pos = 2 + int(i * (width - 4) / max(1, len(time_markers) - 1))
                    if x_pos < width - len(marker):
                        try:
                            stdscr.addstr(start_y + waveform_height, x_pos, marker, curses.A_DIM)
                        except curses.error:
                            pass

    def _draw_progress_bar(self, stdscr, width, y):
        if width < 10:
            return
        bar_width = width - 10

        if self.player.is_playing and self.player.duration > 0:
            progress = min(1.0, self.player.current_position / self.player.duration)
        elif self.player.base_duration > 0:
            progress = min(1.0, self.player.current_position / self.player.base_duration)
        else:
            progress = 0.0

        filled_width = int(progress * bar_width)
        for x in range(5, width - 5):
            stdscr.addch(y, x, ' ', curses.color_pair(7) if curses.has_colors() else 0)
        for x in range(5, 5 + filled_width):
            if x < width - 5:
                stdscr.addch(y, x, '█',
                             curses.color_pair(7) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD)

        stdscr.addch(y, 4, '[', curses.color_pair(7) if curses.has_colors() else 0)
        stdscr.addch(y, width - 6, ']', curses.color_pair(7) if curses.has_colors() else 0)

        percent = int(progress * 100)
        percent_str = f"{percent}%"
        stdscr.addstr(y, width - len(percent_str) - 1, percent_str,
                     curses.color_pair(8) if curses.has_colors() else curses.A_BOLD)

    def _draw_status_bar(self, stdscr, width, y):
        if y >= stdscr.getmaxyx()[0]:
            return

        status_parts = [f"Speed: {self.player.get_speed():.2f}x"]
        if self.selected_file:
            if self.player.is_playing:
                if self.player.duration > 0:
                    status_parts.append(
                        f"{'Paused' if self.player.is_paused else 'Playing'}: "
                        f"{self._format_time(self.player.current_position)} / "
                        f"{self._format_time(self.player.duration)}")
                else:
                    status_parts.append("Playing")
            elif self.selected_file.suffix.lower() in AUDIO_EXTS and self.player.base_duration > 0:
                status_parts.append(f"Duration: {self._format_time(self.player.base_duration)}")

        status_text = " | ".join(status_parts)
        stdscr.addstr(y, 0, status_text[:width].ljust(width),
                     curses.color_pair(6) if curses.has_colors() else curses.A_REVERSE)

    def _format_time(self, seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    def _open_file(self, file_path):
        if not file_path.exists():
            return
        if file_path.suffix.lower() in AUDIO_EXTS:
            self.player.play(str(file_path))
            if self.player.is_playing and self.player.duration <= 0:
                self.waveform.duration = self.player.duration
        elif file_path.suffix.lower() in DOC_EXTS:
            self._open_document(str(file_path))
        else:
            try:
                subprocess.Popen(['xdg-open', str(file_path)],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL,
                                start_new_session=True)
            except FileNotFoundError:
                logger.info("No viewer available")

    def _open_document(self, file_path):
        try:
            subprocess.Popen(['xdg-open', file_path],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL,
                            start_new_session=True)
            return
        except FileNotFoundError:
            pass
        for viewer in ['evince', 'okular', 'xpdf', 'zathura']:
            try:
                subprocess.Popen([viewer, file_path],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL,
                                start_new_session=True)
                return
            except FileNotFoundError:
                continue
        logger.info("No PDF viewer found")


def main():
    logger.info(f"=== session start, debug={DEBUG}, argv={sys.argv} ===")
    logger.debug(f"python: {sys.version}")
    start_dir = os.path.dirname(os.path.abspath(__file__))
    explorer = TUIExplorer(start_dir)
    curses.wrapper(explorer.run)
    logger.info("=== session end ===")


if __name__ == "__main__":
    main()