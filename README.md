# 🎧 TUI Audio Course Player

**A powerful terminal-based audio player designed for language learners**

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 What is this?

TUI Audio Course Player is a **text-based user interface** application that helps you navigate and play audio files directly in your terminal. It's specifically designed for **language learning**, with features that help you understand accents, intonation, and speech patterns.

### ✨ Key Features

| Feature | Description |
|---------|-------------|
| 📁 **File Explorer** | Navigate through directories with keyboard shortcuts |
| ▶️ **Audio Playback** | Play MP3, WAV, OGG, FLAC, M4A files |
| 📊 **Waveform Visualization** | See the audio waveform to identify accents and stress patterns |
| ⚡ **Speed Control** | Slow down or speed up playback (0.5x to 2.0x) |
| ⏱️ **Progress Bar** | Visual progress indicator with time display |
| 📄 **Document Support** | Open PDF files with your default viewer |

---

## 📸 Screenshot (Conceptual)

```
┌─────────────────────────────────────────────────────────────┐
│  TUI Audio Course Player - /home/user/courses/HSK-3        │
│  ↑↓ Navigate  → Enter  ← Back  p Play  s Stop  +/= +Speed │
├─────────────────────────────────────────────────────────────┤
│  📁 audio/                                                    │
│  📁 documents/                                                │
│  📄 lesson-01.mp3   ★★★                                    │
│  📄 lesson-02.mp3                                            │
│  📄 lesson-03.mp3                                            │
├─────────────────────────────────────────────────────────────┤
│  Waveform Visualization                                      │
│  ██        ██████    ██    ████████  ██                      │
│  ██        ██████    ██    ████████  ██                      │
│  ██████    ██████    ██    ████████  ██                      │
│  ██████    ██████    ██    ████████  ██                      │
│                             ▼                              │
├─────────────────────────────────────────────────────────────┤
│  Speed: 0.75x | Playing: 1:23 / 3:45 | 35%                  │
│  [████████░░░░░░░░░░░░░░] 35%                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Clone or download the repository
git clone https://github.com/your-username/tui-audio-course-player.git
cd tui-audio-course-player

# Install Python packages
pip install pygame numpy

# Optional: For speed control
pip install pydub ffmpeg-python
```

> **Note**: `pydub` requires `ffmpeg` to be installed on your system:
> ```bash
> # Ubuntu/Debian
> sudo apt install ffmpeg
> 
> # Fedora
> sudo dnf install ffmpeg
> 
> # Arch Linux
> sudo pacman -S ffmpeg
> 
> # macOS (with Homebrew)
> brew install ffmpeg
> ```

### 2. Install PDF Viewer (Optional)

For opening PDF documents:

```bash
# Ubuntu/Debian
sudo apt install evince

# Fedora
sudo dnf install evince

# Arch Linux
sudo pacman -S evince
```

### 3. Run the Player

```bash
python3 tui_audio_course_player.py
```

---

## 🎹 Keyboard Shortcuts

### Navigation

| Key | Action |
|-----|--------|
| `↑` / `↓` | Move cursor up/down |
| `→` / `Enter` | Enter directory or play file |
| `←` / `ESC` | Go back to parent directory |
| `h` | Go to home directory |
| `q` | Quit application |

### Audio Controls

| Key | Action |
|-----|--------|
| `p` | Play selected audio file |
| `SPACE` | Pause/Resume playback |
| `s` | Stop playback |
| `+` / `=` | Increase playback speed |
| `-` / `_` | Decrease playback speed |
| `w` | Toggle waveform visualization |

### Speed Presets

The player supports **6 speed presets**:
- 0.5x (half speed)
- 0.75x (three-quarters speed)
- **1.0x (normal speed)**
- 1.25x
- 1.5x
- 2.0x (double speed)

---

## 💡 Use Cases

### 🌍 Language Learning

The **waveform visualization** and **speed control** make this tool perfect for language learners:

