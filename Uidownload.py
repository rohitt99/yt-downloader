import sys, os, subprocess, json, urllib.request, webbrowser, datetime, re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QMessageBox, QFileDialog, QHBoxLayout, QProgressBar, QComboBox, QFrame, QSizePolicy,
    QDialog, QListWidget, QListWidgetItem, QAbstractItemView, QTextEdit, QCheckBox, QSpinBox, QGraphicsBlurEffect,
    QScrollArea, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QCoreApplication, QPropertyAnimation, QRect
from PyQt5.QtGui import QIcon, QPixmap, QFont, QColor, QKeySequence
from PyQt5.QtGui import QDesktopServices 
from PyQt5.QtWidgets import QShortcut, QGraphicsDropShadowEffect

# --- Global constants ---
APP_TITLE = "YT & Spotify Downloader"
APP_COPYRIGHT = "© 2025 ROHIT"
APP_VERSION = "v1.3" # The current version of the application.

try:
    from packaging import version as packaging_version
except ImportError:
    print("Required 'packaging' library not found. Please run: pip install packaging")
    sys.exit(1)

try:
    import matplotlib
    matplotlib.use('Qt5Agg') # Set the backend for PyQt5
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    print("Matplotlib not found, analytics dashboard will be disabled. Run: pip install matplotlib")
    MATPLOTLIB_AVAILABLE = False

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

def get_app_data_dir():
    """Returns the platform-specific, persistent application data directory."""
    APP_NAME = "YTSpotifyDownloader" # A safe name for a folder
    if sys.platform == "win32":
        return os.path.join(os.environ['APPDATA'], APP_NAME)
    elif sys.platform == "darwin": # macOS
        return os.path.join(os.path.expanduser('~/Library/Application Support'), APP_NAME)
    else: # Linux and other Unix-like
        return os.path.join(os.path.expanduser('~/.config'), APP_NAME)

APP_DATA_DIR = get_app_data_dir()
os.makedirs(APP_DATA_DIR, exist_ok=True) # Ensure the directory exists on startup
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")
HISTORY_FILE = os.path.join(APP_DATA_DIR, "download_history.json")

# --- Configuration Management ---
def load_config():
    """Loads configuration from config.json."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass  # Corrupted file, return default
    # Default config
    return {
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_notifications_enabled": False,
        "download_folder": os.path.join(os.path.expanduser("~"), "Downloads")
    }

def save_config(config):
    """Saves configuration to config.json."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def send_telegram_notification(entry_data):
    """Sends a professional, aesthetic, and rich download notification to a Telegram chat."""
    config = load_config()
    if not config.get("telegram_notifications_enabled") or not config.get("telegram_bot_token") or not config.get("telegram_chat_id"):
        print("[Telegram] Notifications disabled or not configured. Skipping.")
        return
 
    # --- Start of Rewritten Function ---
    try:
        data_to_send = {}
        def escape_html(text):
            """Escapes characters for Telegram's HTML parser."""
            if not isinstance(text, str):
                text = str(text)
            return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # 1. Gather all data safely
        title = entry_data.get('title', 'N/A')
        source_url = entry_data.get('url', '')
        download_type = entry_data.get('type', 'N/A')
        file_format = entry_data.get('format', '').strip('[]') or 'N/A'
        download_datetime_iso = entry_data.get('datetime')
        filepath = entry_data.get('filepath')
        
        # Use a more stable jpg thumbnail if available, instead of webp
        thumbnail_url = entry_data.get('thumbnail', '')
        thumbnail_url = thumbnail_url.replace('_webp', '').replace('.webp', '.jpg')

        # 2. Process and format the data
        file_size = "N/A"
        directory = "N/A"
        if filepath and os.path.exists(filepath) and os.path.isfile(filepath):
            file_size = human_size(os.path.getsize(filepath))
            directory = os.path.dirname(filepath)

        download_date_str = ""
        if download_datetime_iso:
            dt_obj = datetime.datetime.fromisoformat(download_datetime_iso)
            download_date_str = dt_obj.strftime("%d/%m/%Y %I:%M %p")

        # 3. Build the caption with proper HTML escaping for every dynamic part
        # This is the most critical part to prevent errors.
        base_caption_len = 350 # Approximate length of the static parts of the caption
        caption = (
            f"✨ <b>𝕯𝖔𝖜𝖓𝖑𝖔𝖆𝖉 𝕮𝖔𝖒𝖕𝖑𝖊𝖙𝖊</b> ✨\n\n"
            f"🎬  <b><i>{escape_html(title)}</i></b>\n\n"
            f"﹌﹌﹌﹌﹌﹌❀˖°﹌﹌﹌﹌﹌﹌❀˖°﹌﹌﹌﹌﹌﹌❀˖°\n"
            f"🌸 <b>𝑻𝒀𝑷𝑬</b>: <code>{escape_html(download_type)} ({escape_html(file_format)})</code>\n"
            f"💞 <b>𝑺𝑰𝒁𝑬</b>: <code>{escape_html(file_size)}</code>\n"
            f"🪷 <b>𝑫𝑶𝑾𝑵𝑳𝑶𝑨𝑫𝑬𝑫 𝑶𝑵</b>: <code>{escape_html(download_date_str)}</code>\n"
            f"🌺 <b>𝑺𝑶𝑼𝑹𝑪𝑬</b>: <a href=\"{escape_html(source_url)}\">Click Here</a>\n"
            f"﹌﹌﹌﹌﹌﹌❀˖°﹌﹌﹌﹌﹌﹌❀˖°﹌﹌﹌﹌﹌﹌❀˖°\n\n"
            f"🌹  <b>𝐒𝐀𝐕𝐄𝐃 𝐓𝐎</b>:\n<code>{escape_html(directory)}</code>"
        )

        # Telegram API limit for photo captions is 1024 characters.
        if len(caption) > 1024:
            # Truncate the title if the caption is too long
            overflow = len(caption) - 1024
            truncated_title = title[:-(overflow + 5)] + "..." # Truncate and add ellipsis
            caption = (
                f"✨ <b>Download Complete</b> ✨\n\n"
                f"🎬  <b><i>{escape_html(truncated_title)}</i></b>\n\n"
                f"----------------------------------------\n"
                f"📦  <b>Type</b>: <code>{escape_html(download_type)} ({escape_html(file_format)})</code>\n"
                f"💾  <b>Size</b>: <code>{escape_html(file_size)}</code>\n"
                f"🗓  <b>Downloaded On</b>: <code>{escape_html(download_date_str)}</code>\n"
                f"🔗  <b>Source</b>: <a href=\"{escape_html(source_url)}\">Click Here</a>\n"
                f"----------------------------------------\n\n"
                f"📁  <b>Saved To</b>:\n<code>{escape_html(directory)}</code>"
            )

 
        # Use sendPhoto if thumbnail exists, otherwise sendMessage
        api_method = "sendPhoto" if thumbnail_url and thumbnail_url.startswith('http') else "sendMessage" # Check for valid URL
        url = f"https://api.telegram.org/bot{config['telegram_bot_token']}/{api_method}"
     
        data_to_send = {
            'chat_id': config['telegram_chat_id'],
            'parse_mode': 'HTML'
        }
        if api_method == 'sendPhoto':
            data_to_send['photo'] = thumbnail_url
            data_to_send['caption'] = caption
        else:
            data_to_send['text'] = caption
     
        # We need to build the request properly to handle the complex caption
        post_data = urllib.parse.urlencode(data_to_send).encode('utf-8') # This handles all characters correctly
        req = urllib.request.Request(url, data=post_data, method='POST') # Explicitly POST
        urllib.request.urlopen(req, timeout=10) # Add a timeout

    except Exception as e:
        print(f"--- TELEGRAM NOTIFICATION FAILED ---")
        print(f"Error: {e}")
        # Check if data_to_send was populated before the error
        if 'chat_id' in locals().get('data_to_send', {}):
            failed_data_summary = data_to_send.copy()
            failed_data_summary.pop('caption', None)
            failed_data_summary.pop('text', None)
            print(f"Data sent (summary): {failed_data_summary}")
        print(f"--- END OF TELEGRAM ERROR ---")

