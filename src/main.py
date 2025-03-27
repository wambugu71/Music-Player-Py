from time  import time
st  = time()
from flet import (
    AlertDialog,
    alignment,
    app,
    Audio,
    border_radius,
    BottomSheet,
    Colors,
    Column,
    Container,
    CrossAxisAlignment,
    CupertinoSlider,
    FilePicker,
    FilePickerResultEvent,
    FontWeight,
    IconButton,
    Icons,
    Image,
    ImageFit,
    LinearGradient,
    ListTile,
    ListView,
    MainAxisAlignment,
    margin,
    Page,
    PagePlatform,
    PopupMenuButton,
    PopupMenuItem,
    Row,
    RoundedRectangleBorder,
    Slider,
    SliderInteraction,
    Text,
    TextAlign,
    TextButton,
    TextOverflow,
    TextThemeStyle,
    Theme,
    VisualDensity,
    Icon,
    padding,
    ElevatedButton,
    ButtonStyle

)
from os import walk, path, makedirs, _exit, cpu_count
from threading import  Thread
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from io import BytesIO
from base64 import  b64encode
from typing import List, Optional
from json import dump, load
from hashlib import md5
from collections import OrderedDict
from flet_audio import Audio
from flet_permission_handler import PermissionHandler, PermissionType
print("Imports time  taken: {} s".format(time() - st))
# Constants
SETTINGS_FILE = "player_settings.json"
CACHE_DIR = path.join(path.dirname(path.abspath(__file__)), ".cache")
METADATA_CACHE_FILE = path.join(CACHE_DIR, "metadata_cache.json")
MAX_CACHE_ENTRIES = 1000 
SUPPORTED_EXTENSIONS = ['.mp3', '.flac']
UI_UPDATE_INTERVAL = 500 

makedirs(CACHE_DIR, exist_ok=True)

class LRUCache:
    def __init__(self, capacity: int):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key: str) -> Optional[any]:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: any) -> None:
        
        if key in self.cache:
            self.cache.move_to_end(key)
        elif len(self.cache) >= self.capacity:
            self.cache.popitem(last=False)
        self.cache[key] = value
        
    def save_to_file(self, file_path: str) -> None:
        """Save cacheable items to a file"""
        try:
            # Filter out non-serializable items (like images)
            serializable_cache = {k: v for k, v in self.cache.items() 
                                if isinstance(v, (dict, list, str, int, float, bool))}
            with open(file_path, 'w') as f:
                dump(serializable_cache, f)
        except Exception as e:
            pass
            #logger.error(f"Error saving cache to file: {e}")
            
    def load_from_file(self, file_path: str) -> None:
        """Load cache from a file"""
        if not path.exists(file_path):
            return
        try:
            with open(file_path, 'r') as f:
                loaded_cache = load(f)
            # Replace our cache with loaded data
            self.cache = OrderedDict(loaded_cache)
        except Exception as e:
            pass
            #logger.error(f"Error loading cache from file: {e}")


class BackgroundTaskQueue:
    def __init__(self, num_workers=cpu_count()):
        self.queue = Queue()
        self.executor = ThreadPoolExecutor(max_workers=num_workers)
        self.running = True
        self.workers  = [Thread(target=self._worker_thread, daemon=True).start() or Thread(target=self._worker_thread, daemon=True) for _ in range(num_workers)]
    def _worker_thread(self):
        while self.running:
            try:
                task, callback = self.queue.get(timeout=1)
                result = task()
                if callback:
                    callback(result)
                self.queue.task_done()
            except Empty:
                continue
            except Exception as e:
                #logger.error(f"Error in worker thread: {e}")
                # Ensure task_done is called only if task was retrieved
                if not self.queue.empty():
                    self.queue.task_done()
    
    def add_task(self, task, callback=None):
        """Add a task to be executed in the background"""
        self.queue.put((task, callback))
    
    def execute_with_callback(self, fn, callback, *args, **kwargs):
        """Execute a function with arguments in the background and call callback with result"""
        def task():
            return fn(*args, **kwargs)
        self.add_task(task, callback)
    
    def shutdown(self):
        """Shutdown the task queue and worker threads"""
        self.running = False
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=1)
        self.executor.shutdown(wait=False)

