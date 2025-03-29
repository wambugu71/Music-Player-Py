# Music Player

A modern and feature-rich music player built with Python, that can run on all platforms. Yes you heard  that right!
Running  python  on  all platforms (Android, IOS, MacOS, Windows & Linux and web browsers) with mear  native  performance no lags.
![Main app](screenshot.png)
```
Leave a star!
``` 
## Features

*   **Sleek User Interface:**  A visually appealing and intuitive user interface for a seamless music listening experience.
*   **Cross-Platform Compatibility:** Runs on Windows, macOS, Linux, and web browsers.
*   **Audio Format Support:** Supports popular audio formats such as MP3 and FLAC.
*   **Playlist Management:** Create and manage playlists to organize your favorite tracks.
*   **Folder Playback:** Load and play tracks directly from folders.
*   **Metadata Extraction:** Automatically extracts song title, artist, and album art from audio files.
*   **Cover Art Display:** Displays album cover art for a visually enhanced experience.
*   **Playback Controls:** Standard playback controls including play/pause, skip forward/backward.
*   **Progress Tracking:**  A slider to track the song's progress and allow seeking to specific points.
*   **Volume Control:** Adjust the volume to your desired level.
*   **Light and Dark Themes:** Choose between light and dark themes for comfortable viewing in any environment.
*   **Background Playback:**  Continue listening to music even when the app is minimized.
*   **Customizable Themes**: The UI colors are extracted directly from the song's cover art

## Technologies Used

*   [Flet](https://flet.dev/): A Python UI framework for building cross-platform applications.
*   `mutagen`: For audio metadata extraction.
*   `flet_audio`: For audio playback.
*   `flet-permission-handler`: For handling  audio permissions.
*   `PIL (Pillow)`: For image processing (cover art extraction and color analysis).
*   `threading`: For background tasks and asynchronous operations.
*   `queue`: For managing background task queue.
*   `concurrent.futures`: For thread pool execution.
*   `hashlib`: For generating file hashes for caching.
*   `json`: For saving and loading settings.

## Installation

1.  **Prerequisites:**

    *   Python 3.7+
    *   `pip` package installer

2.  **Clone the repository:**

    ```bash
    git clone https://github.com/wambugu71/Music-Player-Py
    cd Music-Player-Py
    ```

3.  **Install the dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

    *   Create `requirements.txt`:

    ```bash
    pip freeze > requirements.txt
    ```

4.  **Run the application:**
In  am already existing python  environment.
    ```bash
    python main.py
    ```
For the  package  (Android, windows and  linux) find  the  releases/ Action results applications.

## Usage

1.  **Select Music Folder:** Click the "Select Folder" option in the menu to choose a folder containing your music files.
2.  **Browse and Play:** The music player will load the tracks from the selected folder.  You can then browse the playlist and select a track to play.
3.  **Controls:** Use the play/pause, skip forward/backward buttons to control playback.
4.  **Progress:** Use the slider to jump to different points in the song.
5.  **Volume:** Use the volume slider to adjust the volume.

## Folder Structure