def get_download_type_from_url(url):
    """Extracts a user-friendly name from a URL (e.g., YouTube, Vimeo, Web)."""
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc.lower()

        if "youtube.com" in netloc or "youtu.be" in netloc:
            return "YouTube"
        if "spotify.com" in netloc:
            return "Spotify"

        # Remove 'www.' if it exists
        if netloc.startswith('www.'):
            netloc = netloc[4:]

        # Get the first part of the domain and capitalize it
        domain_name = netloc.split('.')[0]
        return domain_name.capitalize() if domain_name else "Web"
    except Exception:
        return "Web"

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

def get_language_name(code):
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
    return lang_names.get(code.split('-')[0], code)

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
            name = get_language_name(lang)
            # Check if subtitle has multiple formats
            formats = [s.get('ext', 'unknown') for s in subs]
            formats_str = f" [{', '.join(set(formats))}]" if formats else ""
            lang_list.append((lang, f"{name} (manual){formats_str}"))
            
    if automatic_captions:
        for lang, subs in automatic_captions.items():
            name = lang_names.get(lang.split('-')[0], lang)
            name = get_language_name(lang)
            if not any(l[0] == lang for l in lang_list):  # Avoid duplicates
                formats = [s.get('ext', 'unknown') for s in subs]
                formats_str = f" [{', '.join(set(formats))}]" if formats else ""
                lang_list.append((lang, f"{name} (auto-generated){formats_str}"))
    
    # Sort by manual subs first, then by language name
    return sorted(
    lang_list,
    key=lambda x: (
        'auto' in x[1],  # manual before auto
        lang_names.get(x[0].split('-')[0], x[0])  # sort by language name
    )
)

class FetchFormatsThread(QThread):
    finished = pyqtSignal(list, str, str, str, str, list, dict, dict, bool, list)
    finished = pyqtSignal(list, str, str, str, str, list, dict, dict, bool, list, list)
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
                self.finished.emit(qual_list, title, thumbnail, channel, duration, [], {}, {}, has_playlist, playlist_entries, [])
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
            
            # Extract audio languages (Dubs)
            audio_langs = set()
            for f in formats:
                if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                    lng = f.get('language')
                    if lng:
                        audio_langs.add(lng)
            audio_lang_list = sorted([(l, get_language_name(l)) for l in audio_langs], key=lambda x: x[1])

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
                    lang_list, subtitles, automatic_captions, has_playlist, playlist_entries, audio_lang_list
                )
        except Exception as e:
            self.error.emit(f"Error fetching formats: {e}")

class DownloadThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str, str, dict)
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, url, folder, format_id, stream_type, title, thumbnail_url,
                 embed_subs=False, subtitle_langs=None, playlist_range=None, playlist_mode=None, playlist_total=None, force_aac=False, proxy=None, use_vpn=False, trim_args=None):
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
        self.trim_args = trim_args
        self._is_cancelled = False
        self.process = None
        self.partial_files = set()

    def cancel(self):
        """Signals the thread to cancel the download."""
        self._is_cancelled = True
        if self.process:
            self.process.terminate()

    def run(self):
        start_time = datetime.datetime.now()
        try:
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
                self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                percent = 0
                filename = None
                all_output = ""
                for line in self.process.stdout:
                    all_output += line
                    if self._is_cancelled:
                        break

                    # Find partial files for cleanup
                    if "%" in line:
                        match = re.search(r'(\d{1,3}\.\d+)%', line)
                        if match:
                            percent = int(float(match.group(1)))
                            self.progress.emit(percent, f"Downloading... {percent}%")
                    if "Downloaded:" in line or "Saved:" in line:
                        part = line.split(":")[-1].strip()
                        if part and os.path.exists(part):
                            self.partial_files.add(part)
                            filename = part # Keep track of the latest potential file

                self.process.wait()

                if self._is_cancelled:
                    self.cleanup_partial_files()
                    self.cancelled.emit()
                    return

                if self.process.returncode != 0:
                    self.error.emit("spotdl failed:\n" + all_output)
                    return

                if not filename:
                    files = [os.path.join(self.folder, f) for f in os.listdir(self.folder) if f.lower().endswith(('.mp3', '.m4a', '.ogg', '.flac')) and os.path.isfile(os.path.join(self.folder, f))]
                    if not files:
                        self.error.emit("No file found in download folder after spotdl run.\nOutput:\n" + all_output)
                        return
                    filename = max(files, key=os.path.getctime)
                end_time = datetime.datetime.now()

                duration = end_time - start_time
                entry = {
                    "title": self.title,
                    "url": self.url,
                    "filepath": filename,
                    "type": "Spotify",
                    "format": "audio",
                    "datetime": end_time.isoformat(),
                    "duration_seconds": duration.total_seconds(),
                    "thumbnail": self.thumbnail_url
                }
                save_history(entry)
                send_telegram_notification(entry)
                self.finished.emit("Download complete!", filename, entry)
                return

            # --- yt-dlp block ---
            outtmpl = os.path.join(self.folder, "%(title)s.%(ext)s")
            fmt_str = self.format_id
            extra_args = []
            is_video = self.stream_type in ("[video+audio]", "[video only]")
            if is_video:
                extra_args += ["--audio-multistreams"]
            if is_video and self.thumbnail_url:
                extra_args += ["--embed-thumbnail"]
            if self.subtitle_langs:
                lang_codes = ",".join(self.subtitle_langs)
                extra_args += ["--write-subs", "--sub-langs", lang_codes]
                if self.embed_subs:
                    extra_args += ["--embed-subs"]
            
            if self.trim_args:
                start, end = self.trim_args
                extra_args += ["--download-sections", f"*{start}-{end}", "--force-keyframes-at-cuts"]

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

            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            percent = 0
            filename = None
            all_output = ""
            current_video = 1
            total_videos = playlist_count
            last_reported_video = -1
            self.partial_files = set() # Reset for this run
            captcha_error = False
            for line in iter(self.process.stdout.readline, ''):
                if self._is_cancelled:
                    break

                all_output += line
                # Playlist video progress detection
                pl_match = re.search(r'\[download\] Downloading video (\d+) of (\d+)', line)
                if pl_match and self.playlist_mode in ("playlist", "range"):
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
                        self.partial_files.add(os.path.join(self.folder, os.path.basename(part)))
                elif "[Merger] Merging formats into" in line:
                    # This is the final file after merging, it's the most important one to track.
                    merge_match = re.search(r'\[Merger\] Merging formats into "(.+)"', line)
                    if merge_match:
                        self.partial_files.add(merge_match.group(1).strip())

                # Detect captcha/robot error
                if "confirm you are not a robot" in line.lower() or "captcha" in line.lower():
                    captcha_error = True
            self.process.wait()

            if self._is_cancelled:
                self.cleanup_partial_files()
                self.cancelled.emit()
                return

            if self.process.returncode != 0:
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
                            self.process = subprocess.Popen(cmd_cookies, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                            percent = 0
                            filename = None
                            all_output2 = ""
                            current_video = 1
                            total_videos = playlist_count
                            last_reported_video = -1
                            self.partial_files = set()
                            captcha_error2 = False
                            for line in iter(self.process.stdout.readline, ''):
                                if self._is_cancelled:
                                    break

                                all_output2 += line
                                # ADD THIS NEW BLOCK to find the final merged file
                                merge_match = re.search(r'\[Merger\] Merging formats into "(.+)"', line)
                                if merge_match:
                                    filename = merge_match.group(1).strip() # This is the final, correct path
                                    self.partial_files.add(filename)
                                # Playlist video progress detection
                                pl_match = re.search(r'\[download\] Downloading video (\d+) of (\d+)', line)
                                if pl_match and self.playlist_mode in ("playlist", "range"):
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
                                        self.partial_files.add(os.path.join(self.folder, os.path.basename(part)))

                                if "confirm you are not a robot" in line.lower() or "captcha" in line.lower():
                                    captcha_error2 = True
                            self.process.wait()

                            if self._is_cancelled:
                                self.cleanup_partial_files()
                                self.cancelled.emit()
                                return

                            if self.process.returncode != 0:
                                self.error.emit(f"yt-dlp failed (with cookies):\n{all_output2}")
                                return
                            # Determine file(s) downloaded for history
                            entries = []
                            download_files = list(self.partial_files)
                            if self.playlist_mode in ("playlist", "range", "single"):
                                for file in download_files:
                                    if os.path.exists(file):
                                        # For playlists, duration should be per-file, not total.
                                        # We'll pass the total duration for now, but a better implementation would time each file.
                                        end_time_playlist = datetime.datetime.now()
                                        duration = end_time_playlist - start_time
                                        entry = {
                                            "title": os.path.splitext(os.path.basename(file))[0],
                                            "url": self.url,
                                            "filepath": file,
                                            "type": get_download_type_from_url(self.url),
                                            "format": self.stream_type,
                                            "datetime": end_time.isoformat(),
                                            "duration_seconds": duration.total_seconds(), # This is the total time, not per-file
                                            "thumbnail": self.thumbnail_url
                                        }
                                        save_history(entry)
                                        # Send Telegram notification
                                        send_telegram_notification(entry)
                                        entries.append(entry)
                                if entries:
                                    first_file = entries[0]["filepath"]
                                else:
                                    files = [os.path.join(self.folder, f) for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f))]
                                    if not files:
                                        self.error.emit("No file found in download folder after yt-dlp run.\nOutput:\n" + all_output2)
                                        return
                                    first_file = max(files, key=os.path.getctime)
                                    end_time = datetime.datetime.now()
                                    duration = end_time - start_time
                                    entry = {
                                        "title": os.path.splitext(os.path.basename(first_file))[0],
                                        "url": self.url,
                                        "filepath": first_file,
                                        "type": get_download_type_from_url(self.url),
                                        "format": self.stream_type,
                                        "datetime": end_time.isoformat(),
                                        "duration_seconds": duration.total_seconds(),
                                        "thumbnail": self.thumbnail_url
                                    }
                                    save_history(entry)
                                    # Send Telegram notification
                                    send_telegram_notification(entry)
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
                            end_time = datetime.datetime.now()
                            duration = end_time - start_time
                            entry = {
                                "title": self.title,
                                "url": self.url,
                                "filepath": filename,
                                "type": get_download_type_from_url(self.url),
                                "format": self.stream_type,
                                "datetime": end_time.isoformat(),
                                "duration_seconds": duration.total_seconds(),
                                "thumbnail": self.thumbnail_url
                            }
                            save_history(entry)
                            # Send Telegram notification
                            send_telegram_notification(entry)
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
                for file in self.partial_files:
                    if os.path.exists(file):
                        # For playlists, duration should be per-file. We'll use total time as an approximation.
                        end_time_playlist = datetime.datetime.now()
                        duration = end_time_playlist - start_time
                        entry = {
                            "title": os.path.splitext(os.path.basename(file))[0],
                            "url": self.url,
                            "filepath": file,
                            "type": get_download_type_from_url(self.url),
                            "format": self.stream_type,
                            "datetime": end_time.isoformat(),
                            "duration_seconds": duration.total_seconds(), # This is the total time, not per-file
                            "thumbnail": self.thumbnail_url
                        }
                        save_history(entry)
                        # Send Telegram notification
                        send_telegram_notification(entry)
                        entries.append(entry)
                if entries:
                    first_file = entries[0]["filepath"]
                else:
                    files = [os.path.join(self.folder, f) for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f))]
                    if not files:
                        self.error.emit("No file found in download folder after yt-dlp run.\nOutput:\n" + all_output)
                        return
                    first_file = max(files, key=os.path.getctime)
                    end_time = datetime.datetime.now()
                    duration = end_time - start_time
                    entry = {
                        "title": os.path.splitext(os.path.basename(first_file))[0],
                        "url": self.url,
                        "filepath": first_file,
                        "type": get_download_type_from_url(self.url),
                        "format": self.stream_type,
                        "datetime": end_time.isoformat(),
                        "duration_seconds": duration.total_seconds(),
                        "thumbnail": self.thumbnail_url
                    }
                    save_history(entry)
                    # Send Telegram notification
                    send_telegram_notification(entry)
                    entries.append(entry)
                self.finished.emit("Download complete!", first_file, {"playlist": True, "entries": entries})
                return
            # --- NEW ROBUST FILE FINDING LOGIC for single files ---
            # This is more reliable because it just finds the newest file instead of parsing the log.
            try:
                # List all files in the download folder
                all_files = [os.path.join(self.folder, f) for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f))]
                if not all_files:
                    raise FileNotFoundError("Download finished, but no files were found in the destination folder.")

                # Find the most recently modified file. This is our downloaded video.
                filename = max(all_files, key=os.path.getmtime)

                end_time = datetime.datetime.now()
                duration = end_time - start_time
                entry = {
                    "title": self.title,
                    "url": self.url,
                    "filepath": filename,
                    "type": get_download_type_from_url(self.url),
                    "format": self.stream_type,
                    "datetime": end_time.isoformat(),
                    "duration_seconds": duration.total_seconds(),
                    "thumbnail": self.thumbnail_url
                }
                save_history(entry)
                # Send Telegram notification
                send_telegram_notification(entry)
                self.finished.emit("Download complete!", filename, entry)
            except Exception as e:
                self.error.emit(f"Error finding downloaded file: {e}\nOutput:\n{all_output}")
        except Exception as e:
            import traceback
            self.error.emit(f"Download error: {e}\n{traceback.format_exc()}")

    def cleanup_partial_files(self):
        """Deletes all files tracked during the download process."""
        print(f"[Cancel] Cleaning up {len(self.partial_files)} partial file(s)...")
        for f_path in self.partial_files:
            try:
                if os.path.exists(f_path):
                    os.remove(f_path)
                    print(f"[Cancel] Deleted: {f_path}")
            except Exception as e:
                print(f"[Cancel] Error deleting {f_path}: {e}")

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
        self.resize(450, 500) # Set a fixed, reasonable size
        self.setStyleSheet("""
            QDialog {background: #23243a; color: #fff;}
            QCheckBox, QLabel {font-size: 15px;}
            QPushButton {background: #009688; color:#fff; border-radius: 8px; font-size: 13px; padding: 6px 18px;}
            QLineEdit {
                border-radius: 8px; border: 1px solid #444; background: #20232a;
                color: #fff; padding: 8px; font-size: 14px;
            }
            QScrollArea { border: 1px solid #444; border-radius: 8px; }
        """)
        self.selected_langs = []
        vbox = QVBoxLayout(self)
        vbox.setSpacing(10)

        # --- Top Section: Embed Checkbox ---
        self.check_embed = QCheckBox("Embed subtitle(s) into video (if possible)")
        self.check_embed.setChecked(True)
        vbox.addWidget(self.check_embed)

        # --- Search Bar ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search for a language...")
        self.search_input.textChanged.connect(self.filter_languages)
        vbox.addWidget(self.search_input)

        # --- Scroll Area for Languages ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: #20232a;")

        container = QWidget()
        container_layout = QVBoxLayout()
        container.setLayout(container_layout)

        self.lang_checks = []
        for lang, desc in lang_list:
            cb = QCheckBox(desc)
            cb.lang = lang
            container_layout.addWidget(cb)
            self.lang_checks.append(cb)
        container_layout.addStretch() # Push checkboxes to the top

        scroll.setWidget(container)
        vbox.addWidget(scroll)

        # --- Selection Buttons ---
        selection_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        deselect_all_btn = QPushButton("Deselect All")
        select_all_btn.clicked.connect(self.select_all)
        deselect_all_btn.clicked.connect(self.deselect_all)
        selection_row.addWidget(select_all_btn)
        selection_row.addWidget(deselect_all_btn)
        vbox.addLayout(selection_row)

        # --- Dialog Buttons (OK/Cancel) ---
        btn_row = QHBoxLayout()
        btn_row.addStretch(2)
        ok = QPushButton("OK")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        ok.setDefault(True)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        vbox.addLayout(btn_row)

    def filter_languages(self):
        """Hides/shows language checkboxes based on search text."""
        query = self.search_input.text().lower()
        for cb in self.lang_checks:
            cb.setVisible(query in cb.text().lower())

    def select_all(self):
        """Checks all visible language checkboxes."""
        for cb in self.lang_checks:
            if cb.isVisible():
                cb.setChecked(True)

    def deselect_all(self):
        """Unchecks all visible language checkboxes."""
        for cb in self.lang_checks:
            if cb.isVisible():
                cb.setChecked(False)

    def get_selection(self):
        langs = [cb.lang for cb in self.lang_checks if cb.isChecked()]
        embed = self.check_embed.isChecked()
        return embed, langs

