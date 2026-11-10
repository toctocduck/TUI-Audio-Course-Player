#!/usr/bin/env python3
"""Simple TUI file explorer and audio player for course materials with waveform visualization and speed control."""

import os
import sys
import subprocess
import curses
import wave
import struct
import math
import threading
import time
from pathlib import Path

try:
    import pygame
    PYGAME_AVAILABLE = True
    try:
        pygame.mixer.init()
    except:
        PYGAME_AVAILABLE = False
except ImportError:
    PYGAME_AVAILABLE = False

# Try to import numpy for waveform processing
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# Try to import pydub for speed control
try:
    from pydub import AudioSegment
    from pydub.playback import play
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

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
        """Load WAV file and extract waveform data."""
        try:
            with wave.open(file_path, 'rb') as wav_file:
                self.sample_rate = wav_file.getframerate()
                self.channels = wav_file.getnchannels()
                n_frames = wav_file.getnframes()
                self.duration = n_frames / self.sample_rate
                
                # Read raw data
                raw_data = wav_file.readframes(n_frames)
                
                # Convert to numpy array or list
                if NUMPY_AVAILABLE:
                    # Use numpy for efficient processing
                    if wav_file.getsampwidth() == 2:  # 16-bit
                        dtype = np.int16
                    elif wav_file.getsampwidth() == 4:  # 32-bit
                        dtype = np.int32
                    else:  # 8-bit
                        dtype = np.int8
                    
                    samples = np.frombuffer(raw_data, dtype=dtype)
                    
                    # Convert to mono by averaging channels
                    if self.channels > 1:
                        samples = samples.reshape(-1, self.channels)
                        samples = samples.mean(axis=1)
                    
                    # Normalize to -1.0 to 1.0
                    max_val = np.max(np.abs(samples))
                    if max_val > 0:
                        samples = samples.astype(np.float32) / max_val
                    else:
                        samples = np.zeros_like(samples, dtype=np.float32)
                    
                    self.waveform_data = samples
                else:
                    # Fallback without numpy
                    fmt = '<' + str(n_frames * self.channels) + 'h'  # Assume 16-bit for now
                    samples = list(struct.unpack(fmt, raw_data))
                    
                    # Convert to mono
                    if self.channels > 1:
                        mono_samples = []
                        for i in range(0, len(samples), self.channels):
                            frame_samples = samples[i:i+self.channels]
                            mono_samples.append(sum(frame_samples) / self.channels)
                        samples = mono_samples
                    
                    # Normalize
                    max_val = max(abs(s) for s in samples) if samples else 1
                    if max_val > 0:
                        samples = [s / max_val for s in samples]
                    
                    self.waveform_data = samples
                
            return True
        except Exception as e:
            print(f"Error loading WAV: {e}", file=sys.stderr)
            return False
    
    def load_with_pygame(self, file_path):
        """Load audio file using pygame.sndarray for waveform extraction."""
        if not PYGAME_AVAILABLE:
            return False
            
        try:
            import pygame.sndarray
            
            # Try to load as sound
            sound = pygame.mixer.Sound(file_path)
            
            # Get raw audio data
            if NUMPY_AVAILABLE:
                raw_array = pygame.sndarray.samples(sound)
                
                # Convert to mono if stereo
                if len(raw_array.shape) > 1 and raw_array.shape[1] > 1:
                    raw_array = raw_array.mean(axis=1)
                
                # Normalize
                max_val = np.max(np.abs(raw_array))
                if max_val > 0:
                    raw_array = raw_array.astype(np.float32) / max_val
                
                self.waveform_data = raw_array
                self.sample_rate = 44100  # Default
                self.channels = 1
                self.duration = sound.get_length()
                return True
            else:
                # Without numpy, we can't easily get the array
                self.duration = sound.get_length()
                return True
                
        except Exception as e:
            print(f"Error loading with pygame.sndarray: {e}", file=sys.stderr)
            return False
    
    def load_with_pydub(self, file_path):
        """Load audio file using pydub for waveform extraction."""
        if not PYDUB_AVAILABLE:
            return False
            
        try:
            audio = AudioSegment.from_file(file_path)
            self.duration = len(audio) / 1000.0  # Convert ms to seconds
            self.sample_rate = audio.frame_rate
            self.channels = audio.channels
            
            # Get samples
            samples = np.array(audio.get_array_of_samples())
            
            # Convert to mono
            if self.channels > 1:
                samples = samples.reshape(-1, self.channels)
                samples = samples.mean(axis=1)
            
            # Normalize
            max_val = np.max(np.abs(samples))
            if max_val > 0:
                samples = samples.astype(np.float32) / max_val
            
            self.waveform_data = samples
            return True
        except Exception as e:
            print(f"Error loading with pydub: {e}", file=sys.stderr)
            return False
    
    def load_audio(self, file_path):
        """Load audio file and extract waveform data."""
        self.waveform_data = None
        self.duration = 0
        
        # Try pydub first (handles more formats)
        if PYDUB_AVAILABLE:
            if self.load_with_pydub(file_path):
                return True
        
        # Try WAV
        if file_path.lower().endswith('.wav'):
            if self.load_wav(file_path):
                return True
        
        # Try with pygame.sndarray
        if self.load_with_pygame(file_path):
            return True
        
        # Fallback: create dummy waveform
        if PYGAME_AVAILABLE:
            try:
                sound = pygame.mixer.Sound(file_path)
                self.duration = sound.get_length()
                # Create a simple sine wave representation
                num_samples = 1000
                self.waveform_data = [0.5 * math.sin(2 * math.pi * i / num_samples * 5) for i in range(num_samples)]
                self.sample_rate = 44100
                return True
            except:
                pass
        
        return False
    
    def get_waveform_segment(self, width, start_time=0, end_time=None):
        """Get waveform data for a segment, resampled to fit the given width."""
        if self.waveform_data is None or (hasattr(self.waveform_data, '__len__') and len(self.waveform_data) == 0):
            return [0.0] * width
        
        if end_time is None:
            end_time = self.duration
        
        # Calculate sample indices for the time range
        start_idx = int(start_time * self.sample_rate)
        end_idx = min(int(end_time * self.sample_rate), len(self.waveform_data))
        
        if start_idx >= end_idx or start_idx >= len(self.waveform_data):
            return [0.0] * width
        
        # Get the segment
        segment = self.waveform_data[start_idx:end_idx]
        
        if NUMPY_AVAILABLE:
            if len(segment) == 0:
                return [0.0] * width
            
            # Resample to width points
            indices = np.linspace(0, len(segment) - 1, width, dtype=np.float32)
            resampled = np.interp(indices, np.arange(len(segment)), segment)
            return resampled.tolist()
        else:
            # Simple resampling without numpy
            if len(segment) <= width:
                # Upsample
                result = []
                for i in range(width):
                    idx = i * (len(segment) - 1) / max(width - 1, 1)
                    result.append(segment[min(int(idx), len(segment) - 1)])
                return result
            else:
                # Downsample
                result = []
                for i in range(width):
                    start = int(i * len(segment) / width)
                    end = int((i + 1) * len(segment) / width)
                    segment_slice = segment[start:end]
                    if segment_slice:
                        result.append(sum(segment_slice) / len(segment_slice))
                    else:
                        result.append(0.0)
                return result
    
    def get_rms_values(self, width, window_size=100):
        """Get RMS values for the waveform for better visualization."""
        if self.waveform_data is None or (hasattr(self.waveform_data, '__len__') and len(self.waveform_data) == 0):
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
                rms = np.sqrt(np.mean(np.array(segment)**2))
            else:
                squares = [s**2 for s in segment]
                mean_sq = sum(squares) / len(squares) if squares else 0
                rms = math.sqrt(mean_sq)
            
            rms_values.append(rms)
        
        return rms_values


