"""Core implementation for translate-movie console script (moved to src)."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from typing import Optional

# Load .env early so environment variables are available at import time
from dotenv import load_dotenv

load_dotenv()

DEBUG = os.environ.get("DEBUG", "FALSE") == "TRUE"


def debug(msg: str) -> None:
    if DEBUG:
        print(f"[DEBUG] {msg}", file=sys.stderr)


def run_cmd(cmd: list[str], check: bool = True, capture_output: bool = False, env=None) -> subprocess.CompletedProcess:
    debug(f"Running command: {' '.join(shlex.quote(c) for c in cmd)}")
    return subprocess.run(cmd, check=check, capture_output=capture_output, env=env)


def update_ytdlp(yt_dlp_path: str) -> None:
    print("=== Updating yt-dlp ===", file=sys.stderr)
    cmd = [
        "sudo",
        "wget",
        "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp",
        "-O",
        yt_dlp_path,
    ]
    run_cmd(cmd)
    run_cmd(["sudo", "chmod", "a+rx", yt_dlp_path])
    print("yt-dlp updated successfully", file=sys.stderr)
    run_cmd([yt_dlp_path, "--version"])  # show version


def download_video(url: str, output_dir: str, yt_dlp_path: str, output_name: str) -> str:
    print("=== Downloading video from URL ===", file=sys.stderr)
    debug(f"URL: {url}")
    debug(f"Output directory: {output_dir}")

    if not os.path.exists(yt_dlp_path) or not os.access(yt_dlp_path, os.X_OK):
        raise FileNotFoundError(f"yt-dlp not found at {yt_dlp_path}. Run --update-ytdlp to install.")

    # Remove old downloaded files
    for fname in os.listdir(output_dir):
        if fname.startswith(output_name + "."):
            try:
                os.remove(os.path.join(output_dir, fname))
            except Exception:
                pass

    out_template = os.path.join(output_dir, f"{output_name}.%(ext)s")
    run_cmd([yt_dlp_path, "-o", out_template, url])

    # pick newest matching file (safe listing + debug on failure)
    try:
        dir_list = os.listdir(output_dir)
    except Exception:
        dir_list = []

    candidates = [os.path.join(output_dir, f) for f in dir_list if f.startswith(output_name + ".")]
    if not candidates:
        debug(f"Looking in output_dir: {output_dir}")
        debug(f"Directory listing: {dir_list}")
        raise FileNotFoundError("Could not find downloaded video file")
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    downloaded = candidates[0]
    debug(f"Downloaded file: {downloaded}")
    return downloaded


def ensure_whisper(video_file: str, video_dir: str, whisper_model: str, whisper_lang: str) -> None:
    print(f"=== Step 1: Generating {whisper_lang} subtitles with Whisper ===")
    debug(f"Running Whisper with model: {whisper_model}, language: {whisper_lang}")
    run_cmd([
        "whisper",
        video_file,
        "--model",
        whisper_model,
        "--language",
        whisper_lang,
        "--output_dir",
        video_dir,
        "--output_format",
        "srt",
    ])


def translate_subtitles(
    translator_path: str,
    openai_model: str,
    srt_en: str,
    srt_out: str,
    source_lang: str,
    target_lang: str,
    batch_sizes: str,
    openai_api_key: str,
    openai_endpoint: str,
):
    print(f"=== Step 2: Translating subtitles to {target_lang} ===")

    env = os.environ.copy()
    env["OPENAI_API_KEY"] = openai_api_key
    env["OPENAI_BASE_URL"] = openai_endpoint

    debug(f"OpenAI endpoint: {openai_endpoint}")
    debug(f"OpenAI model: {openai_model}")
    debug(f"Translation: {source_lang} -> {target_lang}")
    debug(f"Batch sizes: {batch_sizes}")
    debug(f"Translator path: {translator_path}/cli/translator.mjs")
    debug(f"Input file: {srt_en}")
    debug(f"Output file: {srt_out}")

    node_cmd = [
        "node",
        os.path.join(translator_path, "cli", "translator.mjs"),
        "--from",
        source_lang,
        "--to",
        target_lang,
        "--model",
        openai_model,
        "--input",
        srt_en,
        "--output",
        srt_out,
        "--no-use-moderator",
        "--batch-sizes",
        batch_sizes,
    ]

    proc = subprocess.run(node_cmd, env=env)
    debug(f"Translation exit code: {proc.returncode}")
    if proc.returncode != 0:
        raise RuntimeError(f"Translation failed with exit code {proc.returncode}")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Video translation script using Whisper and LM Studio")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--file", dest="file", help="Translate local video file")
    group.add_argument("--net", dest="net", help="Download and translate video from URL (using yt-dlp)")
    parser.add_argument("--postprocess-only", dest="postprocess_only", help="Run post-processing (rename and cleanup) for given video file")
    parser.add_argument("--skip-whisper", action="store_true", help="Skip Whisper transcription (use existing .srt file)")
    parser.add_argument("--update-ytdlp", action="store_true", help="Update yt-dlp to latest version")
    return parser.parse_args(argv)


def get_config() -> dict:
    """Return a dict with configuration loaded from environment (with defaults)."""
    return {
        "WHISPER_MODEL": os.environ.get("WHISPER_MODEL", "large"),
        "WHISPER_LANGUAGE": os.environ.get("WHISPER_LANGUAGE", "en"),
        "OPENAI_ENDPOINT": os.environ.get("OPENAI_ENDPOINT", "http://localhost:20000/v1"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "lm-studio"),
        "OPENAI_MODEL": os.environ.get("OPENAI_MODEL", "qwen3-30b-a3b-instruct-2507"),
        "TRANSLATOR_PATH": os.path.expanduser(os.path.expandvars(os.environ.get("TRANSLATOR_PATH", "$HOME/tools/translateMovie/chatgpt-subtitle-translator"))),
        "SOURCE_LANG": os.environ.get("SOURCE_LANG", "en"),
        "TARGET_LANG": os.environ.get("TARGET_LANG", "pl"),
        "YT_DLP_PATH": os.environ.get("YT_DLP_PATH", "/usr/local/bin/yt-dlp"),
        "YT_DLP_OUTPUT_NAME": os.environ.get("YT_DLP_OUTPUT_NAME", "ytDownloadedFile"),
        "TRANSLATION_BATCH_SIZES": os.environ.get("TRANSLATION_BATCH_SIZES", "[5,10]"),
    }


def postprocess_subtitles(video_dir: str, video_name: str, target_lang: str) -> tuple[str, str]:
    """Rename original English srt to *_en.srt, move translated file to canonical name, and remove progress CSVs.

    Returns (srt_en_final, srt_canonical)
    """
    srt_en = os.path.join(video_dir, f"{video_name}.srt")
    srt_translated = os.path.join(video_dir, f"{video_name}_{target_lang}.srt")

    srt_en_final = os.path.join(video_dir, f"{video_name}_en.srt")
    try:
        if os.path.isfile(srt_en):
            try:
                os.replace(srt_en, srt_en_final)
            except Exception:
                import shutil

                shutil.copy2(srt_en, srt_en_final)
                os.remove(srt_en)
    except Exception as e:
        debug(f"Failed to rename original English srt: {e}")

    srt_canonical = os.path.join(video_dir, f"{video_name}.srt")
    try:
        if os.path.isfile(srt_translated):
            try:
                os.replace(srt_translated, srt_canonical)
            except Exception:
                import shutil

                shutil.copy2(srt_translated, srt_canonical)
                os.remove(srt_translated)
    except Exception as e:
        debug(f"Failed to move translated srt to canonical name: {e}")

    # Cleanup: remove any progress CSV files like *.progress_pl.csv
    try:
        for fname in os.listdir(video_dir):
            if fname.endswith(f".progress_{target_lang}.csv"):
                try:
                    os.remove(os.path.join(video_dir, fname))
                    debug(f"Removed progress CSV: {fname}")
                except Exception as e:
                    debug(f"Failed to remove {fname}: {e}")
    except Exception as e:
        debug(f"Error while cleaning progress files: {e}")

    return srt_en_final, srt_canonical


def main(argv: Optional[list[str]] = None) -> int:
    # Load configuration from environment (can be provided via .env)
    cfg = get_config()
    WHISPER_MODEL = cfg["WHISPER_MODEL"]
    WHISPER_LANGUAGE = cfg["WHISPER_LANGUAGE"]
    OPENAI_ENDPOINT = cfg["OPENAI_ENDPOINT"]
    OPENAI_API_KEY = cfg["OPENAI_API_KEY"]
    OPENAI_MODEL = cfg["OPENAI_MODEL"]
    TRANSLATOR_PATH = cfg["TRANSLATOR_PATH"]
    SOURCE_LANG = cfg["SOURCE_LANG"]
    TARGET_LANG = cfg["TARGET_LANG"]
    YT_DLP_PATH = cfg["YT_DLP_PATH"]
    YT_DLP_OUTPUT_NAME = cfg["YT_DLP_OUTPUT_NAME"]
    TRANSLATION_BATCH_SIZES = cfg["TRANSLATION_BATCH_SIZES"]

    # Parse CLI args early so we can handle different flows
    args = parse_args(argv)

    # If called without args, show help
    if argv is None and len(sys.argv) == 1:
        try:
            parse_args(["--help"])
        except SystemExit:
            return 0

    # Support running postprocessing alone for debugging/verification
    if getattr(args, "postprocess_only", None):
        video_file = args.postprocess_only
        if not os.path.isfile(video_file):
            print(f"Error: File not found: {video_file}", file=sys.stderr)
            return 4
        video_dir = os.path.dirname(video_file)
        video_name = os.path.splitext(os.path.basename(video_file))[0]
        srt_en_final, srt_canonical = postprocess_subtitles(video_dir, video_name, TARGET_LANG)
        print(f"English subtitles: {srt_en_final}")
        print(f"Translated subtitles: {srt_canonical}")
        return 0

    # If neither --file nor --net were provided, show error
    if not getattr(args, "file", None) and not getattr(args, "net", None):
        print("Error: one of --file or --net is required", file=sys.stderr)
        return 2

    if getattr(args, "update_ytdlp", False):
        try:
            update_ytdlp(YT_DLP_PATH)
            return 0
        except Exception as e:
            print(f"Error updating yt-dlp: {e}", file=sys.stderr)
            return 2

    # Determine source video
    if args.net:
        DOWNLOAD_DIR = os.path.expanduser(os.path.expandvars("$HOME/Downloads"))
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        try:
            video_file = download_video(args.net, DOWNLOAD_DIR, YT_DLP_PATH, YT_DLP_OUTPUT_NAME)
        except Exception as e:
            print(f"Error: Failed to download video: {e}", file=sys.stderr)
            return 3
        print(f"Downloaded: {video_file}")
    else:
        video_file = args.file
        if not os.path.isfile(video_file):
            print(f"Error: File not found: {video_file}", file=sys.stderr)
            return 4

    video_dir = os.path.dirname(video_file)
    video_name = os.path.splitext(os.path.basename(video_file))[0]

    srt_en = os.path.join(video_dir, f"{video_name}.srt")
    srt_translated = os.path.join(video_dir, f"{video_name}_{TARGET_LANG}.srt")

    debug(f"Video directory: {video_dir}")
    debug(f"Video name (no ext): {video_name}")
    debug(f"English SRT path: {srt_en}")
    debug(f"Translated SRT path: {srt_translated}")

    if not args.skip_whisper:
        try:
            ensure_whisper(video_file, video_dir, WHISPER_MODEL, WHISPER_LANGUAGE)
        except subprocess.CalledProcessError as e:
            print("Error: Whisper failed to generate subtitles", file=sys.stderr)
            debug(f"Whisper error: returncode={e.returncode}")
            return 5
        except Exception as e:
            print(f"Error running Whisper: {e}", file=sys.stderr)
            return 6
        if not os.path.isfile(srt_en):
            print(f"Error: Whisper failed to generate subtitles (missing {srt_en})", file=sys.stderr)
            return 7
    else:
        print("=== Step 1: Skipping Whisper (using existing subtitles) ===")
        if not os.path.isfile(srt_en):
            print(f"Error: Subtitle file not found: {srt_en}", file=sys.stderr)
            return 8

    # Translation
    try:
        translate_subtitles(
            TRANSLATOR_PATH,
            OPENAI_MODEL,
            srt_en,
            srt_translated,
            SOURCE_LANG,
            TARGET_LANG,
            TRANSLATION_BATCH_SIZES,
            OPENAI_API_KEY,
            OPENAI_ENDPOINT,
        )
    except Exception as e:
        print(f"Error: Translation failed - {e}", file=sys.stderr)
        debug(f"Listing files in output directory: {os.listdir(video_dir)}")
        return 9

    if not os.path.isfile(srt_translated):
        print("Error: Translation failed - output file not found", file=sys.stderr)
        return 10

    print("\n=== Done! ===")
    print(f"Video file: {video_file}")
    # Post-processing: keep original English subtitles as *_en.srt
    srt_en_final = os.path.join(video_dir, f"{video_name}_en.srt")
    try:
        if os.path.isfile(srt_en):
            # If target exists, overwrite it with the original English srt
            try:
                os.replace(srt_en, srt_en_final)
            except Exception:
                # fallback to copy+remove
                import shutil

                shutil.copy2(srt_en, srt_en_final)
                os.remove(srt_en)
    except Exception as e:
        debug(f"Failed to rename original English srt: {e}")

    # Move translated file to canonical name (remove _<lang> suffix)
    srt_canonical = os.path.join(video_dir, f"{video_name}.srt")
    try:
        if os.path.isfile(srt_translated):
            # If canonical exists, overwrite it
            try:
                os.replace(srt_translated, srt_canonical)
            except Exception:
                import shutil

                shutil.copy2(srt_translated, srt_canonical)
                os.remove(srt_translated)
    except Exception as e:
        debug(f"Failed to move translated srt to canonical name: {e}")

    # Cleanup: remove any progress CSV files like *.progress_pl.csv
    try:
        for fname in os.listdir(video_dir):
            if fname.endswith(f".progress_{TARGET_LANG}.csv"):
                try:
                    os.remove(os.path.join(video_dir, fname))
                    debug(f"Removed progress CSV: {fname}")
                except Exception as e:
                    debug(f"Failed to remove {fname}: {e}")
    except Exception as e:
        debug(f"Error while cleaning progress files: {e}")

    print(f"English subtitles: {srt_en_final}")
    print(f"Translated subtitles: {srt_canonical}")

    debug("Script finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
