import sys, os, subprocess, json, urllib.request, webbrowser, datetime, re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QMessageBox, QFileDialog, QHBoxLayout, QProgressBar, QComboBox, QFrame, QSizePolicy,
    QDialog, QListWidget, QListWidgetItem, QAbstractItemView, QTextEdit, QCheckBox, QSpinBox,
    QScrollArea, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl
from PyQt5.QtGui import QIcon, QPixmap, QFont, QColor, QKeySequence
from PyQt5.QtGui import QDesktopServices 
from PyQt5.QtWidgets import QShortcut

def get_browser_cookies(browser_name):
    """
    Extract cookies for YouTube from the selected browser using browser_cookie3.
    Returns path to a temporary cookies.txt file.
    """
    try:
        import browser_cookie3
        import tempfile
        cj = None
        if browser_name == "Chrome":
            cj = browser_cookie3.chrome(domain_name='youtube.com')
        elif browser_name == "Edge":
            cj = browser_cookie3.edge(domain_name='youtube.com')
        elif browser_name == "Firefox":
            cj = browser_cookie3.firefox(domain_name='youtube.com')
        elif browser_name == "Brave":
            cj = browser_cookie3.brave(domain_name='youtube.com')
        else:
            raise Exception("Unsupported browser")
        # Save cookies to a temp file in Netscape format
        import http.cookiejar
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        cj.save(tmp.name, ignore_discard=True, ignore_expires=True)
        return tmp.name
    except Exception as e:
        raise Exception(f"Failed to get cookies from {browser_name}: {e}")

class BrowserSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Browser for Cookies")
        self.setStyleSheet("""
            QDialog {background: #23243a; color: #fff;}
            QPushButton {background: #009688; color:#fff; border-radius: 8px; font-size: 16px; padding: 12px 28px; margin: 12px;}
            QLabel {font-size: 16px;}
        """)
        vbox = QVBoxLayout(self)
        vbox.addWidget(QLabel("Select your browser to use its cookies for YouTube download:"))
        btns = QDialogButtonBox()
        self.browser = None
        for name in ["Chrome", "Edge", "Firefox", "Brave"]:
            btn = QPushButton(name)
            btn.clicked.connect(lambda _, n=name: self.select_browser(n))
            vbox.addWidget(btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        vbox.addWidget(cancel_btn)

    def select_browser(self, name):
        self.browser = name
        self.accept()

# --- Global constants ---
APP_TITLE = "YT & Spotify Downloader"
APP_COPYRIGHT = "© 2024 Alexx993"
APP_VERSION = "v1.0"
HISTORY_FILE = "download_history.json"

def human_size(nbytes):
    try:
        suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
        for unit in suffixes:
            if abs(nbytes) < 1024.0:
                return "%3.1f %s" % (nbytes, unit)
            nbytes /= 1024.0
        return "%.1f PB" % nbytes
    except Exception:
        return "?"

def is_spotify_url(url):
    return "spotify.com" in url

def is_playlist_url(url):
    return "playlist" in url or "list=" in url

def save_history(entry):
    try:
        hist = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    hist = json.load(f)
            except json.JSONDecodeError:
                pass  # If file is corrupted, start fresh
        
        # Validate entry
        if not isinstance(entry, dict) or not entry.get('filepath'):
            return
            
        # Add to history only if file exists
        if os.path.exists(entry['filepath']):
            hist.insert(0, entry)  # latest first
        if len(hist) > 1000:
            hist = hist[:1000]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("History save error:", e)

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print("History load error:", e)
        return []
    return []

def clear_history():
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
    except Exception:
        pass

def get_subtitle_languages(formats, subtitles, automatic_captions):
    # Check if subtitles are actually available
    if not subtitles and not automatic_captions:
        return []
        
    # Filter out empty subtitle lists
    subtitles = {k: v for k, v in subtitles.items() if v}
    automatic_captions = {k: v for k, v in automatic_captions.items() if v}
    
    if not subtitles and not automatic_captions:
        return []
    
    # Common language names mapping
    lang_names = {
        'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
        'it': 'Italian', 'pt': 'Portuguese', 'ru': 'Russian', 'ja': 'Japanese',
        'ko': 'Korean', 'zh': 'Chinese', 'ar': 'Arabic', 'hi': 'Hindi',
        'tr': 'Turkish', 'nl': 'Dutch', 'pl': 'Polish', 'vi': 'Vietnamese',
        'th': 'Thai', 'id': 'Indonesian', 'sv': 'Swedish', 'da': 'Danish',
        'fi': 'Finnish', 'no': 'Norwegian', 'ro': 'Romanian', 'hu': 'Hungarian',
        'cs': 'Czech', 'uk': 'Ukrainian', 'el': 'Greek', 'bg': 'Bulgarian',
        'he': 'Hebrew', 'sk': 'Slovak', 'sr': 'Serbian', 'hr': 'Croatian'
    }
    
    lang_list = []
    if subtitles:
        for lang, subs in subtitles.items():
            name = lang_names.get(lang.split('-')[0], lang)
            # Check if subtitle has multiple formats
            formats = [s.get('ext', 'unknown') for s in subs]
            formats_str = f" [{', '.join(set(formats))}]" if formats else ""
            lang_list.append((lang, f"{name} (manual){formats_str}"))
            
    if automatic_captions:
        for lang, subs in automatic_captions.items():
            name = lang_names.get(lang.split('-')[0], lang)
            if not any(l[0] == lang for l in lang_list):  # Avoid duplicates
                formats = [s.get('ext', 'unknown') for s in subs]
                formats_str = f" [{', '.join(set(formats))}]" if formats else ""
                lang_list.append((lang, f"{name} (auto-generated){formats_str}"))
    
    # Sort by manual subs first, then by language name
    return sorted(lang_list, key=lambda x: (
        'auto' in x[1],  # Sort manual before auto
        lang_names.get(x[0].split('-')[0], x[0])  # Then by language name
    ))

class FetchFormatsThread(QThread):
    finished = pyqtSignal(list, str, str, str, str, list, dict, dict, bool, list)
    error = pyqtSignal(str)
    def __init__(self, url):
        super().__init__()
        self.url = url
    def run(self):
        try:
            if is_spotify_url(self.url):
                qual_list = [("Best Quality [audio]", "best", "[audio only]")]
                title = "Spotify Track"
                thumbnail = ""
                channel = ""
                duration = ""
                has_playlist = False
                playlist_entries = []
                self.finished.emit(qual_list, title, thumbnail, channel, duration, [], {}, {}, has_playlist, playlist_entries)
                return
            cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "-J", "--flat-playlist", "--", self.url]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                self.error.emit(f"yt-dlp error: {proc.stderr or proc.stdout}")
                return
            info = json.loads(proc.stdout)
            has_playlist = 'entries' in info and isinstance(info['entries'], list) and len(info['entries']) > 1
            playlist_entries = []
            if has_playlist:
                playlist_entries = info['entries']
                video_url = "https://www.youtube.com/watch?v=" + playlist_entries[0].get('id', '')
                cmd_info = [sys.executable, "-m", "yt_dlp", "--no-warnings", "-J", "--", video_url]
                proc_info = subprocess.run(cmd_info, capture_output=True, text=True)
                if proc_info.returncode != 0:
                    self.error.emit(f"yt-dlp error: {proc_info.stderr or proc_info.stdout}")
                    return
                info = json.loads(proc_info.stdout)
            formats = info.get("formats", [])
            title = info.get("title", "Unknown Title")
            thumbnail = info.get("thumbnail", "")
            channel = info.get("channel", "")
            duration = info.get("duration_string", "") if "duration_string" in info else ""
            subtitles = info.get("subtitles", {})
            automatic_captions = info.get("automatic_captions", {})
            lang_list = get_subtitle_languages(formats, subtitles, automatic_captions)
            qual_list = []
            for f in formats:
                fs = f.get("filesize") or f.get("filesize_approx")
                size_label = human_size(fs) if fs else "?"
                vcodec = f.get("vcodec", "none")
                acodec = f.get("acodec", "none")
                if vcodec != "none" and acodec != "none":
                    stream_type = "[video+audio]"
                elif vcodec != "none":
                    stream_type = "[video only]"
                elif acodec != "none":
                    stream_type = "[audio only]"
                else:
                    stream_type = "[unknown]"
                res = f.get("resolution") or (f"{f.get('height','')}p" if f.get('height') else "")
                label = f"{f.get('format_id')} {stream_type} | {f.get('ext')} | {res} | {f.get('fps','')}fps | {size_label}"
                qual_list.append((label, f["format_id"], stream_type))
            if not qual_list:
                self.error.emit("No downloadable formats found.")
            else:
                self.finished.emit(
                    qual_list, title, thumbnail, channel, duration,
                    lang_list, subtitles, automatic_captions, has_playlist, playlist_entries
                )
        except Exception as e:
            self.error.emit(f"Error fetching formats: {e}")

class DownloadThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str, str, dict)
    error = pyqtSignal(str)

    def __init__(self, url, folder, format_id, stream_type, title, thumbnail_url,
                 embed_subs=False, subtitle_langs=None, playlist_range=None, playlist_mode=None, playlist_total=None, force_aac=False, proxy=None, use_vpn=False):
        super().__init__()
        self.url = url
        self.folder = folder
        self.format_id = format_id
        self.stream_type = stream_type
        self.title = title
        self.thumbnail_url = thumbnail_url
        self.embed_subs = embed_subs
        self.subtitle_langs = subtitle_langs or []
        self.playlist_range = playlist_range
        self.playlist_mode = playlist_mode
        self.playlist_total = playlist_total
        self.force_aac = force_aac
        self.proxy = proxy
        self.use_vpn = use_vpn

    def run(self):
        try:
            # Connect VPN if requested (dummy implementation, replace with actual VPN logic)
            if self.use_vpn:
                print("[INFO] VPN connection requested. Please connect your VPN manually or implement auto-connect here.")
            if is_spotify_url(self.url):
                outtmpl = os.path.join(self.folder, "{artist} - {title}.{ext}")
                cmd = [
                    sys.executable, "-m", "spotdl", "download", self.url,
                    "--output", outtmpl
                ]
                if self.proxy:
                    cmd += ["--proxy", self.proxy]
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                percent = 0
                filename = None
                all_output = ""
                for line in process.stdout:
                    all_output += line
                    if "%" in line:
                        match = re.search(r'(\d{1,3}\.\d+)%', line)
                        if match:
                            percent = int(float(match.group(1)))
                            self.progress.emit(percent, f"Downloading... {percent}%")
                    if "Downloaded:" in line or "Saved:" in line:
                        part = line.split(":")[-1].strip()
                        if part and os.path.exists(part):
                            filename = part
                process.wait()
                if process.returncode != 0:
                    self.error.emit("spotdl failed:\n" + all_output)
                    return
                if not filename:
                    files = [os.path.join(self.folder, f) for f in os.listdir(self.folder) if f.lower().endswith(('.mp3', '.m4a', '.ogg', '.flac')) and os.path.isfile(os.path.join(self.folder, f))]
                    if not files:
                        self.error.emit("No file found in download folder after spotdl run.\nOutput:\n" + all_output)
                        return
                    filename = max(files, key=os.path.getctime)
                entry = {
                    "title": self.title,
                    "url": self.url,
                    "filepath": filename,
                    "type": "Spotify",
                    "format": "audio",
                    "datetime": datetime.datetime.now().isoformat(),
                    "thumbnail": self.thumbnail_url
                }
                save_history(entry)
                self.finished.emit("Download complete!", filename, entry)
                return

            # --- yt-dlp block ---
            outtmpl = os.path.join(self.folder, "%(title)s.%(ext)s")
            fmt_str = f"{self.format_id}+bestaudio[ext=m4a]/bestaudio" if self.stream_type == "[video only]" else self.format_id
            extra_args = []
            is_video = self.stream_type in ("[video+audio]", "[video only]")
            if is_video and self.thumbnail_url:
                extra_args += ["--embed-thumbnail"]
            if self.subtitle_langs:
                lang_codes = ",".join(self.subtitle_langs)
                extra_args += ["--write-subs", "--sub-langs", lang_codes]
                if self.embed_subs and self.format_id and any(x in self.format_id for x in ["mp4", "mkv"]):
                    extra_args += ["--embed-subs"]
                elif self.embed_subs:
                    print("Warning: Selected format does not support subtitle embedding. Only mp4/mkv support embedding.")
            playlist_args = []
            playlist_count = self.playlist_total if self.playlist_total else 1
            if self.playlist_mode == "playlist":
                playlist_args = []
            elif self.playlist_mode == "range" and self.playlist_range:
                start, end = self.playlist_range
                playlist_args += [f"--playlist-start={start}", f"--playlist-end={end}"]
                playlist_count = end - start + 1
            elif self.playlist_mode == "single" and self.playlist_range:
                index = self.playlist_range[0]
                playlist_args += [f"--playlist-items={index}"]
                playlist_count = 1
            if is_video:
                extra_args += [
                    "--merge-output-format", "mp4",
                    "--add-metadata"
                ]
            cmd = [sys.executable, "-m", "yt_dlp", "-f", fmt_str, "-o", outtmpl, "--newline", self.url]
            if self.proxy:
                cmd += ["--proxy", self.proxy]
            cmd += extra_args + playlist_args

            def parse_progress(line, current_video=None, total_videos=None):
                # Robust regex for yt-dlp progress lines
                # Example: [download]   45.3% of 12.34MiB at 1.23MiB/s ETA 00:15
                percent, speed, eta = None, None, None
                try:
                    # percent
                    pct_match = re.search(r'(\d{1,3}(?:\.\d+)?)%', line)
                    if pct_match:
                        percent = int(float(pct_match.group(1)))
                    # speed
                    speed_match = re.search(r'at ([\d\.]+[KMG]?i?B/s)', line)
                    if speed_match:
                        speed = speed_match.group(1)
                    # ETA
                    eta_match = re.search(r'ETA (\d{2}:\d{2}(?::\d{2})?)', line)
                    if eta_match:
                        eta = eta_match.group(1)
                except Exception:
                    pass
                # Compose status string
                if current_video and total_videos:
                    msg = f"Video {current_video}/{total_videos}"
                    if percent is not None:
                        msg += f" → {percent}%"
                    if speed:
                        msg += f" | {speed}"
                    if eta:
                        msg += f" | ETA {eta}"
                else:
                    msg = "Downloading..."
                    if percent is not None:
                        msg += f" {percent}%"
                    if speed:
                        msg += f" | Speed: {speed}"
                    if eta:
                        msg += f" | Time left: {eta}"
                return percent, msg

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            percent = 0
            filename = None
            all_output = ""
            current_video = 1
            total_videos = playlist_count
            last_reported_video = -1
            download_files = []
            captcha_error = False
            for line in process.stdout:
                all_output += line
                # Playlist video progress detection
                pl_match = re.search(r'\[download\] Downloading video (\d+) of (\d+)', line)
                if pl_match:
                    current_video = int(pl_match.group(1))
                    total_videos = int(pl_match.group(2))
                    last_reported_video = current_video
                    self.progress.emit(0, f"Video {current_video}/{total_videos} → Starting...")
                # Progress info
                pct, msg = parse_progress(line, last_reported_video if last_reported_video > 0 else None, total_videos if last_reported_video > 0 else None)
                if pct is not None:
                    percent = pct
                    self.progress.emit(percent, msg)
                elif "Destination:" in line:
                    part = line.split("Destination:")[-1].strip()
                    if part:
                        filename = os.path.join(self.folder, os.path.basename(part))
                        download_files.append(filename)
                # Detect captcha/robot error
                if "confirm you are not a robot" in line.lower() or "captcha" in line.lower():
                    captcha_error = True
            process.wait()
            if process.returncode != 0:
                # If captcha error, prompt for browser cookies
                if captcha_error:
                    from PyQt5.QtWidgets import QApplication
                    app = QApplication.instance()
                    dlg = BrowserSelectDialog()
                    if dlg.exec_() == QDialog.Accepted and dlg.browser:
                        try:
                            self.progress.emit(0, f"Using cookies from {dlg.browser}...")
                            cookies_file = get_browser_cookies(dlg.browser)
                            cmd_cookies = cmd + ["--cookies", cookies_file]
                            process2 = subprocess.Popen(cmd_cookies, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                            percent = 0
                            filename = None
                            all_output2 = ""
                            current_video = 1
                            total_videos = playlist_count
                            last_reported_video = -1
                            download_files = []
                            captcha_error2 = False
                            for line in process2.stdout:
                                all_output2 += line
                                pl_match = re.search(r'\[download\] Downloading video (\d+) of (\d+)', line)
                                if pl_match:
                                    current_video = int(pl_match.group(1))
                                    total_videos = int(pl_match.group(2))
                                    last_reported_video = current_video
                                    self.progress.emit(0, f"Video {current_video}/{total_videos} → Starting...")
                                pct, msg = parse_progress(line, last_reported_video if last_reported_video > 0 else None, total_videos if last_reported_video > 0 else None)
                                if pct is not None:
                                    percent = pct
                                    self.progress.emit(percent, msg)
                                elif "Destination:" in line:
                                    part = line.split("Destination:")[-1].strip()
                                    if part:
                                        filename = os.path.join(self.folder, os.path.basename(part))
                                        download_files.append(filename)
                                if "confirm you are not a robot" in line.lower() or "captcha" in line.lower():
                                    captcha_error2 = True
                            process2.wait()
                            if process2.returncode != 0:
                                self.error.emit(f"yt-dlp failed (with cookies):\n{all_output2}")
                                return
                            # Determine file(s) downloaded for history
                            entries = []
                            if self.playlist_mode in ("playlist", "range", "single"):
                                for file in download_files:
                                    if os.path.exists(file):
                                        entry = {
                                            "title": os.path.splitext(os.path.basename(file))[0],
                                            "url": self.url,
                                            "filepath": file,
                                            "type": "YouTube",
                                            "format": self.stream_type,
                                            "datetime": datetime.datetime.now().isoformat(),
                                            "thumbnail": self.thumbnail_url
                                        }
                                        save_history(entry)
                                        entries.append(entry)
                                if entries:
                                    first_file = entries[0]["filepath"]
                                else:
                                    files = [os.path.join(self.folder, f) for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f))]
                                    if not files:
                                        self.error.emit("No file found in download folder after yt-dlp run.\nOutput:\n" + all_output2)
                                        return
                                    first_file = max(files, key=os.path.getctime)
                                    entry = {
                                        "title": os.path.splitext(os.path.basename(first_file))[0],
                                        "url": self.url,
                                        "filepath": first_file,
                                        "type": "YouTube",
                                        "format": self.stream_type,
                                        "datetime": datetime.datetime.now().isoformat(),
                                        "thumbnail": self.thumbnail_url
                                    }
                                    save_history(entry)
                                    entries.append(entry)
                                self.finished.emit("Download complete!", first_file, {"playlist": True, "entries": entries})
                                return
                            if not filename:
                                files = [os.path.join(self.folder, f) for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f))]
                                if not files:
                                    self.error.emit("No file found in download folder after yt-dlp run.\nOutput:\n" + all_output2)
                                    return
                                filename = max(files, key=os.path.getctime)
                            if not os.path.exists(filename):
                                self.error.emit(f"Download reported complete, but file not found.\nOutput:\n{all_output2}")
                                return
                            entry = {
                                "title": self.title,
                                "url": self.url,
                                "filepath": filename,
                                "type": "YouTube",
                                "format": self.stream_type,
                                "datetime": datetime.datetime.now().isoformat(),
                                "thumbnail": self.thumbnail_url
                            }
                            save_history(entry)
                            self.finished.emit("Download complete!", filename, entry)
                            return
                        except Exception as e:
                            self.error.emit(f"Failed to use browser cookies: {e}")
                            return
                    else:
                        self.error.emit("Download failed due to robot/captcha. Try again with browser cookies.")
                        return
                self.error.emit(f"yt-dlp failed:\n{all_output}")
                return

            # --- success, handle history/playlist ---
            entries = []
            if self.playlist_mode in ("playlist", "range", "single"):
                for file in download_files:
                    if os.path.exists(file):
                        entry = {
                            "title": os.path.splitext(os.path.basename(file))[0],
                            "url": self.url,
                            "filepath": file,
                            "type": "YouTube",
                            "format": self.stream_type,
                            "datetime": datetime.datetime.now().isoformat(),
                            "thumbnail": self.thumbnail_url
                        }
                        save_history(entry)
                        entries.append(entry)
                if entries:
                    first_file = entries[0]["filepath"]
                else:
                    files = [os.path.join(self.folder, f) for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f))]
                    if not files:
                        self.error.emit("No file found in download folder after yt-dlp run.\nOutput:\n" + all_output)
                        return
                    first_file = max(files, key=os.path.getctime)
                    entry = {
                        "title": os.path.splitext(os.path.basename(first_file))[0],
                        "url": self.url,
                        "filepath": first_file,
                        "type": "YouTube",
                        "format": self.stream_type,
                        "datetime": datetime.datetime.now().isoformat(),
                        "thumbnail": self.thumbnail_url
                    }
                    save_history(entry)
                    entries.append(entry)
                self.finished.emit("Download complete!", first_file, {"playlist": True, "entries": entries})
                return
            if not filename:
                files = [os.path.join(self.folder, f) for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f))]
                if not files:
                    self.error.emit("No file found in download folder after yt-dlp run.\nOutput:\n" + all_output)
                    return
                filename = max(files, key=os.path.getctime)
            if not os.path.exists(filename):
                self.error.emit(f"Download reported complete, but file not found.\nOutput:\n{all_output}")
                return
            entry = {
                "title": self.title,
                "url": self.url,
                "filepath": filename,
                "type": "YouTube",
                "format": self.stream_type,
                "datetime": datetime.datetime.now().isoformat(),
                "thumbnail": self.thumbnail_url
            }
            save_history(entry)
            self.finished.emit("Download complete!", filename, entry)
        except Exception as e:
            import traceback
            self.error.emit(f"Download error: {e}\n{traceback.format_exc()}")

