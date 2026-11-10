#!/usr/bin/env python3
"""Simple TUI file explorer and audio player for course materials."""

import os
import sys
import subprocess
import curses
from pathlib import Path

# Supported audio extensions
AUDIO_EXTS = {'.mp3', '.wav', '.ogg', '.flac', '.m4a'}
# Supported document extensions
DOC_EXTS = {'.pdf'}

class TUIExplorer:
    def __init__(self, start_dir):
        self.start_dir = Path(start_dir).resolve()
        self.current_dir = self.start_dir
        self.cursor = 0
        self.selected_file = None
        
    def get_items(self):
        """Get sorted list of items in current directory."""
        items = []
        try:
            for item in self.current_dir.iterdir():
                if item.name.startswith('.'):
                    continue
                items.append(item)
            # Sort: directories first, then files
            items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            pass
        return items
    
    def run(self, stdscr):
        """Main TUI loop."""
        curses.curs_set(0)  # Hide cursor
        stdscr.keypad(True)
        stdscr.clear()
        
        while True:
            items = self.get_items()
            height, width = stdscr.getmaxyx()
            
            # Draw header
            stdscr.addstr(0, 0, f" TUI Audio Course Player - {self.current_dir}", 
                         curses.A_REVERSE)
            stdscr.addstr(1, 0, " ↑↓ Navigate  → Enter  ← Back  q Quit  p Play ", 
                         curses.A_DIM)
            
            # Draw items
            start_idx = max(0, self.cursor - (height - 4) + 1)
            for idx, item in enumerate(items[start_idx:start_idx + (height - 3)]):
                abs_idx = start_idx + idx
                y = 3 + idx
                if y >= height - 1:
                    break
                
                # Check if this is the selected item
                is_selected = (abs_idx == self.cursor)
                
                # Format item name
                prefix = "📁 " if item.is_dir() else "📄 "
                name = item.name
                if item.is_dir():
                    name += "/"
                
                # Truncate if too long
                display_name = (prefix + name)[:width-2]
                
                # Draw with appropriate attributes
                attr = curses.A_REVERSE if is_selected else 0
                stdscr.addstr(y, 0, display_name.ljust(width), attr)
            
            stdscr.refresh()
            
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
                    else:
                        self.selected_file = selected
                        self._open_file(selected)
            elif key == curses.KEY_LEFT or key == 27:  # Back
                if self.current_dir != self.start_dir:
                    self.current_dir = self.current_dir.parent
                    self.cursor = 0
                else:
                    # At root, ESC to quit
                    if key == 27:
                        break
            elif key == ord('p'):
                # Play selected file
                if items:
                    self.selected_file = items[self.cursor]
                    self._open_file(self.selected_file)
            elif key == ord('q'):
                break
            elif key == ord('h'):
                # Go to home directory
                self.current_dir = self.start_dir
                self.cursor = 0
            
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
        """Play audio file."""
        # Try vlc first
        try:
            subprocess.Popen(['vlc', '--play-and-exit', file_path])
            return
        except FileNotFoundError:
            pass
        
        # Try mpv
        try:
            subprocess.Popen(['mpv', file_path])
            return
        except FileNotFoundError:
            pass
        
        # Try mpg123
        try:
            subprocess.Popen(['mpg123', file_path])
            return
        except FileNotFoundError:
            pass
        
        self._show_message("No audio player found (install vlc or mpv)")
    
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
