# TUI Audio Course Player

A simple terminal-based file explorer and audio player for course materials.

## Features

- Navigate through directories with arrow keys
- Open and play audio files (MP3, WAV, OGG, etc.)
- Open PDF documents
- Keyboard shortcuts for easy navigation

## Usage

```bash
python3 tui_audio_course_player.py
```

## Controls

| Key | Action |
|-----|--------|
| ↑ / ↓ | Navigate up/down |
| → / Enter | Enter directory or open file |
| ← / ESC | Go back to parent directory |
| p | Play selected audio file |
| h | Go to home directory |
| q | Quit |

## Requirements

- Python 3
- curses (standard library)
- VLC media player (or mpv, mpg123)
- PDF viewer (evince, okular, xpdf, zathura, or xdg-open)

## Installation

The script uses standard Python libraries. It will automatically try to use:
1. VLC (recommended)
2. mpv
3. mpg123
4. xdg-open

For best results, install VLC:
```bash
# Ubuntu/Debian
sudo apt install vlc

# Fedora
sudo dnf install vlc

# Arch
sudo pacman -S vlc
```

## Notes

- Audio files will play in the background
- PDF files will open in your default viewer
- The player starts in the directory where the script is located
- Navigation is similar to file managers like ranger or nnn

## Customization

Edit the `AUDIO_EXTS` and `DOC_EXTS` sets in the script to add support for more file types.

## Directory Structure Recommendation

For optimal organization, save audio files under the root directory divided into folders by course, level, or module, for example:

```
Course-1/
├── audio/
│   ├── module-1/
│   │   ├── lesson-01.mp3
│   │   ├── lesson-02.mp3
│   │   └── ...
│   └── module-2/
│       ├── lesson-01.mp3
│       └── ...
├── course-1.pdf
└── workbook-1.pdf

Course-2/
├── audio/
│   ├── module-1/
│   └── module-2/
├── course-2.pdf
└── workbook-2.pdf
```

This structure allows the player to easily navigate through different courses and modules while maintaining a clean organization.
