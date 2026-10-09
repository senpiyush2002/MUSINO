"""
Desktop Music Player
A native (non-browser) desktop application built with Tkinter for the UI
and python-vlc (libVLC) for audio playback, seeking and speed control.

Run with:  python music_player.py
Setup instructions are in README.md
"""

import json
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# When packaged into an .exe (PyInstaller), libvlc.dll and its plugins/
# folder are bundled next to the exe (or inside an _internal/ subfolder,
# depending on PyInstaller version). Point python-vlc at whichever one
# actually has the DLL before importing it.
if getattr(sys, "frozen", False):
    _exe_dir = os.path.dirname(sys.executable)
    for _candidate in (_exe_dir, os.path.join(_exe_dir, "_internal")):
        if os.path.exists(os.path.join(_candidate, "libvlc.dll")):
            os.environ["PYTHON_VLC_MODULE_PATH"] = _candidate
            break

try:
    import vlc
except ImportError:
    raise SystemExit(
        "python-vlc is not installed.\n"
        "Run: pip install python-vlc\n"
        "You also need the VLC media player app installed on your system "
        "(see README.md)."
    )

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LIBRARY_FILE = os.path.join(APP_DIR, "library.json")
PLAYLIST_FILE = os.path.join(APP_DIR, "playlist.json")

SPEED_OPTIONS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]