# Audio file metadata handler
class MetadataManager:
    def __init__(self, task_queue, update_ui_callback):
        self.task_queue = task_queue
        self.update_ui_callback = update_ui_callback
        self.metadata_cache = LRUCache(MAX_CACHE_ENTRIES)
        self.image_cache = LRUCache(MAX_CACHE_ENTRIES)
        self.color_cache = LRUCache(MAX_CACHE_ENTRIES)
        
        # Load metadata cache if available
        if path.exists(METADATA_CACHE_FILE):
            self.metadata_cache.load_from_file(METADATA_CACHE_FILE)
    
    def save_cache(self):
        """Save metadata cache to file"""
        self.metadata_cache.save_to_file(METADATA_CACHE_FILE)
    
    def get_file_hash(self, file_path):
        """Generate a hash of the file path and modification time for cache keys"""
        mod_time = path.getmtime(file_path)
        return md5(f"{file_path}_{mod_time}".encode()).hexdigest()
    
    def extract_metadata(self, file_path):
        """Extract metadata from an audio file"""
        file_hash = self.get_file_hash(file_path)
        
        # Check cache first
        cached_metadata = self.metadata_cache.get(file_hash)
        if cached_metadata:
            return cached_metadata
        
        metadata = {
            "title": path.basename(file_path),
            "artist": "Unknown Artist",
            "duration": 0,
            "has_cover": False
        }
        
        try:
            if file_path.lower().endswith('.flac'):
                audio = FLAC(file_path)
                metadata["title"] = audio.get('title', [path.basename(file_path)])[0]
                metadata["artist"] = audio.get('artist', ['Unknown Artist'])[0]
                metadata["duration"] = audio.info.length
                metadata["has_cover"] = len(audio.pictures) > 0
            elif file_path.lower().endswith('.mp3'):
                audio = MP3(file_path)
                tags = ID3(file_path) if audio.tags else None
                if tags and 'TIT2' in tags:
                    metadata["title"] = str(tags['TIT2'])
                if tags and 'TPE1' in tags:
                    metadata["artist"] = str(tags['TPE1'])
                metadata["duration"] = audio.info.length
                metadata["has_cover"] = tags and ('APIC:' in tags or 'APIC:Cover' in tags)
                
            # Cache the metadata
            self.metadata_cache.put(file_hash, metadata)
            return metadata
        except Exception as e:
            #logger.error(f"Error extracting metadata from {file_path}: {e}")
            return metadata
    
    def extract_cover_art(self, file_path):
        """Extract cover art from an audio file"""
        file_hash = self.get_file_hash(file_path)
        
        # Check image cache first
        cached_image = self.image_cache.get(file_hash)
        if cached_image:
            return cached_image
        
        try:
            if file_path.lower().endswith('.flac'):
                audio = FLAC(file_path)
                if audio.pictures:
                    image_data = audio.pictures[0].data
                    self.image_cache.put(file_hash, image_data)
                    return image_data
            elif file_path.lower().endswith('.mp3'):
                tags = ID3(file_path)
                for key in tags.keys():
                    if key.startswith('APIC:'):
                        image_data = tags[key].data
                        self.image_cache.put(file_hash, image_data)
                        return image_data
        except Exception as e:
            pass
            #logger.error(f"Error extracting cover art from {file_path}: {e}")
        
        return None
    
    def get_dominant_color(self, image_data, num_colors=3, thumbnail_size=(50, 50), sample_size=None):
        """Extract dominant color from image data"""
        if not image_data:
            return "#6c5ce7"  # Default purple color
        
        # Use a hash of the image data as cache key
        image_hash = md5(image_data[:500]).hexdigest()  # Use first 500B for faster hashing
        
        # Check color cache
        cached_color = self.color_cache.get(image_hash)
        if cached_color:
            return cached_color
        
        
        try:
            from PIL import Image as img_pil
            image_stream = img_pil.open(BytesIO(image_data))
            image_stream.thumbnail(thumbnail_size,img_pil.Resampling.LANCZOS)
            pixels = list(image_stream.getdata())
            dominant_color = pixels[10]
            if type(dominant_color)== int:
                dominant_color = (90,90,90)
            else:
                pass

            hex_color = '#{:02x}{:02x}{:02x}'.format(*dominant_color)
            
            # Cache the color
            self.color_cache.put(image_hash, hex_color)
            return hex_color
        except Exception as e:
            print(e)
            #logger.error(f"Error extracting dominant color: {e}")
            return "#6c5ce7"  # Default purple color
    
    def load_track_async(self, file_path, autoplay=True):
        """Load track metadata asynchronously"""
        def load_task():
            result = {
                "metadata": self.extract_metadata(file_path),
                "cover_art": self.extract_cover_art(file_path),
                "file_path": file_path,
                "autoplay": autoplay
            }
            
            # If we got cover art, extract the color in the background thread
            if result["cover_art"]:
                result["color"] = self.get_dominant_color(result["cover_art"])
            else:
                result["color"] = "#6c5ce7"  # Default purple
                
            return result
        
        self.task_queue.add_task(load_task, self.update_ui_callback)