class PlaylistDialog(QDialog):
    def __init__(self, playlist_entries, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Playlist Download Options")
        self.setStyleSheet("""
            QDialog {background: #23243a; color: #fff;}
            QRadioButton, QLabel {font-size: 15px;}
            QPushButton {background: #009688; color:#fff; border-radius: 8px; font-size: 13px; padding: 6px 18px;}
        """)
        self.selection = None
        vbox = QVBoxLayout(self)
        self.entries = playlist_entries
        total = len(self.entries)
        self.range_mode = None

        from PyQt5.QtWidgets import QRadioButton, QButtonGroup
        self.group = QButtonGroup(self)
        self.radio_playlist = QRadioButton(f"Download Entire Playlist ({total} videos)")
        self.radio_range = QRadioButton("Download Range:")
        self.radio_single = QRadioButton("Download Single Video:")
        self.group.addButton(self.radio_playlist, 0)
        self.group.addButton(self.radio_range, 1)
        self.group.addButton(self.radio_single, 2)
        self.radio_playlist.setChecked(True)

        vbox.addWidget(self.radio_playlist)

        range_row = QHBoxLayout()
        self.start_spin = QSpinBox()
        self.start_spin.setMinimum(1)
        self.start_spin.setMaximum(total)
        self.start_spin.setValue(1)
        self.end_spin = QSpinBox()
        self.end_spin.setMinimum(1)
        self.end_spin.setMaximum(total)
        self.end_spin.setValue(min(5, total))
        range_row.addWidget(self.radio_range)
        range_row.addWidget(QLabel("From:"))
        range_row.addWidget(self.start_spin)
        range_row.addWidget(QLabel("To:"))
        range_row.addWidget(self.end_spin)
        vbox.addLayout(range_row)

        single_row = QHBoxLayout()
        self.single_spin = QSpinBox()
        self.single_spin.setMinimum(1)
        self.single_spin.setMaximum(total)
        self.single_spin.setValue(1)
        single_row.addWidget(self.radio_single)
        single_row.addWidget(QLabel("Video #:"))
        single_row.addWidget(self.single_spin)
        vbox.addLayout(single_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch(2)
        ok = QPushButton("OK")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        vbox.addLayout(btn_row)

    def get_selection(self):
        if self.radio_playlist.isChecked():
            return ("playlist", None)
        elif self.radio_range.isChecked():
            start, end = self.start_spin.value(), self.end_spin.value()
            if start > end:
                start, end = end, start
            return ("range", (start, end))
        elif self.radio_single.isChecked():
            idx = self.single_spin.value()
            return ("single", (idx, idx))
        return ("playlist", None)

class SubtitleDialog(QDialog):
    def __init__(self, lang_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Subtitle Options")
        self.setStyleSheet("""
            QDialog {background: #23243a; color: #fff;}
            QCheckBox, QLabel {font-size: 15px;}
            QPushButton {background: #009688; color:#fff; border-radius: 8px; font-size: 13px; padding: 6px 18px;}
        """)
        self.selected_langs = []
        vbox = QVBoxLayout(self)
        self.check_embed = QCheckBox("Embed subtitle(s) into video (if possible)")
        self.check_embed.setChecked(True)
        vbox.addWidget(self.check_embed)
        # Create a scroll area for subtitle options
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none; background:transparent;}")
        
        # Container widget for checkboxes
        container = QWidget()
        container_layout = QVBoxLayout()
        container.setLayout(container_layout)
        
        # Add language checkboxes
        self.lang_checks = []
        container_layout.addWidget(QLabel("Available subtitle languages:"))
        for lang, desc in lang_list:
            cb = QCheckBox(desc)
            cb.lang = lang
            container_layout.addWidget(cb)
            self.lang_checks.append(cb)
        
        scroll.setWidget(container)
        scroll.setMinimumHeight(300)  # Set reasonable default height
        vbox.addWidget(scroll)
        btn_row = QHBoxLayout()
        btn_row.addStretch(2)
        ok = QPushButton("OK")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        vbox.addLayout(btn_row)

    def get_selection(self):
        langs = [cb.lang for cb in self.lang_checks if cb.isChecked()]
        embed = self.check_embed.isChecked()
        return embed, langs

class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download History")
        self.resize(700, 500)
        self.setStyleSheet("""
            QDialog {background: #23243a; color: #fff;}
            QListWidget {background: #20232a; color: #fff; font-size: 15px; border-radius: 10px;}
            QPushButton {background: #009688; color:#fff; border-radius: 8px; font-size: 13px; padding: 6px 18px;}
            QPushButton#clear {background: #ff1744;}
        """)
        vbox = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setIconSize(QSize(60,60))
        vbox.addWidget(self.list)
        btns = QHBoxLayout()
        self.open_btn = QPushButton("Open File")
        self.openf_btn = QPushButton("Open Folder")
        self.copy_btn = QPushButton("Copy Path")
        self.clear_btn = QPushButton("Clear History")
        self.clear_btn.setObjectName("clear")
        btns.addWidget(self.open_btn)
        btns.addWidget(self.openf_btn)
        btns.addWidget(self.copy_btn)
        btns.addStretch(1)
        btns.addWidget(self.clear_btn)
        vbox.addLayout(btns)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setStyleSheet("background:#20232a;color:#ffeb3b;font-size:13px;border-radius:8px;")
        vbox.addWidget(self.details)
        self.load_history()
        self.list.currentItemChanged.connect(self.show_details)
        self.open_btn.clicked.connect(self.open_file)
        self.openf_btn.clicked.connect(self.open_folder)
        self.copy_btn.clicked.connect(self.copy_path)
        self.clear_btn.clicked.connect(self.clear_all)

    def load_history(self):
        self.list.clear()
        self.entries = load_history()
        for entry in self.entries:
            if isinstance(entry, dict) and "entries" in entry and entry.get("playlist"):
                # playlist history
                for pl_entry in entry["entries"]:
                    icon = QIcon()
                    if pl_entry.get("thumbnail"):
                        try:
                            data = urllib.request.urlopen(pl_entry["thumbnail"]).read()
                            pix = QPixmap()
                            pix.loadFromData(data)
                            icon = QIcon(pix)
                        except Exception:
                            icon = QIcon()
                    label = f"{pl_entry['title']}  [{pl_entry['type']}] ({pl_entry['datetime'][:19].replace('T',' ')})"
                    item = QListWidgetItem(icon, label)
                    item.setData(Qt.UserRole, pl_entry)
                    self.list.addItem(item)
            else:
                icon = QIcon()
                if entry.get("thumbnail"):
                    try:
                        data = urllib.request.urlopen(entry["thumbnail"]).read()
                        pix = QPixmap()
                        pix.loadFromData(data)
                        icon = QIcon(pix)
                    except Exception:
                        icon = QIcon()
                label = f"{entry['title']}  [{entry['type']}] ({entry['datetime'][:19].replace('T',' ')})"
                item = QListWidgetItem(icon, label)
                item.setData(Qt.UserRole, entry)
                self.list.addItem(item)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def show_details(self, item):
        if not item:
            self.details.setPlainText("")
            return
        entry = item.data(Qt.UserRole)
        txt = (
            f"Title: {entry.get('title')}\n"
            f"URL: {entry.get('url')}\n"
            f"Type: {entry.get('type')} ({entry.get('format')})\n"
            f"File: {entry.get('filepath')}\n"
            f"Date: {entry.get('datetime')}\n"
        )
        self.details.setPlainText(txt)

    def open_file(self):
        item = self.list.currentItem()
        if item:
            entry = item.data(Qt.UserRole)
            fp = entry.get("filepath")
            if fp and os.path.exists(fp):
                os.startfile(fp) if sys.platform == "win32" else subprocess.call(["open", fp])

    def open_folder(self):
        item = self.list.currentItem()
        if item:
            entry = item.data(Qt.UserRole)
            fp = entry.get("filepath")
            if fp and os.path.exists(fp):
                folder = os.path.dirname(fp)
                os.startfile(folder) if sys.platform == "win32" else subprocess.call(["open", folder])

    def copy_path(self):
        item = self.list.currentItem()
        if item:
            entry = item.data(Qt.UserRole)
            fp = entry.get("filepath")
            if fp:
                QApplication.clipboard().setText(fp)

    def clear_all(self):
        if QMessageBox.question(self, "Clear?", "Clear entire history?") == QMessageBox.Yes:
            clear_history()
            self.load_history()
            self.details.setPlainText("")

class YTDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon("icon.png") if os.path.exists("icon.png") else QIcon())
        self.resize(1200, 700)
        self.setMinimumSize(900, 500)
        self.folder = os.path.join(os.path.expanduser("~"), "Downloads")
        self.setAcceptDrops(True)
        self.theme_dark = True
        self.proxy = ""
        self.proxy_type = "http"  # or "socks5"
        self.use_vpn = False
        self.use_proxy = False
        self.proxy_status = "disconnected"

        # Ensure bg_label is created first
        self.bg_label = QLabel(self)
        self.bg_label.setScaledContents(True)
        pix = QPixmap("bg.jpg") if os.path.exists("bg.jpg") else QPixmap(self.width(), self.height())
        if pix.isNull():
            pix.fill(QColor(34, 40, 49))
        self.bg_label.setPixmap(pix)
        self.bg_label.setGeometry(0, 0, self.width(), self.height())
        self.bg_label.lower()

        # Improved main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)

        # Left panel (controls)
        left_panel = QFrame(self)
        left_panel.setObjectName("leftPanel")
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(32, 32, 32, 32)
        left_layout.setSpacing(18)

        # Proxy/VPN checkbox
        self.proxy_checkbox = QCheckBox("Auto-connect Proxy/VPN for downloads (unblock region)")
        self.proxy_checkbox.setChecked(False)
        self.proxy_checkbox.stateChanged.connect(self.on_proxy_checkbox_changed)
        self.proxy_checkbox.setFont(QFont("Segoe UI", 13))
        left_layout.addWidget(self.proxy_checkbox)

        # Logo and title
        logo_row = QHBoxLayout()
        logo = QLabel()
        logo.setAlignment(Qt.AlignLeft)
        logo_path = "logo.png"
        pix_logo = QPixmap(logo_path)
        if not pix_logo.isNull():
            logo.setPixmap(pix_logo.scaledToHeight(64, Qt.SmoothTransformation))
        else:
            logo.setText("🎬")
            logo.setFont(QFont("Segoe UI Emoji", 50))
        logo_row.addWidget(logo)
        title = QLabel(APP_TITLE)
        title.setFont(QFont("Segoe UI", 28, QFont.Bold))
        title.setStyleSheet("color: #ff1744; letter-spacing:2.5px;")
        title.setAlignment(Qt.AlignLeft)
        title.setWordWrap(True)
        logo_row.addWidget(title)
        left_layout.addLayout(logo_row)

        subtitle = QLabel("Modern YouTube & Spotify Downloader")
        subtitle.setFont(QFont("Segoe UI", 15))
        subtitle.setStyleSheet("color: #fafafa;")
        subtitle.setAlignment(Qt.AlignLeft)
        subtitle.setWordWrap(True)
        left_layout.addWidget(subtitle)

        # URL input row
        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube, Spotify (or other site) URL here")
        self.url_input.setFont(QFont("Segoe UI", 15))
        self.url_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.url_input.returnPressed.connect(self.fetch_qualities)
        url_row.addWidget(self.url_input, 3)
        self.paste_btn = QPushButton("Paste")
        self.paste_btn.setObjectName("paste")
        self.paste_btn.setCursor(Qt.PointingHandCursor)
        self.paste_btn.clicked.connect(lambda: self.url_input.setText(QApplication.clipboard().text()))
        url_row.addWidget(self.paste_btn)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("clear")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_all)
        url_row.addWidget(self.clear_btn)
        self.fetch_btn = QPushButton("Fetch Qualities")
        self.fetch_btn.setCursor(Qt.PointingHandCursor)
        self.fetch_btn.clicked.connect(self.fetch_qualities)
        url_row.addWidget(self.fetch_btn, 2)
        left_layout.addLayout(url_row)

        # Info row
        info_row = QHBoxLayout()
        self.title_label = QLabel("")
        self.title_label.setFont(QFont("Segoe UI", 15, QFont.Bold))
        self.title_label.setStyleSheet("color: #009688;")
        self.title_label.setAlignment(Qt.AlignLeft)
        self.title_label.setWordWrap(True)
        info_row.addWidget(self.title_label, 5)
        self.channel_label = QLabel("")
        self.channel_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.channel_label.setStyleSheet("color:#ffeb3b;")
        info_row.addWidget(self.channel_label, 2)
        self.duration_label = QLabel("")
        self.duration_label.setFont(QFont("Segoe UI", 14))
        self.duration_label.setStyleSheet("color:#b5b5b5;")
        info_row.addWidget(self.duration_label, 1)
        self.play_btn = QPushButton("▶️ Preview")
        self.play_btn.setToolTip("Play this video or Spotify track in your browser")
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setObjectName("preview")
        self.play_btn.setStyleSheet("QPushButton#preview {font-size:15px; background:#222; color:#ff8a65; border-radius:8px; padding:7px 10px;} QPushButton#preview:hover{background:#181824}")
        self.play_btn.clicked.connect(self.play_preview)
        info_row.addWidget(self.play_btn)
        left_layout.addLayout(info_row)

        # Quality box
        self.quality_box = QComboBox()
        self.quality_box.setEnabled(False)
        self.quality_box.setFont(QFont("Segoe UI", 14))
        self.quality_box.setStyleSheet("""
            QComboBox QAbstractItemView {
                background: #23243a;
                color: #fff;
                border-radius: 10px;
                selection-background-color: #ff1744;
                selection-color: #fff;
            }
        """)
        self.quality_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        left_layout.addWidget(self.quality_box)

        # Folder row
        folder_row = QHBoxLayout()
        self.folder_btn = QPushButton("Download Folder")
        self.folder_btn.setCursor(Qt.PointingHandCursor)
        self.folder_btn.setObjectName("folder")
        self.folder_btn.clicked.connect(self.choose_folder)
        folder_row.addWidget(self.folder_btn)
        self.folder_lbl = QLabel("Download Folder: " + self.folder)
        self.folder_lbl.setStyleSheet("color:#bbb; font-size:15px; font-weight:500;")
        self.folder_lbl.setWordWrap(True)
        self.folder_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        folder_row.addWidget(self.folder_lbl)
        self.copy_btn = QPushButton("📋")
        self.copy_btn.setObjectName("copy")
        self.copy_btn.setToolTip("Copy download folder path")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.folder))
        folder_row.addWidget(self.copy_btn)
        self.open_btn = QPushButton("📂")
        self.open_btn.setObjectName("open")
        self.open_btn.setToolTip("Open download folder")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.clicked.connect(lambda: os.startfile(self.folder) if sys.platform == "win32" else webbrowser.open(self.folder))
        self.history_btn = QPushButton("🕓 History")
        self.history_btn.setObjectName("history")
        self.history_btn.setCursor(Qt.PointingHandCursor)
        self.history_btn.setToolTip("Show download history")
        self.history_btn.clicked.connect(self.show_history)
        folder_row.addWidget(self.open_btn)
        folder_row.addWidget(self.history_btn)
        left_layout.addLayout(folder_row)

        # Download button
        self.download_btn = QPushButton("Download")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setFont(QFont("Segoe UI", 17, QFont.Bold))
        self.download_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setEnabled(False)
        left_layout.addWidget(self.download_btn)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        left_layout.addWidget(self.progress)

        # Status label
        self.status = QLabel("Ready.")
        self.status.setObjectName("status")
        self.status.setFont(QFont("Segoe UI", 15, QFont.DemiBold))
        self.status.setAlignment(Qt.AlignLeft)
        left_layout.addWidget(self.status)

        # About/help row
        about_row = QHBoxLayout()
        about_row.setAlignment(Qt.AlignLeft)
        self.mode_btn = QPushButton("🌙")
        self.mode_btn.setToolTip("Toggle Dark/Light mode")
        self.mode_btn.setCursor(Qt.PointingHandCursor)
        self.mode_btn.setObjectName("clear")
        self.mode_btn.clicked.connect(self.toggle_theme)
        self.help_btn = QPushButton("❓")
        self.help_btn.setToolTip("About / Help")
        self.help_btn.setCursor(Qt.PointingHandCursor)
        self.help_btn.setObjectName("clear")
        self.help_btn.clicked.connect(self.show_about)
        about_row.addWidget(QLabel(f"{APP_COPYRIGHT}  {APP_VERSION}"))
        about_row.addStretch(1)
        about_row.addWidget(self.mode_btn)
        about_row.addWidget(self.help_btn)
        left_layout.addLayout(about_row)
        left_layout.addStretch(1)

        # Right panel (thumbnail and details)
        right_panel = QFrame(self)
        right_panel.setObjectName("rightPanel")
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(32, 32, 32, 32)
        right_layout.setSpacing(18)

        # Add browser selection at the top of right panel
        browser_row = QHBoxLayout()
        browser_row.addWidget(QLabel("Browser for Cookies:"))
        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["Chrome", "Edge", "Firefox", "Brave"])
        self.browser_combo.setCurrentText("Chrome")
        self.browser_combo.setStyleSheet("""
            QComboBox {
                background: #353541;
                color: #ff8a65;
                font-size: 13px;
                border: 1.2px solid #444;
                padding: 5px 15px;
                border-radius: 8px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
            }
        """)
        browser_row.addWidget(self.browser_combo)
        right_layout.addLayout(browser_row)

        # Thumbnail label
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.thumbnail_label.setStyleSheet("border-radius: 15px; background: #222;")
        right_layout.addWidget(self.thumbnail_label, 10)
        right_layout.addStretch(1)

        # Playlist options (right panel, below thumbnail)
        playlist_row = QHBoxLayout()
        self.playlist_label = QLabel("")
        self.playlist_label.setFont(QFont("Segoe UI", 13))
        self.playlist_label.setStyleSheet("color:#ffd600;")
        self.playlist_btn = QPushButton("Playlist Options")
        self.playlist_btn.setCursor(Qt.PointingHandCursor)
        self.playlist_btn.setEnabled(False)
        self.playlist_btn.clicked.connect(self.select_playlist)
        playlist_row.addWidget(self.playlist_label)
        playlist_row.addWidget(self.playlist_btn)
        right_layout.addLayout(playlist_row)

        # Subtitle options (right panel, below playlist options)
        subtitle_row = QHBoxLayout()
        self.subtitle_label = QLabel("")
        self.subtitle_label.setFont(QFont("Segoe UI", 13))
        self.subtitle_label.setStyleSheet("color:#81d4fa;")
        self.subtitle_btn = QPushButton("Subtitle Options")
        self.subtitle_btn.setCursor(Qt.PointingHandCursor)
        self.subtitle_btn.setEnabled(False)
        self.subtitle_btn.clicked.connect(self.select_subtitle)
        subtitle_row.addWidget(self.subtitle_label)
        subtitle_row.addWidget(self.subtitle_btn)
        right_layout.addLayout(subtitle_row)

        right_layout.addStretch(1)

        main_layout.addWidget(left_panel, 3)
        main_layout.addWidget(right_panel, 2)

        # Responsive style
        self.setStyleSheet("""
        QWidget {
            background: #181824;
            color: #f4f4f4;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        QFrame#leftPanel {
            background: rgba(30,30,40,0.97);
            border-radius: 24px;
            border: 2px solid #222;
        }
        QFrame#rightPanel {
            background: rgba(40,40,50,0.97);
            border-radius: 24px;
            border: 2px solid #222;
        }
        QLineEdit, QComboBox {
            border-radius: 14px;
            border: 2px solid #444;
            background: #23243a;
            color: #fff;
            padding: 13px 22px;
            font-size: 16px;
        }
        QLineEdit:focus, QComboBox:focus {
            border: 2.2px solid #ff1744;
        }
        QPushButton {
            border-radius: 14px;
            font-weight: 600;
            font-size: 16px;
            background: qlineargradient(
                spread:pad, x1:0, y1:0, x2:1, y2:0,
                stop:0 #ff1744, stop:1 #ff8a65
            );
            color: #fff;
            padding: 13px 34px;
            border: 2px solid #444;
        }
        QPushButton#folder, QPushButton#copy, QPushButton#open, QPushButton#history {
            background: qlineargradient(
                spread:pad, x1:0, y1:0, x2:1, y2:0,
                stop:0 #009688, stop:1 #26d6a3
            );
            font-size: 15px;
            color: #fff;
            border: 2px solid #444;
        }
        QPushButton#clear, QPushButton#paste {
            background: #353541;
            color: #ff8a65;
            font-size: 13px;
            border: 1.2px solid #444;
        }
        QPushButton:hover {
            background: #f857a6;
            color: #fff;
            border: 2.2px solid #ff8a65;
        }
        QPushButton#clear:hover, QPushButton#paste:hover {
            background: #23243a;
        }
        QPushButton#history {
            background: #23243a;
            color: #fff176;
            font-size: 15px;
            border: 2px solid #444;
        }
        QLabel#status {
            color: #ffe082;
            font-size: 17px;
            border-radius: 9px;
            background: rgba(0,0,0,0.18);
            padding: 7px 19px;
        }
        QProgressBar {
            border-radius: 13px;
            background: #181824;
            height: 18px;
        }
        QProgressBar::chunk {
            border-radius: 13px;
            background: qlineargradient(
                spread:pad, x1:0, y1:0, x2:1, y2:0,
                stop:0 #ff1744, stop:1 #ff8a65
            );
        }
        """)

        self.current_formats = []
        self.fetched_title = ""
        self.fetched_thumbnail = ""
        self.available_subtitles = []
        self.selected_subtitle_langs = []
        self.embed_subs = False
        self.has_playlist = False
        self.playlist_entries = []
        self.playlist_mode = None
        self.playlist_range = None
        self.playlist_total = None

        # Add stretch to push everything up
        left_layout.addStretch(1)

        # Setup keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+V"), self).activated.connect(
            lambda: self.url_input.setText(QApplication.clipboard().text()))
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self.fetch_qualities)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.start_download)
        
        self.auto_focus()
        self.show()

    def on_proxy_checkbox_changed(self, state):
        try:
            self.use_proxy = bool(state)
            if not self.use_proxy:
                try:
                    self.status.setText("Disconnecting proxy...")
                    self.disable_system_proxy()
                    self.proxy_status = "disconnected"
                    self.status.setText("Proxy disconnected")
                    self.proxy_checkbox.setStyleSheet("")
                except Exception as e:
                    QMessageBox.warning(self, "Proxy Error", f"Failed to disable proxy: {e}")
                return

            reply = QMessageBox.question(
                self, "Proxy Setup",
                "Do you want to:\n\n"
                "1. Auto-find working proxy (Recommended)\n"
                "2. Enter proxy details manually?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Yes:  # Auto-find
                try:
                    if self.find_working_proxy():
                        self.enable_system_proxy(self.proxy)
                        self.proxy_status = "connected"
                        self.status.setText(f"✅ Connected via proxy: {self.proxy}")
                        self.proxy_checkbox.setStyleSheet("color: #4CAF50; font-weight: bold;")
                    else:
                        raise Exception("Could not find working proxy")
                except Exception as e:
                    QMessageBox.warning(self, "Auto Proxy Failed", 
                        f"Could not find working proxy automatically:\n{str(e)}\n\nTry manual entry?")
                if QMessageBox.Yes == QMessageBox.question(self, "Manual Entry?", "Would you like to enter proxy details manually?", 
                    QMessageBox.Yes | QMessageBox.No):
                    reply = QMessageBox.No  # Continue with manual entry
                else:
                    self.proxy_checkbox.setChecked(False)
                    return

            if reply == 1:  # Manual Entry
                # Define ProxyDialog if not already defined
                class ProxyDialog(QDialog):
                    def __init__(self, parent=None):
                        super().__init__(parent)
                        self.setWindowTitle("Proxy Settings")
                        self.setStyleSheet("""
                            QDialog {background: #23243a; color: #fff;}
                            QLabel, QLineEdit, QComboBox {font-size: 15px;}
                            QPushButton {background: #009688; color:#fff; border-radius: 8px; font-size: 13px; padding: 6px 18px;}
                        """)
                        vbox = QVBoxLayout(self)
                        vbox.addWidget(QLabel("Enter proxy address (e.g. http://ip:port or socks5://ip:port):"))
                        self.proxy_input = QLineEdit()
                        self.proxy_input.setPlaceholderText("Proxy URL")
                        vbox.addWidget(self.proxy_input)
                        vbox.addWidget(QLabel("Proxy type:"))
                        self.type_box = QComboBox()
                        self.type_box.addItems(["http", "https", "socks5"])
                        vbox.addWidget(self.type_box)
                        btn_row = QHBoxLayout()
                        ok = QPushButton("OK")
                        cancel = QPushButton("Cancel")
                        ok.clicked.connect(self.accept)
                        cancel.clicked.connect(self.reject)
                        btn_row.addWidget(ok)
                        btn_row.addWidget(cancel)
                        vbox.addLayout(btn_row)

                    def get_proxy_url(self):
                        return self.proxy_input.text().strip()

                    def get_proxy_type(self):
                        return self.type_box.currentText()

                proxy_dlg = ProxyDialog(self)
                if proxy_dlg.exec_() == QDialog.Accepted:
                    self.proxy = proxy_dlg.get_proxy_url()
                    self.proxy_type = proxy_dlg.get_proxy_type()
                    
                    if not self.proxy:
                        self.use_proxy = False
                        self.proxy_checkbox.setChecked(False)
                        return
                    
                    # First try to import requests
                    try:
                        import requests
                    except ImportError:
                        QMessageBox.warning(self, "Missing Dependency", 
                            "Please install the requests library:\npip install requests")
                        self.use_proxy = False
                        self.proxy_checkbox.setChecked(False)
                        return
                        
                    self.status.setText("Connecting to proxy...")
                    try:
                        if self.test_proxy_connection():
                            self.enable_system_proxy(self.proxy)
                            self.proxy_status = "connected"
                            self.status.setText("✅ Proxy connected successfully")
                            self.proxy_checkbox.setStyleSheet("color: #4CAF50; font-weight: bold;")
                        else:
                            raise Exception("Connection test failed")
                    except Exception as e:
                        self.use_proxy = False
                        self.proxy_checkbox.setChecked(False)
                        self.proxy_status = "error"
                        error_msg = f"Failed to connect to proxy:\n{str(e)}\nPlease check the proxy settings and try again."
                        QMessageBox.warning(self, "Proxy Error", error_msg)
            else:  # Cancel
                self.use_proxy = False
                self.proxy_checkbox.setChecked(False)
                return
        except Exception as e:
            self.use_proxy = False
            self.proxy_checkbox.setChecked(False)
            QMessageBox.critical(self, "Proxy Error", f"An error occurred while setting up proxy:\n{str(e)}")

    def get_public_proxy_list(self):
        """Get list of public proxies from multiple sources"""
        try:
            import requests
            import random
            
            proxies = []
            # Try multiple proxy sources
            sources = [
                "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
                "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
                "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list.txt"
            ]
            
            for source in sources:
                try:
                    response = requests.get(source, timeout=5)
                    if response.status_code == 200:
                        # Extract proxies with format ip:port
                        import re
                        found = re.findall(r'(\d+\.\d+\.\d+\.\d+):(\d+)', response.text)
                        for ip, port in found:
                            proxies.append(f"http://{ip}:{port}")
                except:
                    continue
                    
            # Shuffle proxies
            random.shuffle(proxies)
            return proxies[:20]  # Return top 20 proxies
        except:
            return []

    def find_working_proxy(self):
        """Automatically find a working proxy"""
        self.status.setText("Finding working proxy...")
        
        try:
            import requests
            import concurrent.futures
            
            def test_single_proxy(proxy_url):
                try:
                    proxies = {
                        "http": proxy_url,
                        "https": proxy_url
                    }
                    response = requests.get("http://www.google.com", 
                                         proxies=proxies,
                                         timeout=5,
                                         verify=False)
                    return proxy_url if response.status_code == 200 else None
                except:
                    return None

            # Get proxy list
            proxy_list = self.get_public_proxy_list()
            if not proxy_list:
                raise Exception("Could not fetch proxy list")
                
            # Test proxies in parallel
            working_proxies = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_proxy = {executor.submit(test_single_proxy, proxy): proxy 
                                 for proxy in proxy_list}
                
                for i, future in enumerate(concurrent.futures.as_completed(future_to_proxy)):
                    proxy = future_to_proxy[future]
                    self.status.setText(f"Testing proxy {i+1}/{len(proxy_list)}...")
                    
                    if result := future.result():
                        working_proxies.append(result)
                        break  # Found working proxy
                        
            if working_proxies:
                self.proxy = working_proxies[0]
                return True
            else:
                raise Exception("No working proxy found")
                
        except Exception as e:
            self.status.setText(f"Auto proxy failed: {str(e)}")
            return False

    def verify_proxy_format(self, proxy_url):
        """Verify proxy URL format and extract components"""
        try:
            import re
            pattern = r'^(https?|socks5)://(?:([^:@]+)(?::([^@]+))?@)?([^:]+):(\d+)/?$'
            match = re.match(pattern, proxy_url)
            if not match:
                raise ValueError("Invalid proxy URL format")
            
            proto, user, pwd, host, port = match.groups()
            port = int(port)
            if not (1 <= port <= 65535):
                raise ValueError(f"Invalid port number: {port}")
                
            return {
                'protocol': proto,
                'username': user,
                'password': pwd,
                'host': host,
                'port': port
            }
        except Exception as e:
            raise ValueError(f"Invalid proxy format: {str(e)}")

    def test_proxy_dns(self, host):
        """Test DNS resolution of proxy host"""
        try:
            import socket
            self.status.setText(f"Resolving proxy DNS for {host}...")
            socket.gethostbyname(host)
            return True
        except socket.gaierror:
            raise Exception(f"Could not resolve proxy host: {host}")

    def test_proxy_connection(self):
        """Test if proxy connection works with extended diagnostics"""
        try:
            import requests
            import socket
            
            # First validate proxy URL format
            proxy_info = self.verify_proxy_format(self.proxy)
            
            # Test DNS resolution
            self.test_proxy_dns(proxy_info['host'])
            
            # Test TCP connection
            self.status.setText(f"Testing connection to {proxy_info['host']}:{proxy_info['port']}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            if sock.connect_ex((proxy_info['host'], proxy_info['port'])) != 0:
                raise Exception(f"Could not establish TCP connection to {proxy_info['host']}:{proxy_info['port']}")
            sock.close()
            
            # Configure session with proxy
            session = requests.Session()
            session.proxies = {
                "http": self.proxy,
                "https": self.proxy
            }
            
            if proxy_info['protocol'] == 'socks5':
                try:
                    import socket
                    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    proxy_socket.connect((proxy_info['host'], proxy_info['port']))
                    proxy_socket.close()
                except Exception as e:
                    raise Exception(f"SOCKS5 connection failed: {str(e)}")
            
            # Test connectivity with multiple URLs and protocols
            test_urls = [
                "http://www.google.com",
                "https://www.cloudflare.com",
                "http://www.example.com",
                "https://api.ipify.org?format=json"  # Get public IP
            ]
            
            success = False
            error_details = []
            
            for url in test_urls:
                try:
                    self.status.setText(f"Testing proxy with {url}...")
                    response = session.get(url, timeout=5, verify=True)
                    
                    if response.status_code == 200:
                        if "ipify" in url:
                            ip_data = response.json()
                            self.proxy_ip = ip_data.get('ip', 'Unknown')
                            self.status.setText(f"Connected via: {self.proxy_ip}")
                        success = True
                        break
                except Exception as e:
                    error_details.append(f"{url}: {str(e)}")
                    continue
            
            if not success:
                raise Exception("Could not access internet through proxy.\nTried:\n" + "\n".join(error_details))
                
            # Success - proxy is working
            self.proxy_type = proxy_info['protocol']
            return True
            
        except Exception as e:
            self.status.setText(f"Proxy test failed: {str(e)}")
            raise

    def enable_system_proxy(self, proxy_addr):
        """Enable system proxy settings with backup and restore capabilities"""
        try:
            # Store current settings for potential restore
            self.previous_proxy_settings = self.get_current_proxy_settings()
            
            if sys.platform == "win32":
                try:
                    # Try to run netsh with elevated privileges
                    import ctypes
                    if ctypes.windll.shell32.IsUserAnAdmin() == 0:
                        # Re-run with admin rights
                        ctypes.windll.shell32.ShellExecuteW(None, "runas", "netsh", f"winhttp set proxy {proxy_addr}", None, 1)
                    else:
                        subprocess.run(
                            ["netsh", "winhttp", "set", "proxy", proxy_addr],
                            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        )
                    
                    # Set Internet Options proxy
                    import winreg
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                        0, winreg.KEY_WRITE) as internet_settings:
                        
                        # Backup old settings
                        try:
                            old_proxy = winreg.QueryValueEx(internet_settings, "ProxyServer")[0]
                            old_enable = winreg.QueryValueEx(internet_settings, "ProxyEnable")[0]
                            self.previous_windows_settings = {
                                "ProxyServer": old_proxy,
                                "ProxyEnable": old_enable
                            }
                        except:
                            self.previous_windows_settings = None
                            
                        # Set new settings
                        winreg.SetValueEx(internet_settings, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                        winreg.SetValueEx(internet_settings, "ProxyServer", 0, winreg.REG_SZ, proxy_addr)
                        # Disable proxy bypass for local addresses
                        winreg.SetValueEx(internet_settings, "ProxyOverride", 0, winreg.REG_SZ, "<local>")
                    
                    # Additional Windows proxy settings (optional but helpful)
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Internet Settings\Connections",
                        0, winreg.KEY_WRITE) as connections:
                        # Save default connection settings
                        winreg.SetValueEx(connections, "DefaultConnectionSettings", 0, winreg.REG_BINARY, b"")
                        winreg.SetValueEx(connections, "SavedLegacySettings", 0, winreg.REG_BINARY, b"")
                    
                except Exception as e:
                    error_msg = (
                        f"Failed to set Windows proxy:\n{str(e)}\n"
                        "Tips:\n"
                        "1. Run as Administrator\n"
                        "2. Check proxy format\n"
                        "3. Verify proxy server\n"
                        "4. Try different proxy\n"
                        "5. Check Windows settings"
                    )
                    QMessageBox.warning(self, "Proxy Error", error_msg)
                    raise
            
            # Set environment variables for all platforms
            os.environ["HTTP_PROXY"] = proxy_addr
            os.environ["HTTPS_PROXY"] = proxy_addr
            os.environ["FTP_PROXY"] = proxy_addr
            os.environ["SOCKS_PROXY"] = proxy_addr
            os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
            
            # For Linux/Mac additional settings
            if sys.platform in ["linux", "darwin"]:
                # Try to set GNOME proxy (Linux)
                try:
                    if sys.platform == "linux":
                        subprocess.run([
                            "gsettings", "set", "org.gnome.system.proxy", "mode", "manual"
                        ], check=True)
                        subprocess.run([
                            "gsettings", "set", "org.gnome.system.proxy.http", "host", proxy_info['host']
                        ], check=True)
                        subprocess.run([
                            "gsettings", "set", "org.gnome.system.proxy.http", "port", str(proxy_info['port'])
                        ], check=True)
                except:
                    pass  # Ignore if GNOME is not available
                
            return True
            
        except Exception as e:
            self.status.setText(f"Failed to enable proxy: {str(e)}")
            # Try to restore previous settings
            self.restore_proxy_settings()
            raise
            
    def get_current_proxy_settings(self):
        """Get current proxy settings for backup"""
        settings = {
            "env": {
                "HTTP_PROXY": os.environ.get("HTTP_PROXY", ""),
                "HTTPS_PROXY": os.environ.get("HTTPS_PROXY", ""),
                "FTP_PROXY": os.environ.get("FTP_PROXY", ""),
                "SOCKS_PROXY": os.environ.get("SOCKS_PROXY", ""),
                "NO_PROXY": os.environ.get("NO_PROXY", "")
            }
        }
        
        if sys.platform == "win32":
            try:
                import winreg
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                    0, winreg.KEY_READ) as key:
                    settings["windows"] = {
                        "ProxyEnable": winreg.QueryValueEx(key, "ProxyEnable")[0],
                        "ProxyServer": winreg.QueryValueEx(key, "ProxyServer")[0]
                    }
            except:
                settings["windows"] = None
                
        return settings
        
    def restore_proxy_settings(self):
        """Restore previous proxy settings"""
        if hasattr(self, 'previous_proxy_settings'):
            try:
                # Restore environment variables
                for key, value in self.previous_proxy_settings["env"].items():
                    if value:
                        os.environ[key] = value
                    elif key in os.environ:
                        del os.environ[key]
                
                # Restore Windows settings
                if sys.platform == "win32" and self.previous_proxy_settings.get("windows"):
                    win_settings = self.previous_proxy_settings["windows"]
                    import winreg
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                        0, winreg.KEY_WRITE) as key:
                        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD,
                                        win_settings["ProxyEnable"])
                        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ,
                                        win_settings["ProxyServer"])
                
                self.status.setText("Previous proxy settings restored")
                return True
                
            except Exception as e:
                self.status.setText(f"Failed to restore proxy settings: {str(e)}")
                return False

    def disable_system_proxy(self):
        if sys.platform == "win32":
            try:
                # Try to run with elevated privileges
                import ctypes
                if ctypes.windll.shell32.IsUserAnAdmin() == 0:
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", "netsh", "winhttp reset proxy", None, 1)
                else:
                    subprocess.run(
                        ["netsh", "winhttp", "reset", "proxy"],
                        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
            except Exception as e:
                QMessageBox.warning(self, "Proxy Error", f"Failed to disable proxy: {e}")
        else:
            QMessageBox.warning(self, "Proxy Error", "Auto proxy only supported on Windows.")

    def setup_styles(self):
        if self.theme_dark:
            self.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 #23243a, stop:1 #181824
                );
                color: #f4f4f4;
            }
            QFrame {
                border-radius: 30px;
                background: rgba(30,30,40,0.93);
                border: 2.5px solid rgba(255,255,255,0.08);
                box-shadow: 0 8px 54px #00000088;
            }
            QLineEdit, QComboBox {
                border-radius: 14px;
                border: 1.7px solid #444;
                background: #20232a;
                color: #fff;
                padding: 13px 22px;
                font-size: 18px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 2.2px solid #ff1744;
            }
            QPushButton {
                border-radius: 14px;
                font-weight: 600;
                font-size: 16px;
                background: qlineargradient(
                    spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff1744, stop:1 #ff8a65
                );
                color: #fff;
                padding: 13px 34px;
                border: 2px solid #444;
            }
            QPushButton#folder, QPushButton#copy, QPushButton#open, QPushButton#history {
                background: qlineargradient(
                    spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #009688, stop:1 #26d6a3
                );
                font-size: 15px;
                color: #fff;
                border: 2px solid #444;
            }
            QPushButton#clear, QPushButton#paste {
                background: #353541;
                color: #ff8a65;
                font-size: 13px;
                border: 1.2px solid #444;
            }
            QPushButton:hover {
                background: #f857a6;
                color: #fff;
                border: 2.2px solid #ff8a65;
            }
            QPushButton#clear:hover, QPushButton#paste:hover {
                background: #23243a
                background: #23243a;
            }
            QPushButton#history {
                background: #23243a;
                color: #fff176;
                font-size: 15px;
                border: 2px solid #444;
            }
            QLabel#status {
                color: #ffe082;
                font-size: 15px;
                border-radius: 9px;
                background: #ffd8c2;
                padding: 7px 19px;
            }
            QProgressBar {
                border-radius: 13px;
                background: #ededed;
                height: 18px;
            }
            QProgressBar::chunk {
                border-radius: 13px;
                background: qlineargradient(
                    spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff1744, stop:1 #ff8a65
                );
            }
            """)
        else:
            self.setStyleSheet("""
            QWidget {background:#f5f6fa;color:#181824;}
            QFrame {background:#fff; border-radius:30px; border:2.5px solid #e0e0e0;}
            QLineEdit, QComboBox {background:#f9f9fa;color:#23243a;border:1.5px solid #bbb;}
            QPushButton {
                background: #fff;
                color: #ff1744;
                border: 1.5px solid #ff1744;
                border-radius: 14px;
                font-weight: 600;
                font-size: 16px;
                padding: 13px 34px;
            }
            QPushButton#folder, QPushButton#copy, QPushButton#open, QPushButton#history {
                background: qlineargradient(
                    spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #009688, stop:1 #26d6a3
                );
                font-size: 15px;
                color: #fff;
                border: 1.5px solid #bbb;
            }
            QPushButton#clear, QPushButton#paste {
                background: #ededed;
                color: #ff8a65;
                font-size: 13px;
                border: 1.2px solid #bbb;
            }
            QPushButton:hover {
                background: #ff8a65;
                color: #fff;
                border: 2.2px solid #ff1744;
            }
            QPushButton#clear:hover, QPushButton#paste:hover {
                background: #23243a;
            }
            QPushButton#history {
                background: #f9f9fa;
                color: #ff1744;
                font-size: 15px;
                border: 1.5px solid #bbb;
            }
            QLabel#status {
                color: #ff1744;
                font-size: 15px;
                border-radius: 9px;
                background: #ffd8c2;
                padding: 7px 19px;
            }
            QProgressBar {
                border-radius: 13px;
                background: #ededed;
                height: 18px;
            }
            QProgressBar::chunk {
                border-radius: 13px;
                background: qlineargradient(
                    spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff1744, stop:1 #ff8a65
                );
            }
            """)

    def auto_focus(self):
        self.url_input.setFocus()

    def dragEnterEvent(self, event):
        url = event.mimeData().text()
        if event.mimeData().hasText() and (
            "youtube.com" in url.lower() or "youtu.be" in url.lower() or 
            "spotify.com" in url.lower() or "soundcloud.com" in url.lower()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.url_input.setText(event.mimeData().text())
        self.url_input.setFocus()

    def play_preview(self):
        url = self.url_input.text().strip()
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def toggle_theme(self):
        self.theme_dark = not self.theme_dark
        self.setup_styles()

    def resizeEvent(self, event):
        if hasattr(self, "bg_label"):
            pix = QPixmap("bg.jpg") if os.path.exists("bg.jpg") else QPixmap(self.width(), self.height())
            if pix.isNull():
                pix.fill(QColor(34, 40, 49))
            self.bg_label.setPixmap(pix.scaled(self.width(), self.height(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            self.bg_label.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, "thumbnail_label") and self.thumbnail_label.pixmap():
            width = max(220, int(self.width() * 0.28))
            height = max(120, int(self.height() * 0.33))
            self.thumbnail_label.setPixmap(self.thumbnail_label.pixmap().scaled(
                width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        super().resizeEvent(event)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Download Folder", self.folder)
        if folder:
            self.folder = folder
            self.folder_lbl.setText("Download Folder: " + self.folder)

    def fetch_qualities(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a video or Spotify URL!")
            return    
        self.status.setText("Fetching available qualities...")
        self.fetch_btn.setEnabled(False)
        self.quality_box.clear()
        self.quality_box.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.title_label.setText("")
        self.channel_label.setText("")
        self.duration_label.setText("")
        self.progress.setValue(0)
        self.thumbnail_label.clear()
        self.subtitle_label.setText("")
        self.subtitle_btn.setEnabled(False)
        self.available_subtitles = []
        self.selected_subtitle_langs = []
        self.embed_subs = False
        self.playlist_label.setText("")
        self.playlist_btn.setEnabled(False)
        self.has_playlist = False
        self.playlist_entries = []
        self.playlist_mode = None
        self.playlist_range = None
        self.playlist_total = None
        self.fetch_thread = FetchFormatsThread(url)
        self.fetch_thread.finished.connect(self.qualities_fetched)
        self.fetch_thread.error.connect(self.fetch_error)
        self.fetch_thread.start()

    def qualities_fetched(self, qual_list, title, thumbnail_url, channel, duration,
                         lang_list, subtitles, automatic_captions, has_playlist, playlist_entries):
        self.current_formats = qual_list
        self.fetched_title = title
        self.fetched_thumbnail = thumbnail_url
        self.quality_box.clear()
        for label, fmtid, stream_type in qual_list:
            self.quality_box.addItem(label, (fmtid, stream_type))
        self.quality_box.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.status.setText("Select a quality and click Download.")
        self.title_label.setText(f"<b>Title:</b> <span style='color:#1de9b6'>{title}</span>")
        self.channel_label.setText(f"{channel}" if channel else "")
        self.duration_label.setText(f"{duration}" if duration else "")
        self.fetch_btn.setEnabled(True)
        if thumbnail_url:
            try:
                img_data = urllib.request.urlopen(thumbnail_url).read()
                pix = QPixmap()
                pix.loadFromData(img_data)
                width = max(220, int(self.width() * 0.28))
                height = max(120, int(self.height() * 0.33))
                self.thumbnail_label.setPixmap(pix.scaled(
                    width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except Exception:
                self.thumbnail_label.setText("No thumbnail")
        else:
            self.thumbnail_label.setText("No thumbnail")
        self.available_subtitles = lang_list
        if lang_list:
            self.subtitle_label.setText(f"✓ Subtitles available ({len(lang_list)}): {', '.join(l for l, _ in lang_list[:3])}" + 
                                      ("..." if len(lang_list) > 3 else ""))
            self.subtitle_btn.setEnabled(True)
            self.subtitle_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #81C784);
                    color: white;
                }
            """)
            self.selected_subtitle_langs = []
            self.embed_subs = False
        else:
            self.subtitle_label.setText("No subtitles available.")
            self.subtitle_btn.setEnabled(False)
            self.selected_subtitle_langs = []
            self.embed_subs = False
        self.has_playlist = has_playlist
        self.playlist_entries = playlist_entries
        self.playlist_total = len(playlist_entries) if has_playlist and playlist_entries else 1
        if has_playlist and playlist_entries:
            self.playlist_label.setText(f"Playlist detected ({len(playlist_entries)} videos)")
            self.playlist_btn.setEnabled(True)
            self.playlist_mode = "playlist"
            self.playlist_range = None
        else:
            self.playlist_label.setText("")
            self.playlist_btn.setEnabled(False)
            self.playlist_mode = None
            self.playlist_range = None
    # Removed warning about thumbnail embedding support for mp4/mkv formats

    def fetch_error(self, err):
        self.status.setText("Fetch error.")
        self.fetch_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", str(err))

    def select_subtitle(self):
        if not self.available_subtitles:
            QMessageBox.information(self, "No subtitles", "No subtitles available for this video.")
            return
        
        # First check if ffmpeg supports subtitle embedding
        try:
            ffmpeg_check = subprocess.run(["ffmpeg", "-codecs"], capture_output=True, text=True)
            has_subtitle_support = "ass" in ffmpeg_check.stdout.lower() and "srt" in ffmpeg_check.stdout.lower()
            if not has_subtitle_support:
                QMessageBox.warning(self, "FFmpeg Warning", 
                    "Your FFmpeg installation might not support subtitle embedding. "
                    "Subtitles will be downloaded as separate files.")
        except Exception:
            pass  # Don't block subtitle selection if ffmpeg check fails
            
        dlg = SubtitleDialog(self.available_subtitles, self)
        if dlg.exec_() == QDialog.Accepted:
            embed, langs = dlg.get_selection()
            if not langs:
                self.subtitle_label.setText("No subtitles selected.")
                self.embed_subs = False
                self.selected_subtitle_langs = []
                return
                
            self.embed_subs = embed and bool(langs)
            fmtid, _ = self.quality_box.currentData() if self.quality_box.currentData() else (None, None)
            if fmtid and not any(x in fmtid for x in ["mp4", "mkv"]):
                if self.embed_subs:
                    QMessageBox.warning(self, "Warning", "Selected format does not support subtitle embedding. Only mp4/mkv support embedding. Subtitles will be downloaded, not embedded.")
                    self.embed_subs = False
            if langs:
                if self.embed_subs:
                    self.subtitle_label.setText(f"Will embed: {', '.join(langs)}")
                else:
                    self.subtitle_label.setText(f"Will download: {', '.join(langs)} subtitles")
            else:
                self.subtitle_label.setText("No subtitles selected.")
        else:
            self.subtitle_label.setText("No subtitles selected.")

    def select_playlist(self):
        if not self.has_playlist or not self.playlist_entries:
            return
        dlg = PlaylistDialog(self.playlist_entries, self)
        if dlg.exec_() == QDialog.Accepted:
            mode, rng = dlg.get_selection()
            self.playlist_mode = mode
            self.playlist_range = rng
            if mode == "playlist":
                self.playlist_label.setText(f"Playlist: All {len(self.playlist_entries)} videos")
                self.playlist_total = len(self.playlist_entries)
            elif mode == "range":
                self.playlist_label.setText(f"Playlist: Videos {rng[0]}–{rng[1]}")
                self.playlist_total = rng[1] - rng[0] + 1
            elif mode == "single":
                self.playlist_label.setText(f"Playlist: Video #{rng[0]}")
                self.playlist_total = 1
        else:
            self.playlist_label.setText(f"Playlist: All {len(self.playlist_entries)} videos")
            self.playlist_mode = "playlist"
            self.playlist_range = None
            self.playlist_total = len(self.playlist_entries)

    def start_download(self):
        url = self.url_input.text().strip()
        if not url or not self.current_formats:
            QMessageBox.warning(self, "No quality selected", "Please fetch qualities and select one!")
            return
        fmtid, stream_type = self.quality_box.currentData()
        self.progress.setValue(0)
        self.status.setText("Starting download...")
        self.download_btn.setEnabled(False)
        self.fetch_btn.setEnabled(False)
        self.url_input.setEnabled(False)  # Disable URL input during download
        # Proxy is now system-wide, no need to pass to yt-dlp/spotdl
        try:
            self.thread = DownloadThread(
                url, self.folder, fmtid, stream_type, self.fetched_title, self.fetched_thumbnail,
                embed_subs=self.embed_subs, subtitle_langs=self.selected_subtitle_langs,
                playlist_range=self.playlist_range,
                playlist_mode=self.playlist_mode,
                playlist_total=self.playlist_total,
                force_aac=False,
                proxy=None,
                use_vpn=self.use_vpn
            )
            self.thread.progress.connect(self.update_progress)
            self.thread.finished.connect(self.download_finished)
            self.thread.error.connect(self.download_error)
            self.thread.start()
        except Exception as e:
            QMessageBox.critical(self, "Thread Error", f"Failed to start download thread:\n{e}")
            self.download_btn.setEnabled(True)
            self.fetch_btn.setEnabled(True)

    def update_progress(self, pct, msg):
        if pct == 0:
            self.progress.setMaximum(0)
        else:
            self.progress.setMaximum(100)
            self.progress.setValue(pct)
        self.status.setText(msg)

    def download_finished(self, msg, filename, history_entry):
        self.status.setText(msg)
        self.progress.setMaximum(100)
        self.progress.setValue(100)
        self.download_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self.url_input.setEnabled(True)  # Re-enable URL input
        if isinstance(history_entry, dict) and history_entry.get("playlist"):
            entries = history_entry["entries"]
            file_count = len(entries)
            first_file = entries[0]["filepath"] if entries else filename
            if file_count > 1:
                QMessageBox.information(self, "Playlist Download Complete",
                    f"Downloaded {file_count} videos.\nFirst file:\n{os.path.basename(first_file)}\nLocation:\n{first_file}")
            elif file_count == 1:
                QMessageBox.information(self, "Download Complete",
                    f"Downloaded:\n{os.path.basename(first_file)}\nLocation:\n{first_file}")
            else:
                QMessageBox.warning(self, "Done", "No files found, but download reported as complete.")
        elif filename and os.path.exists(filename):
            size = human_size(os.path.getsize(filename))
            QMessageBox.information(self, "Download Complete",
                f"Downloaded:\n{os.path.basename(filename)}\nSize: {size}\nLocation:\n{filename}")
        else:
            QMessageBox.warning(self, "Done", "No file found, but download reported as complete.")

    def download_error(self, err):
        self.status.setText("Error.")
        self.download_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", str(err))

    def clear_all(self):
        self.url_input.clear()
        self.quality_box.clear()
        self.quality_box.setEnabled(False)
        self.title_label.setText("")
        self.channel_label.setText("")
        self.duration_label.setText("")
        self.thumbnail_label.clear()
        self.subtitle_label.setText("")
        self.subtitle_btn.setEnabled(False)
        self.playlist_label.setText("")
        self.playlist_btn.setEnabled(False)
        self.status.setText("Ready.")
        self.available_subtitles = []
        self.selected_subtitle_langs = []
        self.embed_subs = False
        self.has_playlist = False
        self.playlist_entries = []
        self.playlist_mode = None
        self.playlist_range = None
        self.playlist_total = None

    def show_about(self):
        txt = (
            f"<b>{APP_TITLE}</b> {APP_VERSION}<br>"
            f"{APP_COPYRIGHT}<br><br>"
            "Features:<ul>"
            "<li>Drag & drop YouTube/Spotify links</li>"
            "<li>Paste, clear, preview video or song</li>"
            "<li>Copy/open download folder</li>"
            "<li><b>History</b> of all downloads</li>"
            "<li>Download with subtitles (if available)</li>"
            "<li>Playlist download/range selection</li>"
            "<li>Dark/Light mode toggle</li>"
            "<li>Keyboard navigation, Tab, Enter</li>"
            "<li>Modern, glass-morphism layout</li></ul>"
            "<b>Shortcuts:</b><br>"
            "<ul><li><b>Ctrl+V</b>: Paste link<br>"
            "<li><b>Enter</b>: Fetch Qualities (when input focused)<br>"
            "<li><b>Tab</b>: Next field/button</li></ul>"
            "Powered by <b>yt-dlp</b>, <b>spotdl</b> and <b>PyQt5</b>.<br>"
            "<br>For issues/feedback, contact <b>Alexx993</b>."
        )
        QMessageBox.information(self, "About / Help", txt)

    def show_history(self):
        dlg = HistoryDialog(self)
        dlg.exec_()

if __name__ == '__main__':
    try:
        import yt_dlp
    except ImportError:
        print("Required 'yt-dlp' is not installed. Run:\npip install -U yt-dlp")
        sys.exit(1)
    try:
        import spotdl
    except ImportError:
        print("For Spotify downloads, 'spotdl' is required. Run:\npip install spotdl")
    import shutil
    if not shutil.which("ffmpeg"):
        print("Required 'ffmpeg' is not found in PATH. Install it and try again.")
        sys.exit(1)
    app = QApplication(sys.argv)
    w = YTDownloader()
    w.show()
    sys.exit(app.exec_())