class AudioSelectionDialog(QDialog):
    def __init__(self, lang_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Audio Track Options (Dubs)")
        self.resize(400, 450)
        self.setStyleSheet("""
            QDialog {background: #23243a; color: #fff;}
            QCheckBox, QLabel {font-size: 15px;}
            QPushButton {background: #009688; color:#fff; border-radius: 8px; font-size: 13px; padding: 6px 18px;}
            QScrollArea { border: 1px solid #444; border-radius: 8px; }
        """)
        vbox = QVBoxLayout(self)
        vbox.setSpacing(10)
        
        vbox.addWidget(QLabel("Select additional audio tracks to download:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: #20232a;")
        
        container = QWidget()
        container_layout = QVBoxLayout()
        container.setLayout(container_layout)
        
        self.lang_checks = []
        for lang, name in lang_list:
            cb = QCheckBox(f"{name} ({lang})")
            cb.lang = lang
            container_layout.addWidget(cb)
            self.lang_checks.append(cb)
        container_layout.addStretch()
        
        scroll.setWidget(container)
        vbox.addWidget(scroll)

        # Selection Buttons
        selection_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        deselect_all_btn = QPushButton("Deselect All")
        select_all_btn.clicked.connect(lambda: [cb.setChecked(True) for cb in self.lang_checks])
        deselect_all_btn.clicked.connect(lambda: [cb.setChecked(False) for cb in self.lang_checks])
        selection_row.addWidget(select_all_btn)
        selection_row.addWidget(deselect_all_btn)
        vbox.addLayout(selection_row)

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
        return [cb.lang for cb in self.lang_checks if cb.isChecked()]

class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download History")
        self.resize(700, 500)
        self.setStyleSheet("""
            QListWidget::item { padding: 5px; }
            QDialog {background: #23243a; color: #fff;}
            QListWidget {background: #20232a; color: #fff; font-size: 15px; border-radius: 10px;}
            QPushButton {background: #009688; color:#fff; border-radius: 8px; font-size: 13px; padding: 6px 18px;}
            QPushButton#clear {background: #ff1744;}
            QLineEdit {
                border-radius: 8px; border: 1px solid #444; background: #20232a;
                color: #fff; padding: 8px; font-size: 14px;
            }
        """)
        vbox = QVBoxLayout(self)

        # --- Search Bar ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search by title, type, or date...")
        self.search_input.textChanged.connect(self.filter_history)
        vbox.addWidget(self.search_input)

        # --- History List ---
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setIconSize(QSize(80, 45)) # Standard 16:9 aspect ratio
        vbox.addWidget(self.list)

        # --- Action Buttons ---
        btns = QHBoxLayout()
        self.open_btn = QPushButton("Open File")
        self.openf_btn = QPushButton("Open Folder")
        self.copy_btn = QPushButton("Copy Path")
        self.clear_btn = QPushButton("Clear History")
        self.analytics_btn = QPushButton("📊 Analytics")
        self.analytics_btn.setToolTip("Show Download Analytics")
        self.clear_btn.setObjectName("clear")
        btns.addWidget(self.open_btn)
        btns.addWidget(self.openf_btn)
        btns.addWidget(self.copy_btn)
        btns.addStretch(1)
        btns.addWidget(self.analytics_btn)
        btns.addWidget(self.clear_btn)
        vbox.addLayout(btns)

        # --- Details View ---
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
        self.analytics_btn.clicked.connect(self.show_analytics)

    def filter_history(self):
        """Hides or shows history items based on the search query."""
        query = self.search_input.text().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            # The item's text already contains title, type, and date
            item_text = item.text().lower()
            item.setHidden(query not in item_text)

    def load_history(self):
        self.list.clear()
        self.threads = [] # Keep a reference to threads to prevent them from being garbage collected
        self.entries = load_history()
        
        # Use a placeholder icon
        placeholder_icon = QIcon("icon.png") if os.path.exists("icon.png") else QIcon()

        all_items = []
        for entry in self.entries:
            if isinstance(entry, dict) and "entries" in entry and entry.get("playlist"):
                all_items.extend(entry["entries"])
            else:
                all_items.append(entry)

        for i, entry_data in enumerate(all_items):
            label = f"{entry_data.get('title', 'N/A')}  [{entry_data.get('type', 'N/A')}] ({entry_data.get('datetime', ' ')[0:19].replace('T',' ')})"
            item = QListWidgetItem(placeholder_icon, label)
            item.setData(Qt.UserRole, entry_data)
            self.list.addItem(item)

            # Start a background thread to load the actual thumbnail
            thumbnail_url = entry_data.get("thumbnail")
            if thumbnail_url:
                thread = ThumbnailLoaderThread(thumbnail_url, i)
                thread.finished.connect(self.on_thumbnail_loaded)
                self.threads.append(thread)
                thread.start()

        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def on_thumbnail_loaded(self, pixmap, index):
        """Slot to update an item's icon when its thumbnail has been downloaded."""
        if not pixmap.isNull() and index < self.list.count():
            item = self.list.item(index)
            if item:
                item.setIcon(QIcon(pixmap))

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

    def show_analytics(self):
        """Shows the analytics dashboard dialog."""
        if not MATPLOTLIB_AVAILABLE:
            QMessageBox.warning(self, "Feature Disabled", "The analytics dashboard requires the 'matplotlib' library.\nPlease install it by running: pip install matplotlib")
            return
        # Pass the already loaded history data to the dialog for efficiency
        dlg = AnalyticsDialog(self.entries, self)
        dlg.exec_()

class ThumbnailLoaderThread(QThread):
    """A thread to load a thumbnail image from a URL without blocking the UI."""
    finished = pyqtSignal(QPixmap, int)

    def __init__(self, url, index, parent=None):
        super().__init__(parent)
        self.url = url
        self.index = index

    def run(self):
        if not self.url:
            return
        try:
            data = urllib.request.urlopen(self.url, timeout=5).read()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            self.finished.emit(pixmap, self.index)
        except Exception as e:
            print(f"[ThumbnailLoader] Failed to load {self.url}: {e}")

class TelegramSettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Telegram Notification Settings")
        self.setStyleSheet("""
            QDialog {background: #23243a; color: #fff;}
            QLabel {font-size: 15px; margin-bottom: 5px;}
            QLineEdit {
                border-radius: 8px; border: 1px solid #444; background: #20232a;
                color: #fff; padding: 8px; font-size: 14px;
            }
            QPushButton {
                background: #009688; color:#fff; border-radius: 8px;
                font-size: 13px; padding: 8px 20px;
            }
        """)
        self.config = config
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        layout.addWidget(QLabel("Bot Token:"))
        self.token_input = QLineEdit(self)
        self.token_input.setPlaceholderText("Enter your Telegram Bot Token")
        self.token_input.setText(config.get("telegram_bot_token", ""))
        layout.addWidget(self.token_input)

        layout.addWidget(QLabel("Chat ID:"))
        self.chat_id_input = QLineEdit(self)
        self.chat_id_input.setPlaceholderText("Enter your personal or group Chat ID")
        self.chat_id_input.setText(config.get("telegram_chat_id", ""))
        layout.addWidget(self.chat_id_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

class AnalyticsDialog(QDialog):
    """A professional, god-level dialog to display download analytics with multiple charts."""
    def __init__(self, history_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Analytics Dashboard")
        self.setMinimumSize(900, 700)
        self.setStyleSheet("""
            QDialog { background-color: #23243a; }
            QLabel { color: #fff; font-size: 14px; }
            QLabel#title { font-size: 28px; font-weight: bold; color: #00e5ff; padding-bottom: 10px; }
            QFrame#stat_box { background: #20232a; border-radius: 12px; }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        title_label = QLabel("📊 Download Analytics")
        title_label.setObjectName("title")
        title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(title_label)

        # --- Analytics Calculation ---
        if not history_data:
            self.layout.addWidget(QLabel("No download history available to generate analytics.", alignment=Qt.AlignCenter))
            return

        total_downloads = 0
        source_counts = {}
        format_counts = {}
        downloads_by_month = {}
        total_size = 0
        first_download_date = None

        all_items = []
        for entry in history_data:
            if isinstance(entry, dict) and "entries" in entry and entry.get("playlist"):
                all_items.extend(entry["entries"])
            else:
                all_items.append(entry)

        for entry in all_items:
            try:
                total_downloads += 1
                source = entry.get('type', 'Unknown')
                source_counts[source] = source_counts.get(source, 0) + 1
                
                fmt = os.path.splitext(entry.get('filepath', ''))[1].lower().replace('.', '') or 'N/A'
                format_counts[fmt] = format_counts.get(fmt, 0) + 1

                filepath = entry.get('filepath')
                if filepath and os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)

                dt_iso = entry.get('datetime')
                if dt_iso:
                    dt_obj = datetime.datetime.fromisoformat(dt_iso)
                    if first_download_date is None or dt_obj < first_download_date:
                        first_download_date = dt_obj
                    month_key = dt_obj.strftime('%Y-%m') # e.g., "2024-05"
                    downloads_by_month[month_key] = downloads_by_month.get(month_key, 0) + 1
            except Exception:
                continue # Skip corrupted entries

        # --- Prepare Data for Display ---
        avg_size_str = human_size(total_size / total_downloads) if total_downloads > 0 else "0 B"
        total_size_str = human_size(total_size)
        first_download_str = first_download_date.strftime('%b %d, %Y') if first_download_date else "N/A"
        most_common_format = max(format_counts, key=format_counts.get) if format_counts else "N/A"

        # --- Summary Stats ---
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(15)
        stats_layout.addWidget(self.create_stat_label("Total Downloads", str(total_downloads)))
        stats_layout.addWidget(self.create_stat_label("Total Size", total_size_str))
        stats_layout.addWidget(self.create_stat_label("Average File Size", avg_size_str))
        stats_layout.addWidget(self.create_stat_label("First Download", first_download_str))
        self.layout.addLayout(stats_layout)

        # --- Charts ---
        if MATPLOTLIB_AVAILABLE:
            charts_layout = QHBoxLayout()
            
            # Chart 1: Downloads by Source (Bar Chart)
            sorted_sources = sorted(source_counts.items(), key=lambda item: item[1], reverse=True)[:5]
            source_labels = [item[0] for item in sorted_sources]
            source_values = [item[1] for item in sorted_sources]
            source_chart = self.create_bar_chart(source_labels, source_values, "Top 5 Download Sources")
            charts_layout.addWidget(source_chart)

            # Chart 2: Downloads by Month (Line Chart)
            if len(downloads_by_month) > 1:
                sorted_months = sorted(downloads_by_month.items())
                month_labels = [datetime.datetime.strptime(item[0], '%Y-%m').strftime('%b %Y') for item in sorted_months]
                month_values = [item[1] for item in sorted_months]
                month_chart = self.create_line_chart(month_labels, month_values, "Downloads Over Time")
                charts_layout.addWidget(month_chart)

            self.layout.addLayout(charts_layout)

        # --- Animation ---
        self.setWindowOpacity(0.0)

    def create_stat_label(self, title, value):
        frame = QFrame()
        frame.setObjectName("stat_box")
        layout = QVBoxLayout(frame)
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #ccc; font-weight: bold;")
        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet("font-size: 22px; color: #ffeb3b; font-weight: bold;")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return frame

    def create_bar_chart(self, labels, values, title):
        matplotlib.rcParams.update({'font.size': 10, 'text.color': 'white', 'axes.labelcolor': 'white', 'xtick.color': '#ccc', 'ytick.color': '#ccc'})
        fig = Figure(figsize=(5, 4), dpi=100, facecolor='#23243a')
        ax = fig.add_subplot(111, facecolor='#20232a')
        
        bars = ax.bar(labels, values, color='#009688', zorder=2)
        ax.set_title(title, color='#00e5ff', fontsize=16, weight='bold')
        ax.set_ylabel('Number of Downloads')
        ax.grid(axis='y', color='#444', linestyle='--', linewidth=0.5, zorder=1)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#555')
        ax.spines['left'].set_color('#555')
        fig.tight_layout()
        return FigureCanvas(fig)

    def create_line_chart(self, labels, values, title):
        matplotlib.rcParams.update({'font.size': 10, 'text.color': 'white', 'axes.labelcolor': 'white', 'xtick.color': '#ccc', 'ytick.color': '#ccc'})
        fig = Figure(figsize=(5, 4), dpi=100, facecolor='#23243a')
        ax = fig.add_subplot(111, facecolor='#20232a')
        
        ax.plot(labels, values, color='#ff1744', marker='o', zorder=2)
        ax.fill_between(labels, values, color='#ff1744', alpha=0.2, zorder=1)
        ax.set_title(title, color='#00e5ff', fontsize=16, weight='bold')
        ax.set_ylabel('Number of Downloads')
        ax.grid(axis='y', color='#444', linestyle='--', linewidth=0.5, zorder=1)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#555')
        ax.spines['left'].set_color('#555')
        plt = ax.get_figure()
        plt.autofmt_xdate(rotation=30, ha='right')
        fig.tight_layout()
        return FigureCanvas(fig)

    def showEvent(self, event):
        """Override showEvent to trigger the fade-in animation."""
        super().showEvent(event)
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(350)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

# Place this with your other class definitions, e.g., after TelegramSettingsDialog

class UpdateCheckerThread(QThread):
    """
    A worker thread that checks for application updates on GitHub in the background.
    Emits a signal with the update information if a new version is found.
    """
    update_available = pyqtSignal(str, str, str, str, str) # current_ver, new_ver, changelog, url, download_url
    error = pyqtSignal(str)

    def __init__(self, current_version, version_url, parent=None):
        super().__init__(parent)
        self.current_version_str = current_version.lstrip('v')
        self.version_url = version_url

    def run(self):
        """Fetches the version.json file and compares versions."""
        try:
            # Fetch the version data from GitHub
            with urllib.request.urlopen(self.version_url, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))

            latest_version_str = data.get("version", "0.0").lstrip('v')
            changelog = data.get("changelog", "No details provided.")
            github_url = data.get("url", "")
            download_url = data.get("download_url", "") # The direct download link for the new executable

            # Numerically compare versions (e.g., "1.10" > "1.9")
            current_version = packaging_version.parse(self.current_version_str) # Use packaging for robust comparison
            latest_version = packaging_version.parse(latest_version_str) # Use packaging for robust comparison

            if latest_version > current_version:
                self.update_available.emit(self.current_version_str, latest_version_str, changelog, github_url, download_url)

        except urllib.error.URLError as e:
            self.error.emit(f"Network error: {e.reason}")
        except Exception as e:
            self.error.emit(f"An error occurred while checking for updates: {e}")


class UpdateDialog(QDialog):
    """
    A polished, custom dialog to notify the user about a new update.
    """
    def __init__(self, current_version, new_version, changelog, github_url, download_url, parent=None):
        super().__init__(parent)
        self.github_url = github_url
        self.download_url = download_url
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        self.setup_ui(current_version, new_version, changelog)

    def setup_ui(self, current_version, new_version, changelog):
        # --- Download Progress Thread ---
        self.download_thread = None

        # Main container with shadow and rounded corners
        self.container = QFrame(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            #container {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(45, 49, 66, 240), stop:1 rgba(24, 24, 36, 240));
                border-radius: 20px;
                border: 1px solid #444;
            }
        """)
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(15)

        # --- Title and Icon ---
        title_layout = QHBoxLayout()
        icon_label = QLabel("🚀")
        icon_label.setFont(QFont("Segoe UI Emoji", 30))
        title_label = QLabel("New Update Available!")
        title_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title_label.setStyleSheet("color: #fff;")
        title_layout.addWidget(icon_label)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        # --- Version Info ---
        version_info = QLabel(f"You are on version <b>{current_version}</b>. Version <b>{new_version}</b> is now available.")
        version_info.setFont(QFont("Segoe UI", 12))
        version_info.setStyleSheet("color: #ccc;")
        version_info.setWordWrap(True)
        main_layout.addWidget(version_info)

        # --- Changelog ---
        changelog_header = QLabel("What's New:")
        changelog_header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        changelog_header.setStyleSheet("color: #00e5ff;")
        main_layout.addWidget(changelog_header)

        changelog_text = QTextEdit()
        changelog_text.setReadOnly(True)
        changelog_text.setText(changelog.replace('\n', '<br>')) # Allow basic HTML
        changelog_text.setStyleSheet("""
            QTextEdit {
                background: rgba(0,0,0,0.2);
                border: 1px solid #444;
                color: #f0f0f0;
                font-size: 13px;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        main_layout.addWidget(changelog_text)

        # --- Update Progress Bar (initially hidden) ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { height: 8px; border-radius: 4px; background: #444; } QProgressBar::chunk { border-radius: 4px; background: #00e5ff; }")
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)


        # --- Buttons ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.later_btn = QPushButton("Later")
        self.later_btn.setCursor(Qt.PointingHandCursor)
        self.later_btn.setStyleSheet("""
            QPushButton {
                background: #353541; color: #fff; font-size: 14px;
                padding: 10px 25px; border-radius: 12px; border: 1px solid #555;
            }
            QPushButton:hover { background: #4a4a58; }
        """)
        self.later_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.later_btn)

        self.update_btn = QPushButton("Update & Restart")
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00e5ff, stop:1 #1d8fe1);
                color: #fff; font-size: 14px; font-weight: bold;
                padding: 10px 25px; border-radius: 12px; border: none;
            }
            QPushButton:hover { background: #1d8fe1; }
        """)
        self.update_btn.clicked.connect(self.accept_update)
        button_layout.addWidget(self.update_btn)
        main_layout.addLayout(button_layout)

        # Set the main layout for the dialog
        dialog_layout = QVBoxLayout(self)
        dialog_layout.addWidget(self.container)
        self.setLayout(dialog_layout)

    def accept_update(self):
        """Starts the automatic update process."""
        if not self.download_url:
            # Fallback to opening the GitHub page if no direct download URL is provided
            QDesktopServices.openUrl(QUrl(self.github_url))
            self.accept()
            return

        self.update_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.update_btn.setText("Updating...")
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0) # Indeterminate progress

        self.download_thread = UpdateDownloaderThread(self.download_url)
        self.download_thread.finished.connect(self.on_update_downloaded)
        self.download_thread.error.connect(self.on_update_error)
        self.download_thread.start()

    def on_update_downloaded(self, new_file_path):
        """Called when the new executable is downloaded. Creates and runs the updater script."""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.update_btn.setText("Restarting...")

        try:
            current_app_path = QCoreApplication.applicationFilePath()
            if not current_app_path.lower().endswith('.exe'):
                # This logic is primarily for packaged .exe files.
                # For scripts, a simple restart isn't safe.
                QMessageBox.information(self, "Update Ready", f"Update downloaded to:\n{new_file_path}\nPlease replace the old version and restart manually.")
                self.accept()
                return

            if sys.platform == "win32":
                updater_content = f"""
@echo off
echo Waiting for application to close...
timeout /t 3 /nobreak > nul
echo Replacing application file...
del "{current_app_path}"
move "{new_file_path}" "{current_app_path}"
echo Relaunching application...
start "" "{current_app_path}"
echo Cleaning up...
del "%~f0"
"""
                updater_path = os.path.join(os.path.dirname(current_app_path), "updater.bat")
                with open(updater_path, "w") as f:
                    f.write(updater_content)
                
                # Launch the updater script detached from the current process
                subprocess.Popen(f'"{updater_path}"', shell=True, creationflags=subprocess.DETACHED_PROCESS)
                
                # Close the main application
                QCoreApplication.quit()

            else: # macOS / Linux (basic handling)
                QMessageBox.information(self, "Update Ready", f"Update downloaded to:\n{new_file_path}\nPlease replace the old version and restart.")
                self.accept()

        except Exception as e:
            self.on_update_error(f"Failed to apply update: {e}")

    def on_update_error(self, error_message):
        QMessageBox.critical(self, "Update Failed", f"Could not download the update:\n{error_message}")
        self.update_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
        self.update_btn.setText("Update & Restart")
        self.progress_bar.hide()


class UpdateDownloaderThread(QThread):
    """A simple thread to download a file from a URL."""
    finished = pyqtSignal(str) # Emits the path of the downloaded file
    error = pyqtSignal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            import tempfile
            # Download to a temporary file
            response = urllib.request.urlopen(self.url)
            # Create a temporary file with the correct extension
            original_filename = os.path.basename(urllib.parse.urlparse(self.url).path)
            suffix = os.path.splitext(original_filename)[1]
            
            # Use NamedTemporaryFile to get a path, but manage deletion manually
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            temp_file_path = temp_file.name
            
            with temp_file as f:
                f.write(response.read())
            
            self.finished.emit(temp_file_path)
        except Exception as e:
            self.error.emit(str(e))


class YTDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon("icon.png") if os.path.exists("icon.png") else QIcon())
        self.resize(1200, 700)
        self.setMinimumSize(900, 600)
        self.config = load_config()
        self.folder = self.config.get("download_folder", os.path.join(os.path.expanduser("~"), "Downloads"))
        self.folder = os.path.join(os.path.expanduser("~"), "Downloads")
        self.setAcceptDrops(True)
        self.theme_dark = True
        self.proxy = ""
        self.proxy_type = "http"  # or "socks5"
        self.use_vpn = False
        self.use_proxy = False
        self.proxy_status = "disconnected"

        self.last_clipboard_url = "" # To avoid re-prompting for the same URL
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

        # Trim options
        self.trim_checkbox = QCheckBox("Trim Video")
        self.trim_checkbox.setFont(QFont("Segoe UI", 13))
        self.trim_checkbox.toggled.connect(self.toggle_trim)
        left_layout.addWidget(self.trim_checkbox)
        
        self.trim_container = QWidget()
        self.trim_container.setVisible(False)
        trim_layout = QHBoxLayout(self.trim_container)
        trim_layout.setContentsMargins(20, 0, 0, 0)

        self.trim_start = QLineEdit()
        self.trim_start.setPlaceholderText("Start (e.g. 00:10)")
        self.trim_end = QLineEdit()
        self.trim_end.setPlaceholderText("End (e.g. 01:30)")
        
        trim_layout.addWidget(QLabel("Start:"))
        trim_layout.addWidget(self.trim_start)
        trim_layout.addWidget(QLabel("End:"))
        trim_layout.addWidget(self.trim_end)
        left_layout.addWidget(self.trim_container)

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
        left_layout.addLayout(folder_row)
        folder_row.addWidget(self.history_btn)

        # Download button
        self.download_btn = QPushButton("Download")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setFont(QFont("Segoe UI", 17, QFont.Bold))
        self.download_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setEnabled(False)

        # Cancel button (initially hidden)
        self.cancel_btn = QPushButton("Cancel Download")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setFont(QFont("Segoe UI", 17, QFont.Bold))
        self.cancel_btn.setStyleSheet("background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #c62828, stop:1 #e57373); color: white;")
        self.cancel_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cancel_btn.clicked.connect(self.cancel_download)
        self.cancel_btn.hide()

        # Layout to hold and swap Download/Cancel buttons
        self.download_button_layout = QHBoxLayout()
        self.download_button_layout.addWidget(self.download_btn)
        self.download_button_layout.addWidget(self.cancel_btn)
        left_layout.addLayout(self.download_button_layout)

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
        self.update_btn = QPushButton("🔄")
        self.update_btn.setToolTip("Check for Updates")
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setObjectName("clear")
        self.update_btn.clicked.connect(self.check_for_updates)
        about_row.addWidget(QLabel(f"{APP_COPYRIGHT}  {APP_VERSION}"))
        about_row.addStretch(1)
        about_row.addWidget(self.mode_btn)
        about_row.addWidget(self.update_btn)
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

        # --- NEW TELEGRAM CONTROLS ---
        telegram_row = QHBoxLayout()
        self.telegram_checkbox = QCheckBox("Send History to Telegram")
        self.telegram_checkbox.setFont(QFont("Segoe UI", 13))
        self.telegram_checkbox.setChecked(self.config.get("telegram_notifications_enabled", False))
        self.telegram_checkbox.stateChanged.connect(self.toggle_telegram_notifications)
        telegram_row.addWidget(self.telegram_checkbox)
        telegram_row.addStretch()
        self.telegram_settings_btn = QPushButton("⚙️ Settings")
        self.telegram_settings_btn.setToolTip("Configure Telegram Bot Token and Chat ID")
        self.telegram_settings_btn.setObjectName("clear") # Use a subtle style
        self.telegram_settings_btn.setCursor(Qt.PointingHandCursor)
        self.telegram_settings_btn.clicked.connect(self.open_telegram_settings)
        telegram_row.addWidget(self.telegram_settings_btn)
        right_layout.addLayout(telegram_row)
        # --- END OF NEW TELEGRAM CONTROLS ---


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
        self.thumbnail_container = QWidget()
        self.thumbnail_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.thumbnail_container.setStyleSheet("border-radius: 15px;") # Rounded corners for the container
        thumbnail_container_layout = QVBoxLayout(self.thumbnail_container)
        thumbnail_container_layout.setContentsMargins(0, 0, 0, 0)
        self.thumbnail_bg_label = QLabel() # For the blurred background glow
        self.thumbnail_bg_label.setScaledContents(True)
        self.thumbnail_bg_label.setStyleSheet("border-radius: 15px;")
        blur_effect = QGraphicsBlurEffect()
        blur_effect.setBlurRadius(50) # Adjust for more/less blur
        self.thumbnail_bg_label.setGraphicsEffect(blur_effect)
        self.thumbnail_label = QLabel() # For the sharp foreground thumbnail
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet("background: transparent; border-radius: 15px;")
        thumbnail_container_layout.addWidget(self.thumbnail_label)
        self.thumbnail_bg_label.setParent(self.thumbnail_container)
        right_layout.addWidget(self.thumbnail_container, 10)

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
        # Audio and Subtitle options row
        track_row = QHBoxLayout()
        
        self.audio_btn = QPushButton("DUBS")
        self.audio_btn.setCursor(Qt.PointingHandCursor)
        self.audio_btn.setEnabled(False)
        self.audio_btn.setToolTip("Select additional audio tracks (Dubs)")
        self.audio_btn.clicked.connect(self.select_audio)
        track_row.addWidget(self.audio_btn)

        self.subtitle_btn = QPushButton("SUBS")
        self.subtitle_btn.setCursor(Qt.PointingHandCursor)
        self.subtitle_btn.setEnabled(False)
        self.subtitle_btn.setToolTip("Select subtitles")
        self.subtitle_btn.clicked.connect(self.select_subtitle)
        subtitle_row.addWidget(self.subtitle_label)
        subtitle_row.addWidget(self.subtitle_btn)
        right_layout.addLayout(subtitle_row)
        track_row.addWidget(self.subtitle_btn)
        
        right_layout.addLayout(track_row)
        
        self.tracks_label = QLabel("")
        self.tracks_label.setFont(QFont("Segoe UI", 12))
        self.tracks_label.setStyleSheet("color:#b0bec5;")
        self.tracks_label.setWordWrap(True)
        right_layout.addWidget(self.tracks_label)

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
        self.available_audio_langs = []
        self.selected_audio_langs = []
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
        
        # --- Auto-Update Check on Startup ---
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(2000, self.check_for_updates) # Check 2 seconds after launch

        # --- Clipboard Monitoring ---
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)

        self.auto_focus()
        self.show()

    def check_for_updates(self):
        """Initiates the background check for a new version."""
        print("[UpdateChecker] Checking for updates...") # Optional but smart for console/log
        self.status.setText("Checking for updates...")
        version_url = "https://raw.githubusercontent.com/rohitt99/yt-downloader/main/version.json"
        self.update_thread = UpdateCheckerThread(APP_VERSION, version_url)
        self.update_thread.update_available.connect(self.show_update_dialog)
        self.update_thread.error.connect(lambda msg: self.status.setText(f"Update check failed: {msg}"))
        self.update_thread.finished.connect(lambda: self.status.setText("Ready."))
        self.update_thread.start()

    def show_update_dialog(self, current_ver, new_ver, changelog, url, download_url):
        """Displays the custom update dialog."""
        dialog = UpdateDialog(current_ver, new_ver, changelog, url, download_url, self)
        dialog.exec_()


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

    def toggle_trim(self, checked):
        self.trim_container.setVisible(checked)

    def on_clipboard_changed(self):
        """
        Monitors the clipboard for YouTube/Spotify links and prompts the user.
        """
        try:
            clipboard_text = self.clipboard.text().strip()
            if not clipboard_text or clipboard_text == self.last_clipboard_url:
                return # Ignore empty clipboard or same URL

            # Check if it's a valid URL we care about
            is_yt = "youtube.com" in clipboard_text or "youtu.be" in clipboard_text
            is_spotify = "spotify.com" in clipboard_text

            if is_yt or is_spotify:
                self.last_clipboard_url = clipboard_text # Store to prevent re-prompting

                # Bring window to front to show the message box
                self.activateWindow()
                self.raise_()

                reply = QMessageBox.question(self, "Link Detected", f"A {'YouTube' if is_yt else 'Spotify'} link was found in your clipboard. <br><br><b>{clipboard_text}</b><br><br>Do you want to fetch it for download?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.url_input.setText(clipboard_text)
                    self.fetch_qualities()
        except Exception as e:
            print(f"[ClipboardMonitor] Error: {e}")

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
            self.config['download_folder'] = folder
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
        self.thumbnail_bg_label.clear()
        self.thumbnail_label.clear()
        self.subtitle_label.setText("")
        self.tracks_label.setText("")
        self.subtitle_btn.setEnabled(False)
        self.audio_btn.setEnabled(False)
        self.available_subtitles = []
        self.selected_subtitle_langs = []
        self.available_audio_langs = []
        self.selected_audio_langs = []
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
                         lang_list, subtitles, automatic_captions, has_playlist, playlist_entries, audio_lang_list):
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
            # Use a thread to load the thumbnail without freezing the UI
            self.thumbnail_loader_thread = ThumbnailLoaderThread(thumbnail_url, -1) # -1 index means it's for the main display
            self.thumbnail_loader_thread.finished.connect(self.on_main_thumbnail_loaded)
            self.thumbnail_loader_thread.start()
        else:
            self.thumbnail_bg_label.clear()
            self.thumbnail_label.setText("No thumbnail")

        self.available_subtitles = lang_list
        self.available_audio_langs = audio_lang_list
        
        status_parts = []
        
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
            status_parts.append(f"{len(lang_list)} Subs")
        else:
            self.subtitle_label.setText("No subtitles available.")
            self.subtitle_btn.setEnabled(False)
            self.selected_subtitle_langs = []
            self.embed_subs = False
            
        if audio_lang_list:
            self.audio_btn.setEnabled(True)
            status_parts.append(f"{len(audio_lang_list)} Dubs")
        else:
            self.audio_btn.setEnabled(False)
            
        if status_parts:
            self.tracks_label.setText("Available: " + ", ".join(status_parts))
        else:
            self.tracks_label.setText("No extra tracks available.")
            
        self.selected_subtitle_langs = []
        self.selected_audio_langs = []
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

    def on_main_thumbnail_loaded(self, pixmap, index):
        """Slot to update the main thumbnail display once it's loaded."""
        if index == -1 and not pixmap.isNull():
            # Set the blurred background
            self.thumbnail_bg_label.setPixmap(pixmap)
            self.thumbnail_bg_label.setGeometry(self.thumbnail_container.rect())
            self.thumbnail_bg_label.lower()

            # Set the sharp foreground image, scaled with aspect ratio
            scaled_pixmap = pixmap.scaled(self.thumbnail_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumbnail_label.setPixmap(scaled_pixmap)
        elif pixmap.isNull():
            self.thumbnail_bg_label.clear()
            self.thumbnail_label.setText("No thumbnail")

    def fetch_error(self, err):
        self.status.setText("Fetch error.")
        self.fetch_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", str(err))

    def select_audio(self):
        if not self.available_audio_langs:
            return
        dlg = AudioSelectionDialog(self.available_audio_langs, self)
        if dlg.exec_() == QDialog.Accepted:
            self.selected_audio_langs = dlg.get_selection()
            self.update_tracks_label()
        else:
            self.selected_audio_langs = []
            self.update_tracks_label()

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
            self.selected_subtitle_langs = langs
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
            self.update_tracks_label()
        else:
            self.subtitle_label.setText("No subtitles selected.")
            self.selected_subtitle_langs = []
            self.embed_subs = False
            self.update_tracks_label()

    def update_tracks_label(self):
        parts = []
        if self.selected_audio_langs:
            parts.append(f"{len(self.selected_audio_langs)} Audio(s)")
        if self.selected_subtitle_langs:
            parts.append(f"{len(self.selected_subtitle_langs)} Sub(s)")
        
        if parts:
            self.tracks_label.setText("Selected: " + ", ".join(parts))
            self.tracks_label.setStyleSheet("color: #00e5ff; font-weight: bold;")
        else:
            self.tracks_label.setText("No extra tracks selected.")
            self.tracks_label.setStyleSheet("color: #b0bec5;")

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
        # Replace It With This New Block
        fmtid, stream_type = self.quality_box.currentData()

        # Construct audio selection string
        audio_selection = ""
        if self.selected_audio_langs:
            # Append selected audio tracks to the download
            audio_parts = [f"bestaudio[language={lang}]" for lang in self.selected_audio_langs]
            audio_selection = "+" + "+".join(audio_parts)

        # Trim logic
        trim_args = None
        if self.trim_checkbox.isChecked():
            start = self.trim_start.text().strip()
            end = self.trim_end.text().strip()
            if start and end:
                trim_args = (start, end)

        # --- THIS IS THE NEW, SMART LOGIC ---
        # It determines the correct format string for ALL cases.
        final_fmt_str = ""
        if self.playlist_mode in ("playlist", "range", "single"):
            # --- PLAYLIST CASE ---
            # For playlists, create a generic format string based on selected resolution.
            selected_text = self.quality_box.currentText()
            match = re.search(r'(\d{3,4})p', selected_text)
            if match and stream_type != "[audio only]":
                height = match.group(1)
                final_fmt_str = f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={height}]+bestaudio"
                final_fmt_str = f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]{audio_selection}/bestvideo[height<={height}]+bestaudio{audio_selection}"
            elif stream_type != "[audio only]":
            # Fallback for playlists if resolution isn't in the label
                final_fmt_str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
                final_fmt_str = f"bestvideo[ext=mp4]+bestaudio[ext=m4a]{audio_selection}/best"
            else:
        # For audio-only playlists, the original format ID is fine
                final_fmt_str = fmtid
        else:
            # --- SINGLE VIDEO CASE ---
            # For single videos, use the specific format ID the user selected.
            if stream_type == "[video only]":
                # If it's video-only, we must add the best audio part, preferring m4a.
                final_fmt_str = f"{fmtid}+bestaudio[ext=m4a]/bestaudio"
                final_fmt_str = f"{fmtid}+bestaudio[ext=m4a]{audio_selection}/bestaudio{audio_selection}"
            else:
                # If it already has audio, just use the ID.
                final_fmt_str = fmtid
                final_fmt_str = f"{fmtid}{audio_selection}"

        self.progress.setValue(0)
        self.status.setText("Starting download...")
        self.cancel_btn.show()
        self.download_btn.setEnabled(False)
        self.download_btn.hide()
        self.fetch_btn.setEnabled(False)
        self.url_input.setEnabled(False)  # Disable URL input during download
# Now, we need to pass the new 'final_fmt_str' to the thread
# Find the line that starts with 'self.thread = DownloadThread(...)'
# and change 'fmtid' to 'final_fmt_str'. # Disable URL input during download
        # Proxy is now system-wide, no need to pass to yt-dlp/spotdl
        try:
            self.thread = DownloadThread(
                url, self.folder, final_fmt_str, stream_type, self.fetched_title, self.fetched_thumbnail,
                embed_subs=self.embed_subs, subtitle_langs=self.selected_subtitle_langs,
                playlist_range=self.playlist_range,
                playlist_mode=self.playlist_mode,
                playlist_total=self.playlist_total,
                force_aac=False,
                proxy=None,
                use_vpn=self.use_vpn,
                trim_args=trim_args
            )
            self.thread.progress.connect(self.update_progress)
            self.thread.finished.connect(self.download_finished)
            self.thread.error.connect(self.download_error)
            self.thread.cancelled.connect(self.download_cancelled)
            self.thread.start()
        except Exception as e:
            QMessageBox.critical(self, "Thread Error", f"Failed to start download thread:\n{e}")
            self.reset_ui_after_download()

    def cancel_download(self):
        if hasattr(self, 'thread') and self.thread.isRunning():
            reply = QMessageBox.question(self, "Cancel Download", "Are you sure you want to cancel the current download?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.status.setText("Cancelling...")
                self.thread.cancel()

    def reset_ui_after_download(self):
        self.download_btn.setEnabled(True)
        self.download_btn.show()
        self.fetch_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        self.cancel_btn.hide()
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
        self.reset_ui_after_download()
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
        self.reset_ui_after_download()
        QMessageBox.critical(self, "Error", str(err))

    def download_cancelled(self):
        self.status.setText("Download cancelled by user.")
        self.progress.setValue(0)
        self.reset_ui_after_download()

    def clear_all(self):
        self.url_input.clear()
        self.quality_box.clear()
        self.quality_box.setEnabled(False)
        self.title_label.setText("")
        self.channel_label.setText("")
        self.duration_label.setText("")
        self.thumbnail_bg_label.clear()
        self.thumbnail_label.clear()
        self.subtitle_label.setText("")
        self.tracks_label.setText("")
        self.subtitle_btn.setEnabled(False)
        self.audio_btn.setEnabled(False)
        self.playlist_label.setText("")
        self.playlist_btn.setEnabled(False)
        self.status.setText("Ready.")
        self.available_subtitles = []
        self.selected_subtitle_langs = []
        self.available_audio_langs = []
        self.selected_audio_langs = []
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
            "<br>For issues/feedback, contact <b>Rohit</b>."
        )
        QMessageBox.information(self, "About / Help", txt)

    def show_history(self):
        dlg = HistoryDialog(self)
        dlg.exec_()

    def toggle_telegram_notifications(self, state):
        """Saves the state of the Telegram notification checkbox."""
        self.config["telegram_notifications_enabled"] = bool(state)
        save_config(self.config)
        if bool(state) and (not self.config.get("telegram_bot_token") or not self.config.get("telegram_chat_id")):
            QMessageBox.information(self, "Configuration Needed",
                                      "Telegram notifications are enabled, but your Bot Token or Chat ID is missing. "
                                      "Please configure them in the Telegram Settings.")
            self.open_telegram_settings()

    def open_telegram_settings(self):
        """Opens the dialog to configure Telegram settings."""
        dialog = TelegramSettingsDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            self.config["telegram_bot_token"] = dialog.token_input.text().strip()
            self.config["telegram_chat_id"] = dialog.chat_id_input.text().strip()
            save_config(self.config)
            self.status.setText("✅ Telegram settings saved.")


if __name__ == '__main__':
    try:
        from packaging import version
    except ImportError:
        print("Required 'packaging' library not found. Please run: pip install packaging")
        sys.exit(1)
    if MATPLOTLIB_AVAILABLE:
        try:
            import matplotlib
        except ImportError:
            print("Required 'matplotlib' library not found. Please run: pip install matplotlib")
            sys.exit(1)
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