# Utility functions
def load_tracks_from_folder_async(directory, task_queue, callback):
    """Load tracks from a folder asynchronously"""
    def task():
        audio_files = []
        for root, _, files in walk(directory):
            for file in files:
                if any(file.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                    audio_files.append(path.join(root, file))
        return sorted(audio_files)
    
    task_queue.add_task(task, callback)

def convert_milliseconds(ms):
    """Convert milliseconds to MM:SS format"""
    minutes = int(ms) // 60000
    seconds = (int(ms) % 60000) // 1000
    return f"{minutes:02d}:{seconds:02d}"

def convert_seconds(seconds):
    """Convert seconds to MM:SS format"""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}:{secs:02d}"

def main(page: Page):
    page.bgcolor = "#121212"
    page.padding = 1
    page.theme = Theme(
        color_scheme_seed=Colors.PURPLE,
        visual_density=VisualDensity.COMFORTABLE,
    )
    ph = PermissionHandler()
    page.overlay.append(ph)
    # Create background task queue
    task_queue = BackgroundTaskQueue(num_workers=cpu_count())
    # Colors dictionary
    colors = {
        "primary": "#6c5ce7",
        "background": "#121212",
        "card": "#1e1e1e",
        "text_primary": "#ffffff",
        "text_secondary": "#b3b3b3"
    }

    # Track list management
    class PlaylistState:
        def __init__(self):
            self.tracks: List[str] = []
            self.current_index: int = -1
            self.current_folder: str = ""
            self.load_settings()
            # Track update notifications
            self.need_tracks_update = False
            self.last_ui_update = 0

        def save_settings(self):
            settings = {
                "last_folder": self.current_folder
            }
            task_queue.add_task(
                lambda: self._save_settings_task(settings), 
              #  lambda _: #logger.info("Settings saved")
            )
            
        def _save_settings_task(self, settings):
            try:
                with open(SETTINGS_FILE, "w") as f:
                    dump(settings, f)
                return True
            except Exception as e:
                #logger.error(f"Error saving settings: {e}")
                return False

        def load_settings(self):
            try:
                if path.exists(SETTINGS_FILE):
                    with open(SETTINGS_FILE, "r") as f:
                        settings = load(f)
                        last_folder = settings.get("last_folder", "")
                        if last_folder and path.exists(last_folder):
                            self.current_folder = last_folder
                            # We'll load tracks asynchronously
                            return last_folder
            except Exception as e:
                pass
                #logger.error(f"Error loading settings: {e}")
            return None

    playlist_state = PlaylistState()
    def request_permission(e):
        o = ph.request_permission(e.control.data)
        page.update()
    # Initialize audio player
    audio1 = Audio(
        autoplay=True,
        src="sounds/sound.wav",
        volume=1,
        balance=0,
    )
    page.overlay.append(audio1)

    # Track the playing state
    is_playing = False

   
    
    # UI controls that need global access
    album_image = Image(
        src="logo.png",
        width=300,
        height=300,
        fit=ImageFit.COVER,
        border_radius=border_radius.all(10),
    )
    
    song_title = Text(
        "No song selected",
        size=24,
        color=colors["text_primary"],
        weight=FontWeight.BOLD,
        text_align=TextAlign.CENTER,overflow= TextOverflow.ELLIPSIS,
    )

    song_artist = Text(
        "Select a song to play",
        size=16,
        color=colors["text_secondary"],
        text_align=TextAlign.CENTER,overflow= TextOverflow.ELLIPSIS
    )

    time_current = Text("00:00", color=colors["text_secondary"], size=12)
    time_total = Text("00:00", color=colors["text_secondary"], size=12)
    
    play_button = IconButton(
        icon=Icons.PLAY_CIRCLE_FILL,
        icon_color=colors["text_primary"],
        icon_size=56,
        on_click=None,  # Will be set later
    )

    prev_button = IconButton(
        icon=Icons.SKIP_PREVIOUS_ROUNDED,
        icon_color=colors["text_primary"],
        icon_size=32,
        on_click=None,  # Will be set later
        disabled=True,
    )

    next_button = IconButton(
        icon=Icons.SKIP_NEXT_ROUNDED,
        icon_color=colors["text_primary"],
        icon_size=32,
        on_click=None,  # Will be set later
        disabled=True,
    )
    
    playlist_info = Text(
        "No playlist",
        color=colors["text_secondary"],
        size=12,
        text_align=TextAlign.CENTER,
    )
    
    folder_info = Text(
        "",
        color=colors["text_secondary"],
        size=12,
        text_align=TextAlign.CENTER,
    )

    gradient = LinearGradient(
        begin=alignment.top_center,
        end=alignment.bottom_center,
        colors=[colors["primary"], colors["background"]],
        stops=[0.0, 1.0],
    )
     # Create views
    player_view = Container(expand=True)
    playlist_view = Container(expand=True, border_radius= 8)
    progress_slider = None  # Will be initialized later
    def update_ui_colors(new_color):
        colors["primary"] = new_color
        gradient.colors[0] = new_color
        play_button.icon_color = colors["text_primary"]#new_color
        if progress_slider:
            progress_slider.active_color = new_color
            progress_slider.thumb_color = new_color
        page.update()

    def update_controls_state():
        if not playlist_state.tracks:
            prev_button.disabled = True
            next_button.disabled = True
        else:
            prev_button.disabled = playlist_state.current_index <= 0
            next_button.disabled = playlist_state.current_index >= len(playlist_state.tracks) - 1
        page.update()

    def update_playlist_info():
        if playlist_state.tracks:
            current = playlist_state.current_index + 1
            total = len(playlist_state.tracks)
            playlist_info.value = f"Track {current}/{total}"
            
            if playlist_state.current_folder:
                folder_name = path.basename(playlist_state.current_folder)
                folder_info.value = f"From: {folder_name}"
            else:
                folder_info.value = ""
        else:
            playlist_info.value = "No playlist"
            folder_info.value = "Please Select Folder"

    def update_tracks_list():
        """Update the tracks list view"""
        if not playlist_state.tracks:
            playlist_view.content = Column(
                [
                    playlist_header,
                    Container(
                        content=Text(
                            "No tracks loaded",
                            color=colors["text_secondary"],
                            text_align=TextAlign.CENTER,
                        ),
                        alignment=alignment.center,
                        expand=True,
                    )
                ],
                expand=True,
            )
            playlist_view.update()
            return
        list_tiles = [Container(content=ListTile(leading=IconButton(icon=Icons.MUSIC_NOTE), title=Text(f"{metadata_manager.extract_metadata(track_path)['title']}\n{metadata_manager.extract_metadata(track_path)['artist']}", color=Colors.BLACK), on_click=lambda x, index=i: play_track_at_index(index)), bgcolor=colors["card"] if i == playlist_state.current_index else Colors.WHITE, border_radius=10) for i, track_path in enumerate(playlist_state.tracks)]
        playlist_view.content = Column(
            [
                playlist_header,
                ListView(
                    expand=True,
                    spacing=10,
                    controls=list_tiles
                )
            ],
            expand=True,
        )
        
    

    def handle_loaded_folder_tracks(tracks):
        """Handle tracks loaded from a folder"""
        playlist_state.tracks = tracks
        if tracks:
            playlist_state.current_index = 0
            metadata_manager.load_track_async(tracks[0])
            update_controls_state()
            update_tracks_list()
        else:
            pass
            page.update()

    def handle_loaded_track_data(data):
        """Handle loaded track data from background thread"""
        if not data:
            return
            
        metadata = data["metadata"]
        cover_art = data["cover_art"]
        file_path = data["file_path"]
        autoplay = data["autoplay"]
        color = data.get("color", colors["primary"])
        
        # Update audio source
        audio1.pause()
        audio1.src = file_path
        audio1.update()
        
        # Update UI
        song_title.value = metadata["title"]
        song_artist.value = metadata["artist"]
        
        progress_slider.value = 0
        time_current.value = "00:00"
        time_total.value = convert_seconds(metadata["duration"])
        
        if cover_art:
            album_image.src_base64 =b64encode(cover_art).decode("utf-8")
            update_ui_colors(color)
        else:
            album_image.src = "logo.png"
            update_ui_colors(colors["primary"])
        
        play_button.icon = Icons.PAUSE_CIRCLE_FILLED if autoplay else Icons.PLAY_CIRCLE_FILL
        global is_playing
        is_playing = autoplay
        
        page.update()
        
        if autoplay:
            audio1.play()
        
        update_controls_state()
        update_playlist_info()
        update_tracks_list()

    # Initialize metadata manager
    metadata_manager = MetadataManager(task_queue, handle_loaded_track_data)
    
    def play_track_at_index(index):
        """Play track at specified index"""
        if 0 <= index < len(playlist_state.tracks):
            playlist_state.current_index = index
            metadata_manager.load_track_async(playlist_state.tracks[index], autoplay=True)
            update_tracks_list()

    def play_next_track(_):
        """Play the next track in the playlist"""
        global is_playing  # This line already exists, which is good
        
        if playlist_state.tracks and playlist_state.current_index < len(playlist_state.tracks) - 1:
            playlist_state.current_index += 1
            metadata_manager.load_track_async(playlist_state.tracks[playlist_state.current_index], autoplay=True)
        else:
            is_playing = False
            play_button.icon = Icons.PLAY_CIRCLE_FILL
            play_button.update()

    def play_previous_track(_):
        """Play the previous track in the playlist"""
        if playlist_state.tracks and playlist_state.current_index > 0:
            playlist_state.current_index -= 1
            metadata_manager.load_track_async(playlist_state.tracks[playlist_state.current_index], autoplay=True)

    def toggle_play(e):
        """Toggle play/pause"""
        global is_playing
        try:
            if play_button.icon == Icons.PLAY_CIRCLE_FILL:
                play_button.icon = Icons.PAUSE_CIRCLE_FILLED
                is_playing = True
                if audio1.get_current_position() > 0:
                    audio1.resume()
                else:
                    audio1.play()
            else:
                play_button.icon = Icons.PLAY_CIRCLE_FILL
                is_playing = False
                audio1.pause()
        except:
            pass
        play_button.update()

    # Set button callbacks
    play_button.on_click = toggle_play
    prev_button.on_click = play_previous_track
    next_button.on_click = play_next_track

    def check_track_end(e=None):
        """Check if the track has ended and play the next one"""
        global is_playing
        try:
            if is_playing  and audio1.get_duration() > 0:
                if audio1.get_current_position() >= audio1.get_duration() - 1000:  # Within 1 second of the end
                    play_next_track(None)
                    return True
        except:
            pass
        return False

    def on_position_changed(e):
        """Handle position changed events from audio player"""
        now = time() * 1000
        if playlist_state.last_ui_update + UI_UPDATE_INTERVAL > now:
            # Skip UI update if too soon
            return
            
        playlist_state.last_ui_update = now
            
        if not progress_slider.dragging:
            current_pos = convert_milliseconds(e.data)
            time_current.value = current_pos
            try:
                if audio1.get_duration():
                    progress_slider.value = (int(e.data) / audio1.get_duration()) * 100
                page.update()
            except:
                pass
                
        # Check if track ended
        check_track_end(e)

    def on_duration_changed(e):
        """Handle duration changed events from audio player"""
        duration_ms = int(e.data)
        time_total.value = convert_milliseconds(duration_ms)
        page.update()

    def on_slider_change_start(e):
        """Handle slider drag start"""
        progress_slider.dragging = True

    def on_slider_change_end(e):
        """Handle slider drag end"""
        progress_slider.dragging = False
        if audio1.get_duration():
            position = (progress_slider.value * audio1.get_duration()) / 100
            audio1.seek(int(position))
            if is_playing:
                audio1.resume()

    def on_slider_changed(e):
        """Handle slider value changes"""
        if e.data is not None and audio1.get_duration():
            position = (int(e.data) * audio1.get_duration()) / 100
            time_current.value = convert_milliseconds(position)
            page.update()

   
    # File picker setup
    def pick_files_result(e: FilePickerResultEvent):
        """Handle file picker result"""
        if e.files and len(e.files) > 0:
            file_path = e.files[0].path
            if file_path in playlist_state.tracks:
                playlist_state.current_index = playlist_state.tracks.index(file_path)
            else:
                playlist_state.tracks = [file_path]
                playlist_state.current_index = 0
            metadata_manager.load_track_async(file_path)
            update_controls_state()

    def pick_folder_result(e: FilePickerResultEvent):
        """Handle folder picker result"""
        if e.path:
            playlist_state.current_folder = e.path
            playlist_state.save_settings()
            load_tracks_from_folder_async(e.path, task_queue, handle_loaded_folder_tracks)

    pick_files_dialog = FilePicker(on_result=pick_files_result)
    pick_folder_dialog = FilePicker(on_result=pick_folder_result)
    page.overlay.extend([pick_files_dialog, pick_folder_dialog])

    def open_file_picker(_):
        """Open file picker dialog"""
        pick_files_dialog.pick_files(
            allow_multiple=False,
            allowed_extensions=["flac", "mp3"]
        )

    def open_folder_picker(_):
        """Open folder picker dialog"""
        pick_folder_dialog.get_directory_path()

    # Progress slider
    progress_slider = Slider(
        min=0,
        max=100,
        value=0,
        active_color=colors["primary"],
        inactive_color=Colors.with_opacity(0.2, colors["text_secondary"]),
        thumb_color=colors["primary"],
        on_change=on_slider_changed,
        on_change_start=on_slider_change_start,
        on_change_end=on_slider_change_end, interaction= SliderInteraction.TAP_AND_SLIDE
    )
    progress_slider.dragging = False

    # Create playlist header
    playlist_header = Row(
        [
            TextButton(
                text  = "Playlist",
                #color=colors["text_primary"],
               # weight=FontWeight.BOLD,
               # size=20,
               icon= Icons.MUSIC_NOTE,
            ),
            IconButton(icon  = Icons.CANCEL, on_click= lambda _ : page.close(song_list)),
        ],
        alignment=MainAxisAlignment.SPACE_BETWEEN,
    )
    alert = AlertDialog(
    modal=True,
    title=Text(
        "Player Info",
        size=24,
        weight="bold",
        color="#1a237e"  # Dark blue for title
    ),
    content=Container(
        padding=10,
        border_radius=8,
        content=Column(
            spacing=15,
            controls=[
                Container(
                    padding=15,
                    bgcolor="#e3f2fd",  # Light blue background
                    border_radius=8,
                    content=Column(
                        controls=[
                            Row(
                                alignment="start",
                                controls=[
                                    Icon(
                                        name="person",
                                        color="#1976d2",
                                        size=24
                                    ),
                                    Text(
                                        "Wambugu Kinyua",
                                        size=16,
                                        weight="w500",
                                        color="#1976d2"
                                    )
                                ]
                            )
                        ]
                    )
                ),Container(
                    padding=10,
                    bgcolor="#f5f5f5",  # Light gray background
                    border_radius=8,
                    content= Row(
                                alignment="start",
                                controls=[
                                    Icon(
                                        name="email",
                                        color="#1976d2",
                                        size=24
                                    ),
                                    Text(
                                        "wambugukinyua@duck.com",
                                        size=16,
                                        color="#1976d2"
                                    )
                                ]
                            )
                ),
                Container(
                    padding=10,
                    bgcolor="#f5f5f5",  # Light gray background
                    border_radius=8,
                    content=Row(
                        alignment="start",
                        controls=[
                            Icon(
                                name=Icons.FAVORITE_OUTLINE,
                                color="#616161",
                                size=20
                            ),
                            Text(
                                "Enjoy Free Software",
                                size=14,
                                color="#616161"
                            )
                        ]
                    )
                )
            ]
        )
    ),
    actions=[
        Container(
            content=ElevatedButton(
                text="Close",
                color="white",
                bgcolor="#1976d2",
                style=ButtonStyle(
                    shape={
                        "": RoundedRectangleBorder(radius=8),
                    },
                    padding=15,
                ),
                on_click=lambda _: page.close(alert)
            ),
            padding=padding.only(bottom=10, right=10)
        )
    ],
    actions_alignment="end",
    shape=RoundedRectangleBorder(radius=10)
)
    def handle_change(e):
        slider_value.value = str(e.control.value)
        audio1.playback_rate  = e.control.value
        page.update()
    def balance_left(_):
        audio1.balance -= 0.2
        balance_txt.value  = f"Balance: {float(audio1.balance):.1f}"
        audio1.update()

    def balance_right(_):
        audio1.balance += 0.2
        balance_txt.value  = f"Balance: {float(audio1.balance):.1f}"
        audio1.update()
    slider_value = Text("0.0")
   
    balance_txt  = Text(value= "Balance: 0.0")
    #song settings
    song_settings  = AlertDialog(modal= True,
     title=Row([Text("Sound  Settings",font_family= "roboto",theme_style= TextThemeStyle.HEADLINE_MEDIUM, weight= FontWeight.BOLD), IconButton(icon= Icons.CANCEL, on_click= lambda _: page.close(song_settings))], alignment= MainAxisAlignment.SPACE_BETWEEN),
        content= Container(
            content= Column(
                [
                    Text(value= "playback rate", weight= FontWeight.BOLD),
                    slider_value,
                     CupertinoSlider(value= audio1.playback_rate,
            divisions=6,
            max=2,min= 0.5, on_change= handle_change)
                ,
                balance_txt,
                Row([IconButton(icon= Icons.ADD,on_click =  balance_left, icon_color= colors["primary"]), IconButton(icon= Icons.REMOVE,icon_color= colors["primary"], on_click=balance_right)], alignment= MainAxisAlignment.SPACE_AROUND)]
            )
        ,width= 500)
    )
    song_list = BottomSheet(
            
                content= playlist_view
                , shape= RoundedRectangleBorder(radius=10)
        )

    def  open_settings(e):
        o = ph.open_app_settings()
    #def  audio_settings(e):

    # Main player layout
    player_view.content = Column(
        [
            Row(
                [
                   Text(value= "")
                ]
            ),
            # Top bar
            Row(
                [
                    Text(
                        "Now Playing",
                        color=colors["text_primary"],
                        weight=FontWeight.BOLD,
                    ),
                    PopupMenuButton(
                        items=[
                            PopupMenuItem(
                                text="Select File",
                                icon=Icons.FILE_OPEN,
                                on_click=open_file_picker
                            ),
                            PopupMenuItem(
                                text="Select Folder",
                                icon=Icons.FOLDER_OPEN,
                                on_click=open_folder_picker, data= PermissionType.AUDIO
                            ),
                            TextButton(text= "Songlist", icon= Icons.PLAYLIST_PLAY, on_click= lambda _ : page.open(song_list))
                            ,
                            TextButton(text= "Grant Permissions", icon= Icons.PERM_DEVICE_INFORMATION, on_click= open_settings)
                            , TextButton(text= "Audio Settings", icon= Icons.SETTINGS, on_click= lambda  _ : page.open(song_settings))
                            
                           # TextButton(text= "Settings", icon= Icons.SETTINGS,data = PermissionType.AUDIO, on_click= request_permission)
                            ,TextButton(text= "About", icon= Icons.INFO,on_click=lambda _ :page.open(alert))
                        ],
                        icon=Icons.MORE_VERT,
                        icon_color=colors["text_primary"]
                    ),
                ],
                alignment=MainAxisAlignment.SPACE_BETWEEN,
            ),
            
            # Album cover
            Container(
                content= album_image,
                margin=margin.only(top=30, bottom=30),
                alignment=alignment.center,
                border_radius= 10, ignore_interactions= True, width= "auto"
            ),
            
            # Song info
            song_title,
            song_artist,
            
            # Progress bar
            Container(
                content=Column(
                    [
                        progress_slider,
                        Row(
                            [time_current, time_total],
                            alignment=MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=0,
                ),
                margin=margin.only(top=20, bottom=20),
            ),
            
            # Controls
            Row(
                [prev_button, play_button, next_button],
                alignment=MainAxisAlignment.CENTER,
            ),
            
            # Playlist info
            Container(
                content=Row(
                    [playlist_info, folder_info],
                    spacing=5,
                alignment= MainAxisAlignment.SPACE_EVENLY,
                ),
                margin=margin.only(top=20),
            ),
        ],
        horizontal_alignment=CrossAxisAlignment.CENTER, #expand= True
    )

    # Initialize playlist view with header
    playlist_view.content = Column(
        [
            playlist_header,
            Container(
                content=Text(
                    "No tracks loaded",
                    color=colors["text_secondary"],
                    text_align=TextAlign.CENTER,
                ),
                alignment=alignment.center,
                expand=True,
            )
        ],
        expand=True,
    )

    # Add the main container that will switch between views
    player_main  = Container(
            content=player_view,
            expand=True,
            gradient=gradient, )
    page.add(
        player_main
    )
    


    # Set up audio events
    audio1.on_position_changed = on_position_changed
    audio1.on_duration_changed = on_duration_changed

    # Periodic UI updates and state checks
    def periodic_ui_update(e):
        """Periodically update UI elements and check for track end"""
        # If the track has reached the end, this will handle playing the next track
        check_track_end()
        
        # If the playlist view needs updating and is visible
        if playlist_state.need_tracks_update:
            update_tracks_list()
            playlist_state.need_tracks_update = False

    # Set up periodic timer for UI updates (every 1 second)
    #page.set_interval(periodic_ui_update, 1000)
    
    # Load initial tracks if a folder was previously saved
    last_folder = playlist_state.current_folder
    if last_folder and path.exists(last_folder):
        load_tracks_from_folder_async(last_folder, task_queue, handle_loaded_folder_tracks)
    
    # Update initial controls state
    update_controls_state()

    def event(e):
        if e.data=='detach' and page.platform == PagePlatform.ANDROID:
            _exit(1)

    page.on_app_lifecycle_state_change = event
    # Set up cleanup handler
    def on_close(e):
        """Clean up resources when app is closed"""
        # Save metadata cache
        metadata_manager.save_cache()
        # Shutdown task queue
        task_queue.shutdown()
        
    page.on_close = on_close

if __name__ == "__main__":
    app(target=main, assets_dir="assets")                            