class AudioPlayer:
    """Class to handle audio playback with speed control."""
    
    def __init__(self, explorer):
        self.explorer = explorer
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.current_position = 0.0
        self.duration = 0.0
        self.speed = 1.0
        self.playback_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.start_time = 0
        self.base_duration = 0.0
        
    def play(self, file_path):
        """Start playing audio file."""
        self.stop()
        self.current_file = file_path
        self.is_playing = True
        self.is_paused = False
        self.current_position = 0.0
        self.start_time = time.time()
        self.stop_event.clear()
        
        # Try to use pygame for normal speed
        if self.speed == 1.0 and PYGAME_AVAILABLE:
            self._play_with_pygame(file_path)
        else:
            # Use pydub for speed control
            self._play_with_pydub(file_path)
    
    def _play_with_pygame(self, file_path):
        """Play audio using pygame."""
        try:
            sound = pygame.mixer.Sound(file_path)
            self.duration = sound.get_length()
            self.base_duration = self.duration
            sound.play()
            
            # Start position update thread
            self.playback_thread = threading.Thread(target=self._update_position_pygame, args=(sound,))
            self.playback_thread.daemon = True
            self.playback_thread.start()
        except Exception as e:
            print(f"Error playing with pygame: {e}", file=sys.stderr)
            self.is_playing = False
    
    def _play_with_pydub(self, file_path):
        """Play audio using pydub with speed control."""
        if not PYDUB_AVAILABLE:
            print("pydub not available for speed control. Install with: pip install pydub ffmpeg-python", file=sys.stderr)
            self._play_with_pygame(file_path)
            return
        
        try:
            audio = AudioSegment.from_file(file_path)
            self.base_duration = len(audio) / 1000.0  # Convert ms to seconds
            self.duration = self.base_duration / self.speed
            
            # Adjust speed
            if self.speed != 1.0:
                audio = audio.speedup(playback_speed=self.speed)
            
            self.playback_thread = threading.Thread(target=self._play_pydub_thread, args=(audio,))
            self.playback_thread.daemon = True
            self.playback_thread.start()
        except Exception as e:
            print(f"Error playing with pydub: {e}", file=sys.stderr)
            self.is_playing = False
    
    def _play_pydub_thread(self, audio):
        """Thread function to play audio with pydub."""
        try:
            play(audio)
        except Exception as e:
            print(f"Playback error: {e}", file=sys.stderr)
        finally:
            self.is_playing = False
            self.is_paused = False
    
    def _update_position_pygame(self, sound):
        """Update current position based on pygame playback."""
        while self.is_playing and not self.stop_event.is_set():
            if not self.is_paused:
                # Get position from pygame
                try:
                    pos_ms = pygame.mixer.music.get_pos()
                    if pos_ms >= 0:
                        self.current_position = pos_ms / 1000.0
                    else:
                        # If get_pos returns -1, use elapsed time
                        self.current_position = (time.time() - self.start_time) * self.speed
                except:
                    self.current_position = (time.time() - self.start_time) * self.speed
                
                # Check if finished
                if self.current_position >= self.duration:
                    self.is_playing = False
                    self.current_position = self.duration
                    break
            
            time.sleep(0.1)
    
    def stop(self):
        """Stop playback."""
        self.stop_event.set()
        
        if PYGAME_AVAILABLE:
            pygame.mixer.music.stop()
        
        self.is_playing = False
        self.is_paused = False
        self.current_position = 0.0
        
        if self.playback_thread and self.playback_thread.is_alive():
            # Wait a bit for thread to finish
            time.sleep(0.2)
    
    def pause(self):
        """Pause playback."""
        if not self.is_playing:
            return
            
        self.is_paused = not self.is_paused
        
        if PYGAME_AVAILABLE:
            if self.is_paused:
                pygame.mixer.music.pause()
            else:
                pygame.mixer.music.unpause()
    
    def set_speed(self, speed):
        """Set playback speed (0.5 to 2.0)."""
        self.speed = max(0.1, min(2.0, speed))
        
        # If playing, restart with new speed
        if self.is_playing and self.current_file:
            # Remember current position
            relative_pos = self.current_position / max(self.duration, 0.001)
            self.play(self.current_file)
            # Seek to relative position (approximate)
            if self.duration > 0:
                self.current_position = relative_pos * self.duration
    
    def get_speed(self):
        """Get current playback speed."""
        return self.speed
    
    def get_duration(self):
        """Get audio duration in seconds."""
        return self.duration
    
    def get_position(self):
        """Get current playback position in seconds."""
        return self.current_position