def format_ms(ms):
    if ms is None or ms < 0:
        ms = 0
    total_seconds = int(ms / 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


class Library:
    """Holds every song ever added, plus a play count for each."""

    def __init__(self):
        self.songs = {}  # path -> {"title": str, "play_count": int}
        self.load()

    def load(self):
        if os.path.exists(LIBRARY_FILE):
            try:
                with open(LIBRARY_FILE, "r") as f:
                    self.songs = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.songs = {}

    def save(self):
        try:
            with open(LIBRARY_FILE, "w") as f:
                json.dump(self.songs, f, indent=2)
        except OSError:
            pass

    def add(self, path):
        if path not in self.songs:
            title = os.path.splitext(os.path.basename(path))[0]
            self.songs[path] = {"title": title, "play_count": 0}
            self.save()

    def register_play(self, path):
        if path in self.songs:
            self.songs[path]["play_count"] += 1
            self.save()

    def top_played(self, n=8):
        items = [(p, d) for p, d in self.songs.items() if d["play_count"] > 0]
        items.sort(key=lambda x: x[1]["play_count"], reverse=True)
        return items[:n]

    def title_for(self, path):
        d = self.songs.get(path)
        return d["title"] if d else os.path.basename(path)


class Playlist:
    """The user-built queue (box 4)."""

    def __init__(self):
        self.items = []  # list of paths
        self.load()

    def load(self):
        if os.path.exists(PLAYLIST_FILE):
            try:
                with open(PLAYLIST_FILE, "r") as f:
                    self.items = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.items = []

    def save(self):
        try:
            with open(PLAYLIST_FILE, "w") as f:
                json.dump(self.items, f, indent=2)
        except OSError:
            pass

    def add(self, path):
        self.items.append(path)
        self.save()

    def remove_at(self, index):
        if 0 <= index < len(self.items):
            del self.items[index]
            self.save()

    def move(self, index, delta):
        new_index = index + delta
        if 0 <= new_index < len(self.items):
            self.items[index], self.items[new_index] = (
                self.items[new_index],
                self.items[index],
            )
            self.save()


class MusicPlayerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Music Player")
        self.root.geometry("820x520")
        self.root.minsize(700, 460)

        self.library = Library()
        self.playlist = Playlist()

        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()

        self.current_path = None
        self.current_speed = 1.0
        self.duration_ms = 0
        self.user_is_scrubbing = False
        self.play_counted_for_current = False

        self._build_ui()
        self._refresh_frequent()
        self._refresh_playlist_view()
        self._tick()

    # ---------- UI construction ----------

    def _build_ui(self):
        self.root.columnconfigure(0, weight=3)
        self.root.columnconfigure(1, weight=2)
        self.root.rowconfigure(1, weight=1)


        # Left column: box1 (now playing + scrub) over box2 (controls)
        left = tk.Frame(self.root)
        left.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.rowconfigure(0, weight=3)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        self._build_box1(left)
        self._build_box2(left)

        # Right column: box3 / box4 / box5 stacked
        right = tk.Frame(self.root)
        right.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right.rowconfigure(0, weight=2)
        right.rowconfigure(1, weight=3)
        right.rowconfigure(2, weight=2)
        right.columnconfigure(0, weight=1)

        self._build_box3(right)
        self._build_box4(right)
        self._build_box5(right)

    def _build_box1(self, parent):
        box = tk.LabelFrame(parent, text="Now Playing", padx=10, pady=10)
        box.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)

        self.song_name_var = tk.StringVar(value="No song loaded")
        tk.Label(
            box, textvariable=self.song_name_var,
            font=("Segoe UI", 16, "bold"), anchor="center", justify="center",
            wraplength=380,
        ).grid(row=0, column=0, sticky="nsew")

        scrub_frame = tk.Frame(box)
        scrub_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        scrub_frame.columnconfigure(0, weight=1)

        self.scrub_var = tk.DoubleVar(value=0)
        self.scrub_bar = ttk.Scale(
            scrub_frame, from_=0, to=1000, orient="horizontal",
            variable=self.scrub_var,
            command=self._on_scrub_drag,
        )
        self.scrub_bar.grid(row=0, column=0, sticky="ew")
        self.scrub_bar.bind("<ButtonPress-1>", lambda e: self._set_scrubbing(True))
        self.scrub_bar.bind("<ButtonRelease-1>", self._on_scrub_release)

        time_frame = tk.Frame(box)
        time_frame.grid(row=2, column=0, sticky="ew")
        self.elapsed_var = tk.StringVar(value="00:00")
        self.total_var = tk.StringVar(value="00:00")
        tk.Label(time_frame, textvariable=self.elapsed_var).pack(side="left")
        tk.Label(time_frame, textvariable=self.total_var).pack(side="right")

    def _build_box2(self, parent):
        box = tk.LabelFrame(parent, text="Controls", padx=10, pady=10)
        box.grid(row=1, column=0, sticky="nsew")

        btns = tk.Frame(box)
        btns.pack(fill="x")
        self.play_button = tk.Button(
            btns, text="Play", width=8, command=self.toggle_play
        )
        self.play_button.pack(side="left", padx=4)
        tk.Button(btns, text="Stop", width=8, command=self.stop).pack(
            side="left", padx=4
        )

        vol_frame = tk.Frame(box)
        vol_frame.pack(fill="x", pady=(10, 0))
        tk.Label(vol_frame, text="Volume").pack(side="left")
        self.volume_var = tk.IntVar(value=70)
        vol_scale = ttk.Scale(
            vol_frame, from_=0, to=100, orient="horizontal",
            variable=self.volume_var, command=self._on_volume_change,
        )
        vol_scale.pack(side="left", fill="x", expand=True, padx=8)
        self.player.audio_set_volume(self.volume_var.get())

        speed_frame = tk.Frame(box)
        speed_frame.pack(fill="x", pady=(10, 0))
        tk.Label(speed_frame, text="Speed").pack(side="left")
        self.speed_var = tk.StringVar(value="1.0x")
        speed_menu = ttk.Combobox(
            speed_frame, textvariable=self.speed_var, state="readonly",
            width=6, values=[f"{s}x" for s in SPEED_OPTIONS],
        )
        speed_menu.pack(side="left", padx=8)
        speed_menu.bind("<<ComboboxSelected>>", self._on_speed_change)

    def _build_box3(self, parent):
        box = tk.LabelFrame(parent, text="Frequently Played", padx=8, pady=8)
        box.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)

        self.frequent_list = tk.Listbox(box, activestyle="none")
        self.frequent_list.grid(row=0, column=0, sticky="nsew")
        self.frequent_list.bind("<Double-Button-1>", self._play_selected_frequent)

    def _build_box4(self, parent):
        box = tk.LabelFrame(parent, text="Playlist", padx=8, pady=8)
        box.grid(row=1, column=0, sticky="nsew", pady=(0, 6))
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)

        self.playlist_box = tk.Listbox(box, activestyle="none")
        self.playlist_box.grid(row=0, column=0, sticky="nsew")
        self.playlist_box.bind("<Double-Button-1>", self._play_selected_playlist)

        pl_btns = tk.Frame(box)
        pl_btns.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        tk.Button(pl_btns, text="Up", width=5, command=lambda: self._move_playlist(-1)).pack(side="left")
        tk.Button(pl_btns, text="Down", width=5, command=lambda: self._move_playlist(1)).pack(side="left", padx=4)
        tk.Button(pl_btns, text="Remove", width=7, command=self._remove_from_playlist).pack(side="left")

    def _build_box5(self, parent):
        box = tk.LabelFrame(parent, text="Add a Song", padx=8, pady=8)
        box.grid(row=2, column=0, sticky="nsew")
        tk.Button(
            box, text="Browse for song file...", command=self._browse_for_song
        ).pack(fill="x", pady=4)
        tk.Label(
            box, text="Adds to your playlist and library.",
            font=("Segoe UI", 8), fg="#666",
        ).pack()

    # ---------- Playback actions ----------

    def _load_and_play(self, path):
        if not os.path.exists(path):
            messagebox.showerror("File not found", f"Could not find:\n{path}")
            return
        self.current_path = path
        self.play_counted_for_current = False
        media = self.vlc_instance.media_new(path)
        self.player.set_media(media)
        self.player.play()
        self.player.set_rate(self.current_speed)
        self.song_name_var.set(self.library.title_for(path))
        self.play_button.config(text="Pause")
        self.duration_ms = 0  # will be picked up once VLC parses it

    def toggle_play(self):
        if self.current_path is None:
            messagebox.showinfo("No song", "Add and select a song first.")
            return
        state = self.player.get_state()
        if state == vlc.State.Playing:
            self.player.pause()
            self.play_button.config(text="Play")
        else:
            self.player.play()
            self.player.set_rate(self.current_speed)
            self.play_button.config(text="Pause")

    def stop(self):
        self.player.stop()
        self.play_button.config(text="Play")
        self.scrub_var.set(0)
        self.elapsed_var.set("00:00")

    def _on_volume_change(self, _value):
        self.player.audio_set_volume(self.volume_var.get())

    def _on_speed_change(self, _event):
        value = self.speed_var.get().rstrip("x")
        try:
            self.current_speed = float(value)
            self.player.set_rate(self.current_speed)
        except ValueError:
            pass

    def _set_scrubbing(self, flag):
        self.user_is_scrubbing = True

    def _on_scrub_drag(self, _value):
        pass  # visual only while dragging; real seek happens on release

    def _on_scrub_release(self, _event):
        if self.duration_ms > 0:
            fraction = self.scrub_var.get() / 1000.0
            target_ms = int(fraction * self.duration_ms)
            self.player.set_time(target_ms)
        self.user_is_scrubbing = False

    # ---------- Library / playlist interactions ----------

    def _browse_for_song(self):
        path = filedialog.askopenfilename(
            title="Select a song",
            filetypes=[
                ("Audio files", "*.mp3 *.wav *.flac *.ogg *.m4a *.aac"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.library.add(path)
        self.playlist.add(path)
        self._refresh_playlist_view()
        self._load_and_play(path)

    def _refresh_frequent(self):
        self.frequent_list.delete(0, tk.END)
        top = self.library.top_played()
        if not top:
            self.frequent_list.insert(tk.END, "(play songs to build this list)")
            self._frequent_paths = []
            return
        self._frequent_paths = [p for p, _ in top]
        for path, data in top:
            self.frequent_list.insert(
                tk.END, f"{data['title']}  ({data['play_count']} plays)"
            )

    def _play_selected_frequent(self, _event):
        sel = self.frequent_list.curselection()
        if not sel or not getattr(self, "_frequent_paths", None):
            return
        idx = sel[0]
        if idx < len(self._frequent_paths):
            self._load_and_play(self._frequent_paths[idx])

    def _refresh_playlist_view(self):
        self.playlist_box.delete(0, tk.END)
        for path in self.playlist.items:
            self.playlist_box.insert(tk.END, self.library.title_for(path))

    def _play_selected_playlist(self, _event):
        sel = self.playlist_box.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self.playlist.items):
            self._load_and_play(self.playlist.items[idx])

    def _move_playlist(self, delta):
        sel = self.playlist_box.curselection()
        if not sel:
            return
        idx = sel[0]
        self.playlist.move(idx, delta)
        self._refresh_playlist_view()
        new_idx = max(0, min(len(self.playlist.items) - 1, idx + delta))
        self.playlist_box.selection_set(new_idx)

    def _remove_from_playlist(self):
        sel = self.playlist_box.curselection()
        if not sel:
            return
        self.playlist.remove_at(sel[0])
        self._refresh_playlist_view()

    # ---------- Periodic update loop ----------

    def _tick(self):
        if self.current_path is not None:
            state = self.player.get_state()

            length = self.player.get_length()
            if length and length > 0:
                self.duration_ms = length
                self.total_var.set(format_ms(length))

            current_ms = self.player.get_time()
            if current_ms is not None and current_ms >= 0:
                self.elapsed_var.set(format_ms(current_ms))
                if not self.user_is_scrubbing and self.duration_ms > 0:
                    fraction = current_ms / self.duration_ms
                    self.scrub_var.set(fraction * 1000)

            # Count a play once we're solidly into the track
            if (
                not self.play_counted_for_current
                and current_ms is not None
                and current_ms > 5000
            ):
                self.library.register_play(self.current_path)
                self.play_counted_for_current = True
                self._refresh_frequent()

            if state == vlc.State.Ended:
                self.play_button.config(text="Play")
                self.stop()

        self.root.after(400, self._tick)


def main():
    root = tk.Tk()
    app = MusicPlayerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
