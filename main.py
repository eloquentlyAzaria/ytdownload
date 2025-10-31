import pytubefix
from pytubefix import YouTube
import customtkinter as ctk
from PIL import Image
from io import BytesIO
from typing import Optional
import ffmpeg
import threading
import functools
import requests
import sys
import os
import re

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# note: for theme files to work, they must be in ./themes/
ctk.set_appearance_mode("dark")

THEME_OPTIONS = {
    "Dark Blue": "dark-blue",
    "Green": "green",
    "Blue": "blue",
    "Autumn": "./themes/autumn.json",
    "Breeze": "./themes/breeze.json",
    "Carrot": "./themes/carrot.json",
    "Cherry": "./themes/cherry.json",
    "Coffee": "./themes/coffee.json",
    "Lavender": "./themes/lavender.json",
    "Marsh": "./themes/marsh.json",
    "Metal": "./themes/metal.json",
    "Midnight": "./themes/midnight.json",
    "Orange": "./themes/orange.json",
    "Patina": "./themes/patina.json",
    "Pink": "./themes/pink.json",
    "Red": "./themes/red.json",
    "Rime": "./themes/rime.json",
    "Rose": "./themes/rose.json",
    "Sky": "./themes/sky.json",
    "Violet": "./themes/violet.json",
    "Yellow": "./themes/yellow.json"
}
THEME_PREF_FILE = "theme_preference.txt"


# reads the saved theme preference
def get_current_theme():
    pref_file_path = resource_path(THEME_PREF_FILE)
    if os.path.exists(pref_file_path):
        with open(pref_file_path, 'r') as f:
            return f.read().strip()
    return list(THEME_OPTIONS.keys())[0]


# saves the theme preference for the next session
def save_theme_preference(theme_name):
    pref_file_path = resource_path(THEME_PREF_FILE)
    with open(pref_file_path, 'w') as f:
        f.write(theme_name)


# applies the theme preference found in the config file on startup
def apply_initial_theme():
    theme_name = get_current_theme()
    theme_setting = THEME_OPTIONS.get(theme_name)

    if theme_setting and theme_setting.endswith(".json"):
        try:
            theme_file_path = resource_path(theme_setting)
            ctk.set_default_color_theme(theme_file_path)
        except Exception:
            ctk.set_default_color_theme("blue")  # fallback
    elif theme_setting:
        ctk.set_default_color_theme(theme_setting)

    return theme_name

def clean_filename(title: str) -> str:
    """Removes invalid characters and shortens long titles for file safety."""
    safe_title = re.sub(r'[^\w\s-]', '', title).strip()
    safe_title = re.sub(r'\s+', ' ', safe_title)
    return safe_title[:100]

