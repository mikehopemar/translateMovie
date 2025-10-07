
# translateMovie

A small CLI to generate subtitles (Whisper) and translate them (external translator) for video files or online videos.

Features

- Download videos using `yt-dlp` and save them to your Downloads folder
- Generate subtitles (SRT) using `whisper`
- Translate subtitles using a Node-based translator (configurable path)
- Post-process subtitles:
	- keep the original English subtitles as `video_name_en.srt`
	- move translated subtitles to the canonical `video_name.srt`
	- remove temporary progress CSV files like `*.progress_pl.csv`

Installation

This project uses Poetry. From the repository root:

```bash
poetry install
```

Run

- Translate a remote video (download, transcribe, translate):

```bash
poetry run translate-movie --net <youtube-url>
```

- Translate a local video file:

```bash
poetry run translate-movie --file /path/to/video.mp4
```

- Run post-processing only (rename subtitles and cleanup) for an existing video file and its subtitle files:

```bash
poetry run translate-movie --postprocess-only /path/to/video.mp4
```

Configuration

Create a `.env` in the project root (see `.env.example`) or set environment variables directly. Important environment variables:

- `WHISPER_MODEL` (default: `large`)
- `WHISPER_LANGUAGE` (default: `en`)
- `OPENAI_ENDPOINT` (default: `http://localhost:20000/v1`)
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (default: `qwen3-30b-a3b-instruct-2507`)
- `TRANSLATOR_PATH` (path to the Node translator project)
- `SOURCE_LANG` and `TARGET_LANG` (e.g. `en` and `pl`)
- `YT_DLP_PATH` (path to `yt-dlp`, default `/usr/local/bin/yt-dlp`)
- `YT_DLP_OUTPUT_NAME` (default: `ytDownloadedFile`)
- `TRANSLATION_BATCH_SIZES` (default: `[5,10]`)
- `DEBUG` (set to `TRUE` to enable debug logs)

Notes

- The CLI calls external tools (`yt-dlp`, `whisper`, `node`) — ensure they are installed and available in PATH or point the environment variables to their locations.
- If Whisper or the translator require GPU and you hit resource issues, adjust your environment or model choice.

yt-dlp: selecting quality
------------------------

You can control the video quality yt-dlp downloads via the `YT_DLP_FORMAT` environment variable (see `.env` / `.env.example`). Useful examples:

- Prefer best available up to 360p (recommended if you want to avoid 720p/4K):

```bash
YT_DLP_FORMAT="bestvideo[height<=360]+bestaudio/best"
```

- Require exactly 360p (if not available, yt-dlp will fall back to `best`):

```bash
YT_DLP_FORMAT="bestvideo[height=360]+bestaudio/best"
```

- Force mp4 container after merge:

```bash
# pass --merge-output-format mp4 to yt-dlp (not currently set by default)
yt-dlp -f "bestvideo[height<=360]+bestaudio/best" 'URL' --merge-output-format mp4
```

How to override in this project

- Edit `.env` and set `YT_DLP_FORMAT` to any selector you like. The wrapper forwards it to yt-dlp as `-f` when downloading.
- You can also pass any yt-dlp flags by editing the download command in `src/translate_movie/core.py` if you need fine-grained control.

License

See the `LICENSE` file.
