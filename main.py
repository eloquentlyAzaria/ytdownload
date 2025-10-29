import pytubefix
from pytubefix import YouTube
import customtkinter as ctk
from PIL import Image
import requests
from io import BytesIO
import ffmpeg
import threading
import functools
from typing import Optional
import os

ctk.set_appearance_mode("dark")
try:
    ctk.set_default_color_theme("./marsh.json")
except FileNotFoundError:
    ctk.set_default_color_theme("blue")  # fallback theme

# logic functions
selected_video: Optional["pytubefix.streams.Stream"] = None
selected_audio: Optional["pytubefix.streams.Stream"] = None
selected_video_btn = None
selected_audio_btn = None


def getvideoinfo(link):
    yt = YouTube(link)
    title = yt.title
    thumbnail = yt.thumbnail_url
    video = yt.streams.filter(progressive=False, type="video")
    audio = yt.streams.filter(only_audio=True)
    return yt, title, thumbnail, video, audio


# --- organise and print video streams ---
def list_video_streams(link):
    video = getvideoinfo(link)[3]

    # sort resolutions numerically
    def res_value(stream):
        if getattr(stream, "resolution", None):
            # resolution strings like "1080p"
            return int(stream.resolution.replace("p", ""))
        return 0

    sorted_video = sorted(video, key=res_value, reverse=True)
    return sorted_video


# --- organise and print audio streams ---
def list_audio_streams(link):
    yt, title, thumbnail, video, audio = getvideoinfo(link)

    def abr_value(stream):
        if getattr(stream, "abr", None):
            return int(stream.abr.replace("kbps", "").strip())
        return 0

    sorted_audio = sorted(audio, key=abr_value, reverse=True)
    return sorted_audio


def on_fetch():
    threading.Thread(target=_fetch_thread, daemon=True).start()


def _fetch_thread():
    global selected_video, selected_audio, selected_video_btn, selected_audio_btn
    selected_video = None
    selected_audio = None
    selected_video_btn = None
    selected_audio_btn = None

    link = url_entry.get().strip()
    if not link:
        root.after(0, lambda: title_label.configure(text="Please enter a valid URL."))
        return

    root.after(0, lambda: title_label.configure(text="Fetching info… please wait."))
    root.after(0, lambda: status_label.configure(text=""))
    # Clear old buttons
    root.after(0, lambda: [w.destroy() for w in video_scroll.winfo_children()])
    root.after(0, lambda: [w.destroy() for w in audio_scroll.winfo_children()])
    root.after(0, lambda: thumbnail_label.configure(image=None, text="(Thumbnail will appear here)"))

    try:
        yt, title, thumbnail, video, audio = getvideoinfo(link)
        root.after(0, lambda: title_label.configure(text=title))

        # thumbnail
        try:
            response = requests.get(thumbnail, timeout=10)
            img = Image.open(BytesIO(response.content)).resize((320, 180))
            photo = ctk.CTkImage(light_image=img, size=(320, 180))
            root.after(0, lambda: _set_thumbnail(photo))
        except Exception as e:
            root.after(0, lambda err=e: title_label.configure(text=f"Image error: {err}"))

        # add video buttons
        for stream in list_video_streams(link):
            ext = stream.mime_type.split("/")[-1]
            info = f"{stream.resolution or 'N/A'} | {stream.fps or 'N/A'}fps | {ext.upper()}"
            root.after(0, lambda s=stream, t=info: _add_stream_button(video_scroll, t, s, "video"))

        # add audio buttons
        for stream in list_audio_streams(link):
            ext = stream.mime_type.split("/")[-1]
            info = f"{stream.abr or 'N/A'} | {ext.upper()}"
            root.after(0, lambda s=stream, t=info: _add_stream_button(audio_scroll, t, s, "audio"))

    except Exception as e:
        root.after(0, lambda err=e: title_label.configure(text=f"Error: {err}"))


def _set_thumbnail(photo):
    thumbnail_label.configure(image=photo, text="")
    thumbnail_label.image = photo


def _add_stream_button(parent, text, stream, mode):
    btn = ctk.CTkButton(parent, text=text, anchor="w")
    btn.configure(command=functools.partial(select_stream, stream, btn, mode))
    btn.pack(pady=3, padx=5, fill="x")


def select_stream(stream, button, mode):
    global selected_video, selected_audio, selected_video_btn, selected_audio_btn

    # reset previous highlight
    if mode == "video":
        if selected_video_btn:
            selected_video_btn.configure(fg_color=customtkinter.ThemeManager.theme["CTkButton"]["fg_color"])
        selected_video = stream
        selected_video_btn = button
    else:
        if selected_audio_btn:
            selected_audio_btn.configure(fg_color=customtkinter.ThemeManager.theme["CTkButton"]["fg_color"])
        selected_audio_btn = button
        selected_audio = stream

    # highlight current
    button.configure(fg_color=("#2a8cff", "#1b6fd8"))
    print(f"Selected {mode}: {getattr(stream, 'resolution', getattr(stream, 'abr', ''))} | {stream.mime_type}")

    resolution = getattr(stream, 'resolution', getattr(stream, 'abr', ''))
    print(f"Selected {mode}: {resolution} | {stream.mime_type}")