class YouTubeDownloaderApp:
    def __init__(self, master):
        self.master = master

        # state variables
        self.selected_video: Optional["pytubefix.streams.Stream"] = None
        self.selected_audio: Optional["pytubefix.streams.Stream"] = None
        self.selected_video_btn = None
        self.selected_audio_btn = None
        self.current_yt_object: Optional[YouTube] = None

        # ctk string vars
        self.filename_var = ctk.StringVar(value="output")
        self.choice_var = ctk.StringVar(value="both")
        self.theme_var = ctk.StringVar(value=get_current_theme())

        # build the initial UI
        self.create_ui()

    def create_ui(self):
        # builds the entire UI, destroying previous widgets if called for theme change

        for widget in self.master.winfo_children():
            widget.destroy()

        self.master.title("YouTube Downloader")
        self.master.geometry("850x750")
        self.master.grid_columnconfigure(0, weight=1)

        input_frame = ctk.CTkFrame(self.master)
        input_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(input_frame, placeholder_text="Enter YouTube URL here...")
        self.url_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")

        fetch_button = ctk.CTkButton(input_frame, text="Fetch Info", command=self.on_fetch, width=120)
        fetch_button.grid(row=0, column=1, padx=(5, 10), pady=10)

        info_frame = ctk.CTkFrame(self.master)
        info_frame.grid(row=1, column=0, pady=10, padx=20, sticky="ew")
        info_frame.grid_columnconfigure(1, weight=1)

        self.thumbnail_label = ctk.CTkLabel(info_frame, text="(Thumbnail)", height=135, width=240)
        self.thumbnail_label.grid(row=0, column=0, rowspan=3, padx=10, pady=10, sticky="n")

        self.title_label = ctk.CTkLabel(info_frame, text="Ready to fetch a URL.", font=("Segoe UI", 16, "bold"), wraplength=550, anchor="w", justify="left")
        self.title_label.grid(row=0, column=1, padx=10, pady=(10, 5), sticky="ew")

        self.status_label = ctk.CTkLabel(info_frame, text="Awaiting link.", font=("Segoe UI", 12), anchor="w")
        self.status_label.grid(row=1, column=1, padx=10, pady=(0, 5), sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(info_frame, orientation="horizontal", height=15)
        self.progress_bar.grid(row=2, column=1, padx=10, pady=(5, 10), sticky="ew")
        self.progress_bar.set(0)

        lists_frame = ctk.CTkFrame(self.master)
        lists_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        lists_frame.grid_columnconfigure((0, 1), weight=1)
        lists_frame.grid_rowconfigure(0, weight=1)
        self.master.grid_rowconfigure(2, weight=1)  # let the stream lists take up space

        self.video_scroll = ctk.CTkScrollableFrame(lists_frame, label_text="Video Streams (MP4/WEBM Sorted by Quality)")
        self.video_scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.audio_scroll = ctk.CTkScrollableFrame(lists_frame, label_text="Audio Streams (M4A/WEBM Sorted by Bitrate)")
        self.audio_scroll.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        control_frame = ctk.CTkFrame(self.master)
        control_frame.grid(row=3, column=0, pady=(10, 20), padx=20, sticky="ew")
        control_frame.grid_columnconfigure(0, weight=1)

        filename_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        filename_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(5, 5))
        filename_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(filename_frame, text="Output Filename:").grid(row=0, column=0, padx=(0, 10), sticky="w")

        filename_entry = ctk.CTkEntry(filename_frame, textvariable=self.filename_var, placeholder_text="Enter custom filename...")
        filename_entry.grid(row=0, column=1, sticky="ew")

        controls_row = ctk.CTkFrame(control_frame, fg_color="transparent")
        controls_row.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(5, 5))
        controls_row.grid_columnconfigure(0, weight=1)
        controls_row.grid_columnconfigure(1, weight=1)
        controls_row.grid_columnconfigure(2, weight=1)

        radio_frame = ctk.CTkFrame(controls_row, fg_color="transparent")
        radio_frame.grid(row=0, column=0, sticky="w")
        ctk.CTkRadioButton(radio_frame, text="Video Only", variable=self.choice_var, value="video").pack(side="left", padx=15)
        ctk.CTkRadioButton(radio_frame, text="Audio Only", variable=self.choice_var, value="audio").pack(side="left", padx=1)
        ctk.CTkRadioButton(radio_frame, text="Both", variable=self.choice_var, value="both").pack(side="left", padx=15)

        self.download_button = ctk.CTkButton(controls_row, text="Download", command=self.on_download, width=150)
        self.download_button.grid(row=0, column=1, padx=10)
        self.download_button.configure(state="disabled")  # disabled by default

        theme_selector_frame = ctk.CTkFrame(controls_row, fg_color="transparent")
        theme_selector_frame.grid(row=0, column=2, sticky="e")

        ctk.CTkLabel(theme_selector_frame, text="Theme:").pack(side="left", padx=5)

        theme_choices = list(THEME_OPTIONS.keys())

        theme_menu = ctk.CTkOptionMenu(
            theme_selector_frame,
            values=theme_choices,
            variable=self.theme_var,
            command=self.change_theme_event
        )
        theme_menu.pack(side="left", padx=5)

    def change_theme_event(self, theme_name):
        # applies the new theme and rebuilds the UI dynamically

        # save state before destruction
        current_url = self.url_entry.get() if hasattr(self, 'url_entry') else ""
        current_filename = self.filename_var.get()
        current_choice = self.choice_var.get()

        # apply the new theme globally
        theme_setting = THEME_OPTIONS.get(theme_name)
        if theme_setting and theme_setting.endswith(".json"):
            try:
                theme_file_path = resource_path(theme_setting)
                ctk.set_default_color_theme(theme_file_path)
            except Exception as e:
                print(f"Failed to load theme {theme_setting}: {e}. Falling back to 'blue'.")
                ctk.set_default_color_theme("blue")
        elif theme_setting:
            ctk.set_default_color_theme(theme_setting)

        # save the user's choice
        save_theme_preference(theme_name)

        # rebuild the entire UI
        self.create_ui()

        # restore state
        self.master.after(0, lambda: self.url_entry.delete(0, 'end'))
        self.master.after(0, lambda: self.url_entry.insert(0, current_url))
        self.filename_var.set(current_filename)
        self.choice_var.set(current_choice)
        self.theme_var.set(theme_name)

    def getvideoinfo(self, link):
        # fetches YouTube metadata and streams
        self.current_yt_object = YouTube(link)
        yt = self.current_yt_object
        title = yt.title
        thumbnail = yt.thumbnail_url
        video = yt.streams.filter(progressive=False, type="video")
        audio = yt.streams.filter(only_audio=True)
        return yt, title, thumbnail, video, audio

    def _sort_streams(self, streams):
        # sorts streams: first by MIME type (MP4 first), then by quality/bitrate (highest first)
        def sort_key(stream):
            mime_type = stream.mime_type
            type_score = 0 if 'mp4' in mime_type else 1  # 0 for MP4/M4A, 1 for WebM

            if hasattr(stream, 'resolution') and stream.resolution:
                quality_score = int(stream.resolution.replace('p', ''))
            elif hasattr(stream, 'abr') and stream.abr:
                quality_score = int(stream.abr.replace('kbps', '').strip())
            else:
                quality_score = 0

            # return tuple: (MIME type score, negative quality score for descending order)
            return (type_score, -quality_score)

        return sorted(streams, key=sort_key)

    def list_video_streams(self, link):
        video_streams = self.getvideoinfo(link)[3]
        return self._sort_streams(video_streams)

    def list_audio_streams(self, link):
        audio_streams = self.getvideoinfo(link)[4]
        return self._sort_streams(audio_streams)

    def on_fetch(self):
        threading.Thread(target=self._fetch_thread, daemon=True).start()

    def _fetch_thread(self):
        # reset state and UI
        self.selected_video = None
        self.selected_audio = None
        self.selected_video_btn = None
        self.selected_audio_btn = None
        self.current_yt_object = None

        link = self.url_entry.get().strip()
        if not link:
            self.master.after(0, lambda: self.title_label.configure(text="Please enter a valid URL."))
            return

        self.master.after(0, lambda: self.title_label.configure(text="Fetching info… please wait."))
        self.master.after(0, lambda: self.status_label.configure(text=""))
        self.master.after(0, lambda: [w.destroy() for w in self.video_scroll.winfo_children()])
        self.master.after(0, lambda: [w.destroy() for w in self.audio_scroll.winfo_children()])
        self.master.after(0, lambda: self.thumbnail_label.configure(image=None, text="(Thumbnail will appear here)"))
        self.master.after(0, lambda: self.progress_bar.set(0))
        self.master.after(0, lambda: self.download_button.configure(state="disabled"))

        try:
            yt, title, thumbnail, video, audio = self.getvideoinfo(link)
            self.master.after(0, lambda: self.title_label.configure(text=title))
            self.master.after(0, lambda: self.download_button.configure(state="normal"))

            # set default filename
            safe_title = clean_filename(title)
            self.master.after(0, lambda t=safe_title: self.filename_var.set(t))

            # thumbnail
            try:
                response = requests.get(thumbnail, timeout=10)
                img = Image.open(BytesIO(response.content)).resize((240, 135))
                photo = ctk.CTkImage(light_image=img, size=(240, 135))
                self.master.after(0, lambda: self._set_thumbnail(photo))
            except Exception as e:
                self.master.after(0, lambda err=e: self.title_label.configure(text=f"Image error: {e}"))

            # add stream buttons
            for stream in self.list_video_streams(link):
                ext = stream.mime_type.split("/")[-1]
                info = f"{stream.resolution or 'N/A'} | {stream.fps or 'N/A'}fps | {ext.upper()}"
                self.master.after(0, lambda s=stream, t=info: self._add_stream_button(self.video_scroll, t, s, "video"))

            for stream in self.list_audio_streams(link):
                ext = stream.mime_type.split("/")[-1]
                info = f"{stream.abr or 'N/A'} | {ext.upper()}"
                self.master.after(0, lambda s=stream, t=info: self._add_stream_button(self.audio_scroll, t, s, "audio"))

        except Exception as e:
            self.master.after(0, lambda err=e: self.title_label.configure(text=f"Error: {e}"))
            self.master.after(0, lambda: self.download_button.configure(state="disabled"))

    def _set_thumbnail(self, photo):
        self.thumbnail_label.configure(image=photo, text="")
        self.thumbnail_label.image = photo

    def _add_stream_button(self, parent, text, stream, mode):
        btn = ctk.CTkButton(parent, text=text, anchor="w")
        btn.configure(command=functools.partial(self.select_stream, stream, btn, mode))
        btn.pack(pady=3, padx=5, fill="x")

    def select_stream(self, stream, button, mode):
        selection_changed = False

        if mode == "video":
            if self.selected_video == stream: return
            if self.selected_video_btn:
                self.selected_video_btn.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])
            self.selected_video = stream
            self.selected_video_btn = button
            selection_changed = True
        else:
            if self.selected_audio == stream: return
            if self.selected_audio_btn:
                self.selected_audio_btn.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])
            self.selected_audio_btn = button
            self.selected_audio = stream
            selection_changed = True

        button.configure(fg_color=("#2a8cff", "#1b6fd8"))

        if selection_changed:
            resolution = getattr(stream, 'resolution', getattr(stream, 'abr', ''))
            print(f"Selected {mode}: {resolution} | {stream.mime_type}")

    def on_progress(self, stream, chunk, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        percentage_of_completion = bytes_downloaded / total_size

        self.master.after(0, lambda: self.progress_bar.set(percentage_of_completion))
        self.master.after(0, lambda: self.status_label.configure(
            text=f"Downloading... {percentage_of_completion * 100:.1f}%"))

    def on_complete(self, stream, file_path):
        print(f"Download of {stream.title} completed at {file_path}!")
        self.master.after(0, lambda: self.status_label.configure(text="Download complete, starting merge.", text_color="white"))

    def on_download(self):
        threading.Thread(target=self._download_thread, daemon=True).start()

    def _download_thread(self):
        choice = self.choice_var.get()
        print(f"Download mode: {choice}")
        self.master.after(0, lambda: self.status_label.configure(text="Downloading...", text_color="white"))
        self.master.after(0, lambda: self.download_button.configure(state="disabled"))

        video_path = None
        audio_path = None

        self.master.after(0, lambda: self.progress_bar.set(0))

        try:
            if choice == "video":
                if self.selected_video is not None:
                    ext = self.selected_video.mime_type.split('/')[-1]
                    print("Downloading video...")
                    self.selected_video.on_progress_callback = self.on_progress
                    self.selected_video.download(filename=f"video.{ext}")
                    self.master.after(0, lambda: self.status_label.configure(text="Download complete!", text_color="green"))
                else:
                    self.master.after(0, lambda: self.status_label.configure(text="No video selected.", text_color="yellow"))

            elif choice == "audio":
                if self.selected_audio is not None:
                    ext = self.selected_audio.mime_type.split('/')[-1]
                    print("Downloading audio...")
                    self.selected_audio.on_progress_callback = self.on_progress
                    self.selected_audio.download(filename=f"audio.{ext}")
                    self.master.after(0, lambda: self.status_label.configure(text="Download complete!", text_color="green"))
                else:
                    self.master.after(0, lambda: self.status_label.configure(text="No audio selected.", text_color="yellow"))

            elif choice == "both":
                if self.selected_video and self.selected_audio:

                    self.selected_video.on_progress_callback = self.on_progress
                    self.selected_video.on_complete_callback = self.on_complete

                    print("Downloading video stream...")
                    video_path = self.selected_video.download(filename_prefix="video_")

                    self.master.after(0, lambda: self.progress_bar.set(0))
                    self.master.after(0, lambda: self.status_label.configure(text="Downloading audio stream...", text_color="white"))
                    print("Downloading audio stream...")
                    # audio progress not tracked, just status label
                    audio_path = self.selected_audio.download(filename_prefix="audio_")

                    custom_name = self.filename_var.get().strip()
                    if not custom_name and self.current_yt_object:
                        custom_name = clean_filename(self.current_yt_object.title)
                    elif not custom_name:
                        custom_name = "output"  # fallback

                    output_path = f"{custom_name}.mp4"
                    print(f"Merging streams into {output_path}...")
                    self.master.after(0, lambda: self.status_label.configure(
                        text="Merging streams... (This may take a moment)", text_color="white"))
                    self.master.after(0, lambda: self.progress_bar.set(-1))  # indeterminate status

                    (
                        ffmpeg.concat(
                            ffmpeg.input(video_path),
                            ffmpeg.input(audio_path),
                            v=1, a=1,
                        ).output(output_path, vcodec='copy', acodec='copy')
                        .run(overwrite_output=True)
                    )

                    print("Merged and saved as", output_path)
                    self.master.after(0, lambda: self.status_label.configure(text=f"Merged and saved as {output_path}", text_color="green"))
                    self.master.after(0, lambda: self.progress_bar.set(1.0))

                else:
                    self.master.after(0, lambda: self.status_label.configure(text="Select both video and audio first.", text_color="yellow"))

        except Exception as e:
            print(f"Download error: {e}")
            self.master.after(0, lambda err=e: self.status_label.configure(text=f"Error: {e}", text_color="red"))

        finally:
            self.master.after(0, lambda: self.progress_bar.set(0))  # reset progress visual
            self.master.after(0, lambda: self.download_button.configure(state="normal"))

            # clean up temporary files
            try:
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)
                    print(f"Cleaned up {video_path}")
                if audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)
                    print(f"Cleaned up {audio_path}")
            except Exception as e:
                print(f"Error cleaning up temp files: {e}")


if __name__ == "__main__":
    apply_initial_theme()
    root = ctk.CTk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()