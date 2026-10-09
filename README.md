# Music Player (desktop app)

A native desktop app — not a web app. It uses Tkinter for the window and
libVLC (via python-vlc) for actual audio playback, which is what gives you
reliable seeking and playback-speed control across MP3, WAV, FLAC, OGG,
M4A and AAC.

## One-time setup

1. **Install VLC media player** (the engine, not the Python package):
   - Windows / Mac: download from https://www.videolan.org/vlc/
   - Linux: `sudo apt install vlc` (or your distro's package manager)

2. **Install the Python binding**:
   ```
   pip install python-vlc
   ```

3. Make sure you're on Python 3.8+. Tkinter ships with Python by default
   on Windows/Mac; on Linux you may need `sudo apt install python3-tk`.

## Run it

```
python music_player.py
```

A window opens. Nothing plays until you add a song.

## How the layout maps to your sketch

| Box | What it is |
|---|---|
| Top bar | App header |
| Box 1 | Song title + scrub bar (drag to seek, shows elapsed/total time) |
| Box 2 | Play/Pause, Stop, Volume slider, Speed dropdown (0.5x–2x) |
| Box 3 | Frequently Played — auto-ranks songs by play count, double-click to play |
| Box 4 | Playlist — your queue; double-click to play, reorder with Up/Down, Remove |
| Box 5 | Add a Song — opens a file browser, adds the song to your library and playlist |

## Data it keeps

Two small JSON files are created next to the script:
- `library.json` — every song you've added, with its play count
- `playlist.json` — your current playlist order

Delete either file to reset that part. Nothing is sent anywhere; it's all
local.

## Building a standalone .exe

Run these on the same Windows machine where VLC is installed and the app
already works with `python music_player.py`.

1. Install the packager:
   ```
   pip install pyinstaller
   ```

2. From the folder containing `music_player.py`, run (one line, adjust the
   VLC path if yours differs):
   ```
   pyinstaller --onedir --windowed --name "MusicPlayer" --add-binary "C:\Program Files\VideoLAN\VLC\libvlc.dll;." --add-binary "C:\Program Files\VideoLAN\VLC\libvlccore.dll;." --add-data "C:\Program Files\VideoLAN\VLC\plugins;plugins" music_player.py
   ```

3. Your app is in `dist\MusicPlayer\`. Run `MusicPlayer.exe` from inside
   that folder.

**Important:** don't send people just the `.exe` file — send the whole
`dist\MusicPlayer` folder (zip it up). The exe depends on the DLLs and
`plugins` folder sitting beside it; it's not truly standalone, and VLC's
licensing also expects its files to travel together with it rather than
be hidden inside a single-file bundle.

Use `--onedir`, not `--onefile`. One-file mode extracts everything to a
temp folder on every launch, which makes libVLC's plugin discovery
unreliable and adds a startup delay on top of the one you already fixed.

## Known limits

- A play only counts toward "Frequently Played" once you've listened past
  5 seconds of it.
- Speed changes apply going forward from when you change them (this is a
  VLC characteristic, not a bug).
- This plays files already on your computer — it doesn't stream or search
  online libraries.