def on_download():
    threading.Thread(target=_download_thread, daemon=True).start()


def _download_thread():
    global selected_video, selected_audio
    choice = choice_var.get()
    print(f"Download mode: {choice}")
    root.after(0, lambda: status_label.configure(text="Downloading...", text_color="white"))

    video_path = selected_video.download(filename_prefix="video_")
    audio_path = selected_audio.download(filename_prefix="audio_")

    try:
        if choice == "video":
            if selected_video is not None:
                ext = selected_video.mime_type.split('/')[-1]
                print("Downloading video...")
                selected_video.download(filename=f"video.{ext}")
                root.after(0, lambda: status_label.configure(text="Download complete!", text_color="green"))
            else:
                print("No video selected.")
                root.after(0, lambda: status_label.configure(text="No video selected.", text_color="yellow"))

        elif choice == "audio":
            if selected_audio is not None:
                ext = selected_audio.mime_type.split('/')[-1]
                print("Downloading audio...")
                selected_audio.download(filename=f"audio.{ext}")
                root.after(0, lambda: status_label.configure(text="Download complete!", text_color="green"))
            else:
                print("No audio selected")
                root.after(0, lambda: status_label.configure(text="No audio selected.", text_color="yellow"))

        elif choice == "both":
            if selected_video and selected_audio:
                print("Downloading video stream...")
                video_path = selected_video.download(filename_prefix="video_")
                print("Downloading audio stream...")
                audio_path = selected_audio.download(filename_prefix="audio_")

                #---DIAGNOSTIC PRINT---
                print(f"FFmpeg INPUT 1 (Video): Path='{video_path}' Type={type(video_path)}")
                print(f"FFmpeg INPUT 2 (Audio): Path='{audio_path}' Type={type(audio_path)}")
                #----------------------

                output_path = "output.mp4"
                print(f"Merging streams into {output_path}...")

                (
                    ffmpeg
                    .input(video_path)
                    .input(audio_path)
                    .output(output_path, vcodec='copy', acodec='aac')
                    .run(overwrite_output=True)
                )
                print("Merged and saved as", output_path)
                root.after(0, lambda: status_label.configure(text=f"Merged and saved as {output_path}",
                                                             text_color="green"))

            else:
                print("Select both video and audio first.")
                root.after(0, lambda: status_label.configure(text="Select both video and audio first.",  text_color="yellow"))

    except Exception as e:
        print(f"Download error: {e}")
        root.after(0, lambda err=e: status_label.configure(text=f"Error: {err}", text_color="red"))

    finally:
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


# --- GUI ---
root = ctk.CTk()
root.title("YouTube Video Downloader")
root.geometry("800x650")

# input and fetch button section
input_frame = ctk.CTkFrame(root)
input_frame.pack(pady=20, padx=20, fill="x")
url_entry = ctk.CTkEntry(input_frame, placeholder_text="Enter YouTube URL here...")
url_entry.pack(side="left", expand=True, fill="x", padx=10)
fetch_button = ctk.CTkButton(input_frame, text="Fetch Info", command=on_fetch)
fetch_button.pack(side="right", padx=10)

# video info section
info_frame = ctk.CTkFrame(root)
info_frame.pack(pady=10, padx=20, fill="x")

# wraplength
title_label = ctk.CTkLabel(info_frame, text="", font=("Segoe UI", 18, "bold"), wraplength=750)
title_label.pack(pady=(0, 10))

thumbnail_label = ctk.CTkLabel(info_frame, text="(Thumbnail will appear here)", height=180)
thumbnail_label.pack()

# streams list
lists_frame = ctk.CTkFrame(root)
lists_frame.pack(fill="both", expand=True, padx=20, pady=10)

video_scroll = ctk.CTkScrollableFrame(lists_frame, label_text="Video Streams")
video_scroll.pack(side="left", fill="both", expand=True, padx=5)

audio_scroll = ctk.CTkScrollableFrame(lists_frame, label_text="Audio Streams")
audio_scroll.pack(side="right", fill="both", expand=True, padx=5)

# controls
bottom_frame = ctk.CTkFrame(root)
bottom_frame.pack(pady=15, fill="x", padx=20)  # fill x

radio_frame = ctk.CTkFrame(bottom_frame)
radio_frame.pack(side="left", padx=(10, 0))

choice_var = ctk.StringVar(value="both")

ctk.CTkRadioButton(radio_frame, text="Video Only", variable=choice_var, value="video").pack(side="left", padx=5)
ctk.CTkRadioButton(radio_frame, text="Audio Only", variable=choice_var, value="audio").pack(side="left", padx=5)
ctk.CTkRadioButton(radio_frame, text="Both", variable=choice_var, value="both").pack(side="left", padx=5)

download_button = ctk.CTkButton(bottom_frame, text="Download", command=on_download)
download_button.pack(side="right", padx=10)

status_label = ctk.CTkLabel(root, text="")
status_label.pack(pady=(0, 10))


root.mainloop()