1. **Understand Accents**: The waveform helps you visualize stress patterns and intonation
2. **Shadowing Practice**: Slow down audio to practice pronunciation
3. **Listening Comprehension**: Adjust speed to match your understanding level
4. **Transcription**: Use the progress bar to navigate precisely

### 🎓 Course Materials

Organize your audio courses in folders:

```
MyCourses/
├── Chinese/
│   ├── HSK-1/
│   │   ├── audio/
│   │   │   ├── lesson-01.mp3
│   │   │   ├── lesson-02.mp3
│   │   │   └── ...
│   │   └── workbook.pdf
│   └── HSK-2/
│       └── ...
└── English/
    └── ...
```

### 📚 Audiobooks & Podcasts

Navigate through long audio files and control playback speed for better comprehension.

---

## ⚙️ Configuration

### Supported File Types

**Audio Files:**
- `.mp3` - MP3 audio
- `.wav` - WAV audio (best for waveform visualization)
- `.ogg` - OGG Vorbis
- `.flac` - FLAC lossless audio
- `.m4a` - AAC audio

**Documents:**
- `.pdf` - PDF files

### Customization

You can customize supported file types by editing the `AUDIO_EXTS` and `DOC_EXTS` sets in the `tui_audio_course_player.py` file:

```python
AUDIO_EXTS = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.your_format'}
DOC_EXTS = {'.pdf', '.epub', '.your_format'}
```

---

## 🐛 Troubleshooting

### Waveform Not Showing

**Solution:** Install `numpy`:
```bash
pip install numpy
```

**Note:** WAV files work best for waveform visualization. MP3 and other compressed formats may show approximate waveforms.

### Speed Control Not Working

**Solution:** Install `pydub` and `ffmpeg`:
```bash
pip install pydub ffmpeg-python
# And install ffmpeg on your system (see above)
```

Without `pydub`, the player will use pygame's native playback at normal speed (1.0x) only.

### No Audio Playback

**Solution:**
1. Make sure `pygame` is installed: `pip install pygame`
2. Check your system's audio output configuration
3. MP3 playback requires SDL2_mixer with MP3 support

### Colors Not Displaying

**Solution:** Most modern terminals support colors. If you're using an older terminal, try a different one (like `gnome-terminal`, `konsole`, or `alacritty`).

---

## 🔒 Privacy & Security

This application:
- ✅ Does **NOT** collect any user data
- ✅ Does **NOT** require internet access
- ✅ Does **NOT** contain any API keys or secrets
- ✅ Runs **completely offline**

All your files stay on your computer.

---

## 🤖 AI Assistance

> **Developed with the help of Artificial Intelligence**

This project was created with the assistance of AI tools (Mistral Vibe). While the AI provided code suggestions and helped implement features, all code has been:

- ✅ **Reviewed** for security and quality
- ✅ **Tested** for edge cases (non-existent files, empty directories, invalid paths, etc.)
- ✅ **Verified** to work correctly with real audio files
- ✅ **Documented** with clear instructions
- ✅ **Hardened** - No API keys or secrets hardcoded in the source
- ✅ **Protected** - `.gitignore` configured to exclude sensitive files

The AI helped accelerate development, but the final result is a fully functional, safe, and useful application.

---

## 📜 License

This project is open source and available under the **[MIT License](LICENSE)**.

---

## 🙏 Acknowledgments

- **[pygame](https://www.pygame.org/)** - For audio playback
- **[numpy](https://numpy.org/)** - For waveform processing
- **[pydub](https://github.com/jiaaro/pydub)** - For audio speed control
- **[curses](https://docs.python.org/3/library/curses.html)** - For terminal UI

---

## 📞 Support

For questions, issues, or feature requests:

1. Check the [Troubleshooting](#-troubleshooting) section above
2. Open an issue on GitHub
3. Or... just enjoy using the player! 😊

---

<p align="center">
  Made with ❤️ for language learners and audio enthusiasts
</p>