class TUIExplorer:
    def __init__(self, start_dir):
        self.start_dir = Path(start_dir).resolve()
        self.current_dir = self.start_dir
        self.cursor = 0
        self.selected_file = None
        self.needs_clear = True  # Flag to indicate screen needs clearing
        
        # Audio player with speed control
        self.player = AudioPlayer(self)
        
        # Waveform visualization
        self.waveform = AudioWaveform()
        self.show_waveform = True
        self.waveform_height = 10  # Lines for waveform display
        
        # Progress bar height
        self.progress_height = 2  # Lines for progress bar
        
        # Available speeds
        self.speed_options = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        self.speed_index = 2  # Default to 1.0x
        
    def get_items(self):
        """Get sorted list of items in current directory."""
        items = []
        try:
            # Ensure current_dir is a Path object
            current_path = Path(self.current_dir) if not isinstance(self.current_dir, Path) else self.current_dir
            for item in current_path.iterdir():
                if item.name.startswith('.'):
                    continue
                items.append(item)
            # Sort: directories first, then files
            items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            pass
        return items
    
    def load_waveform_for_file(self, file_path):
        """Load waveform data for the given audio file."""
        try:
            if self.waveform.load_audio(str(file_path)):
                # Update player duration from waveform
                if self.waveform.duration > 0:
                    self.player.base_duration = self.waveform.duration
                    self.player.duration = self.waveform.duration / self.player.speed
                return True
        except Exception as e:
            print(f"Error loading waveform: {e}", file=sys.stderr)
        
        return False
    
    def run(self, stdscr):
        """Main TUI loop."""
        curses.curs_set(0)  # Hide cursor
        stdscr.keypad(True)
        stdscr.clear()
        
        # Enable colors if available
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            # Define color pairs
            curses.init_pair(1, curses.COLOR_CYAN, -1)  # Selected item
            curses.init_pair(2, curses.COLOR_GREEN, -1)  # Playing indicator
            curses.init_pair(3, curses.COLOR_YELLOW, -1)  # Waveform
            curses.init_pair(4, curses.COLOR_RED, -1)  # Playback position
            curses.init_pair(5, curses.COLOR_MAGENTA, -1)  # Directory
            curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Status bar
            curses.init_pair(7, curses.COLOR_BLUE, -1)  # Progress bar
            curses.init_pair(8, curses.COLOR_WHITE, -1)  # Speed indicator
        
        last_update_time = time.time()
        
        while True:
            # Clear screen if needed (after directory change)
            if self.needs_clear:
                stdscr.clear()
                self.needs_clear = False
            
            items = self.get_items()
            height, width = stdscr.getmaxyx()
            
            # Calculate available space for file list
            available_height = height
            
            if self.show_waveform and height > 15:
                available_height -= self.waveform_height
            
            # Reserve space for progress bar
            available_height -= self.progress_height
            
            file_list_height = available_height - 3  # -3 for headers
            
            # Draw header
            header_text = f" TUI Audio Course Player - {self.current_dir.name if self.current_dir != self.start_dir else self.current_dir.name}"
            stdscr.addstr(0, 0, header_text[:width-1].ljust(width), curses.A_REVERSE)
            
            # Draw subheader with controls
            speed_str = f"Speed: {self.player.get_speed():.2f}x" if self.player.get_speed() != 1.0 else "Speed: 1.0x"
            controls = f"↑↓ Navigate  → Enter  ← Back  p Play  s Stop  SPACE Pause  +/= Speed+  - Speed-  w Toggle Waveform  q Quit"
            stdscr.addstr(1, 0, controls[:width-1].ljust(width), curses.A_DIM)
            
            # Draw file list
            start_idx = max(0, self.cursor - (file_list_height - 1))
            for idx, item in enumerate(items[start_idx:start_idx + file_list_height]):
                abs_idx = start_idx + idx
                y = 3 + idx
                if y >= height - 1:
                    break
                
                # Check if this is the selected item
                is_selected = (abs_idx == self.cursor)
                is_playing_file = (self.player.is_playing and 
                                   self.selected_file and 
                                   self.selected_file == items[abs_idx])
                
                # Format item name
                prefix = "📁 " if item.is_dir() else "📄 "
                name = item.name
                if item.is_dir():
                    name += "/"
                
                # Truncate if too long
                display_name = (prefix + name)[:width-4]
                
                # Draw with appropriate attributes
                attr = 0
                if is_selected:
                    attr = curses.A_REVERSE | curses.color_pair(1)
                elif is_playing_file:
                    attr = curses.color_pair(2)
                elif item.is_dir():
                    attr = curses.color_pair(5)
                
                stdscr.addstr(y, 0, display_name.ljust(width), attr)
            
            # Draw waveform if enabled
            waveform_start_y = 3 + file_list_height
            if self.show_waveform and height > 15:
                self._draw_waveform(stdscr, width, height, waveform_start_y)
            
            # Draw progress bar
            progress_start_y = height - self.progress_height
            if progress_start_y > 0:
                self._draw_progress_bar(stdscr, width, progress_start_y)
            
            # Draw status bar above progress bar
            if progress_start_y > 1:
                status_line = progress_start_y - 1
                self._draw_status_bar(stdscr, width, status_line)
            
            stdscr.refresh()
            
            # Update playback position
            current_time = time.time()
            if current_time - last_update_time > 0.1:
                last_update_time = current_time
                if self.player.is_playing:
                    # Update position for pygame playback
                    if self.player.speed == 1.0 and PYGAME_AVAILABLE:
                        try:
                            pos_ms = pygame.mixer.music.get_pos()
                            if pos_ms >= 0:
                                self.player.current_position = pos_ms / 1000.0
                        except:
                            pass
                    
                    # Check if finished
                    if self.player.current_position >= self.player.duration:
                        self.player.is_playing = False
                        self.player.current_position = self.player.duration
            
            # Get user input
            key = stdscr.getch()
            
            if key == curses.KEY_UP:
                self.cursor = max(0, self.cursor - 1)
            elif key == curses.KEY_DOWN:
                self.cursor = min(len(items) - 1, self.cursor + 1)
            elif key == curses.KEY_ENTER or key == 10:
                # Enter directory or select file
                if items:
                    selected = items[self.cursor]
                    if selected.is_dir():
                        self.current_dir = selected
                        self.cursor = 0
                        # Reset waveform when entering new directory
                        self.waveform.waveform_data = None
                        self.needs_clear = True
                    else:
                        self.selected_file = selected
                        self._open_file(selected)
                        # Load waveform for audio files
                        if selected.suffix.lower() in AUDIO_EXTS:
                            self.load_waveform_for_file(selected)
            elif key == curses.KEY_LEFT or key == 27:  # Back
                if self.current_dir != self.start_dir:
                    self.current_dir = self.current_dir.parent
                    self.cursor = 0
                    # Reset waveform when going back
                    self.waveform.waveform_data = None
                    self.needs_clear = True
                else:
                    # At root, ESC to quit
                    if key == 27:
                        break
            elif key == ord('p'):
                # Play selected file
                if items:
                    self.selected_file = items[self.cursor]
                    self._open_file(self.selected_file)
                    # Load waveform for audio files
                    if self.selected_file.suffix.lower() in AUDIO_EXTS:
                        self.load_waveform_for_file(self.selected_file)
            elif key == ord('s'):
                # Stop playback
                self.player.stop()
            elif key == ord(' '):
                # Pause/Resume playback
                self.player.pause()
            elif key == ord('+') or key == ord('='):
                # Increase speed
                self.speed_index = min(len(self.speed_options) - 1, self.speed_index + 1)
                self.player.set_speed(self.speed_options[self.speed_index])
            elif key == ord('-') or key == ord('_'):
                # Decrease speed
                self.speed_index = max(0, self.speed_index - 1)
                self.player.set_speed(self.speed_options[self.speed_index])
            elif key == ord('w'):
                # Toggle waveform display
                self.show_waveform = not self.show_waveform
            elif key == ord('q'):
                self.player.stop()
                break
            elif key == ord('h'):
                # Go to home directory
                self.current_dir = self.start_dir
                self.cursor = 0
                self.waveform.waveform_data = None
                self.needs_clear = True
            
    def _draw_waveform(self, stdscr, width, height, start_y):
        """Draw the waveform visualization."""
        waveform_height = self.waveform_height
        
        if width < 10 or waveform_height < 3:
            return
        
        # Draw separator line
        if start_y < height:
            stdscr.addstr(start_y, 0, "─" * width, curses.A_DIM)
        
        # Draw waveform title
        if start_y + 1 < height:
            title = " Waveform Visualization "
            stdscr.addstr(start_y + 1, 0, title[:width].ljust(width), 
                         curses.color_pair(3) if curses.has_colors() else curses.A_BOLD)
        
        # Draw waveform area
        waveform_y = start_y + 2
        available_height = min(waveform_height - 2, height - waveform_y - 1)
        
        if self.waveform.waveform_data is not None and hasattr(self.waveform.waveform_data, '__len__') and len(self.waveform.waveform_data) > 0:
            # Get RMS values for visualization (better for seeing overall shape)
            rms_values = self.waveform.get_rms_values(width - 4)
            
            # Normalize to display height
            max_rms = max(rms_values) if rms_values and max(rms_values) > 0 else 1
            
            # Draw waveform
            for x in range(min(width - 4, len(rms_values))):
                bar_height = int(rms_values[x] / max_rms * available_height) if max_rms > 0 else 0
                
                # Draw from center line
                center = available_height // 2
                bar_top = center - bar_height // 2
                
                # Draw vertical bar
                for y in range(bar_height):
                    if waveform_y + bar_top + y < height - 1:
                        try:
                            stdscr.addch(waveform_y + bar_top + y, 2 + x, 
                                       '█' if curses.has_colors() else '#',
                                       curses.color_pair(3) if curses.has_colors() else 0)
                        except:
                            pass
            
            # Draw center line
            for x in range(2, width - 2):
                if waveform_y + available_height // 2 < height - 1:
                    stdscr.addch(waveform_y + available_height // 2, x, 
                               '─' if curses.has_colors() else '-',
                               curses.A_DIM)
            
            # Draw playback position indicator
            if self.player.is_playing and self.waveform.duration > 0:
                pos_ratio = self.player.current_position / self.waveform.duration
                pos_x = 2 + int(pos_ratio * (width - 4))
                
                if 0 <= pos_x < width - 2:
                    # Draw vertical line at position
                    for y_offset in range(available_height):
                        if waveform_y + y_offset < height - 1:
                            stdscr.addch(waveform_y + y_offset, pos_x, 
                                       '│', curses.color_pair(4) if curses.has_colors() else curses.A_BOLD)
                    
                    # Draw position marker
                    if waveform_y + available_height // 2 < height - 1:
                        stdscr.addch(waveform_y + available_height // 2, pos_x, 
                                   '▼' if curses.has_colors() else 'v',
                                   curses.color_pair(4) if curses.has_colors() else curses.A_BOLD)
        else:
            # No waveform data - show message
            if waveform_y < height - 1:
                msg = " Select an audio file to see waveform "
                stdscr.addstr(waveform_y, 0, msg[:width].center(width), curses.A_DIM)
        
        # Draw scale markers
        if self.waveform.duration > 0 and start_y + waveform_height < height:
            # Show time markers
            time_markers = []
            if self.waveform.duration >= 60:
                # Minutes
                for minute in range(0, int(self.waveform.duration) + 1, max(1, int(self.waveform.duration) // 10)):
                    time_markers.append(f"{minute}s")
            else:
                # Seconds
                for sec in range(0, int(self.waveform.duration) + 1, max(1, int(self.waveform.duration) // 5)):
                    time_markers.append(f"{sec}s")
            
            # Distribute markers across width
            if time_markers:
                for i, marker in enumerate(time_markers):
                    x_pos = 2 + int(i * (width - 4) / (len(time_markers) - 1))
                    if x_pos < width - len(marker):
                        stdscr.addstr(start_y + waveform_height, x_pos, marker, curses.A_DIM)
    
    def _draw_progress_bar(self, stdscr, width, y):
        """Draw the progress bar."""
        if width < 10:
            return
        
        bar_width = width - 10
        
        # Calculate progress ratio
        if self.player.is_playing and self.player.duration > 0:
            progress = min(1.0, self.player.current_position / self.player.duration)
        elif self.player.base_duration > 0:
            progress = min(1.0, self.player.current_position / self.player.base_duration)
        else:
            progress = 0.0
        
        # Draw progress bar
        filled_width = int(progress * bar_width)
        
        # Draw background
        for x in range(5, width - 5):
            stdscr.addch(y, x, ' ', curses.color_pair(7) if curses.has_colors() else 0)
        
        # Draw filled portion
        for x in range(5, 5 + filled_width):
            if x < width - 5:
                stdscr.addch(y, x, '█' if curses.has_colors() else '#', 
                           curses.color_pair(7) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD)
        
        # Draw borders
        stdscr.addch(y, 4, '[', curses.color_pair(7) if curses.has_colors() else 0)
        stdscr.addch(y, width - 6, ']', curses.color_pair(7) if curses.has_colors() else 0)
        
        # Draw percentage
        percent = int(progress * 100)
        percent_str = f"{percent}%"
        stdscr.addstr(y, width - len(percent_str) - 1, percent_str, 
                     curses.color_pair(8) if curses.has_colors() else curses.A_BOLD)
    
    def _draw_status_bar(self, stdscr, width, y):
        """Draw the status bar with file info and time."""
        if y >= stdscr.getmaxyx()[0]:
            return
        
        status_parts = []
        
        # Current speed
        speed_str = f"Speed: {self.player.get_speed():.2f}x"
        status_parts.append(speed_str)
        
        # File info
        if self.selected_file:
            file_name = self.selected_file.name[:width//3]
            
            if self.player.is_playing:
                time_info = f"Playing: {self._format_time(self.player.current_position)} / {self._format_time(self.player.duration)}" if self.player.duration > 0 else "Playing"
                status_parts.append(time_info)
            elif self.selected_file.suffix.lower() in AUDIO_EXTS:
                if self.player.base_duration > 0:
                    time_info = f"Duration: {self._format_time(self.player.base_duration)}"
                    status_parts.append(time_info)
        
        # Combine status parts
        status_text = " | ".join(status_parts)
        
        stdscr.addstr(y, 0, status_text[:width].ljust(width), 
                     curses.color_pair(6) if curses.has_colors() else curses.A_REVERSE)
    
    def _format_time(self, seconds):
        """Format seconds to MM:SS."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
    
    def _open_file(self, file_path):
        """Open the selected file with appropriate application."""
        if not file_path.exists():
            return
        
        # Check if it's an audio file
        if file_path.suffix.lower() in AUDIO_EXTS:
            self._play_audio(str(file_path))
        elif file_path.suffix.lower() in DOC_EXTS:
            self._open_document(str(file_path))
        else:
            # Try to open with xdg-open
            try:
                subprocess.Popen(['xdg-open', str(file_path)])
            except FileNotFoundError:
                self._show_message("No viewer available")
    
    def _play_audio(self, file_path):
        """Play audio file using the audio player."""
        self.player.play(file_path)
        
        # Update waveform duration from player
        if self.player.duration > 0 and self.waveform.duration <= 0:
            self.waveform.duration = self.player.base_duration
    
    def _stop_audio(self):
        """Stop audio playback."""
        self.player.stop()
    
    def _toggle_pause(self):
        """Toggle pause/resume playback."""
        self.player.pause()
    
    def _open_document(self, file_path):
        """Open document file."""
        # Try xdg-open first
        try:
            subprocess.Popen(['xdg-open', file_path])
            return
        except FileNotFoundError:
            pass
        
        # Try specific PDF viewers
        for viewer in ['evince', 'okular', 'xpdf', 'zathura']:
            try:
                subprocess.Popen([viewer, file_path])
                return
            except FileNotFoundError:
                continue
        
        self._show_message("No PDF viewer found")
    
    def _show_message(self, message):
        """Show a temporary message."""
        # For now, just print to stderr
        print(f"\n{message}", file=sys.stderr)


def main():
    start_dir = os.path.dirname(os.path.abspath(__file__))
    explorer = TUIExplorer(start_dir)
    curses.wrapper(explorer.run)


if __name__ == "__main__":
    main()
