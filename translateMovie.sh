#!/bin/bash
# Save as ~/project/translate/translate.sh
# Video translation script with Whisper + LM Studio

# ============================================
# CONFIGURATION
# ============================================
WHISPER_MODEL="large"
WHISPER_LANGUAGE="en"
OPENAI_ENDPOINT="http://localhost:20000/v1"
OPENAI_API_KEY="lm-studio"
OPENAI_MODEL="qwen3-30b-a3b-instruct-2507"
TRANSLATOR_PATH="$HOME/tools/translateMovie/chatgpt-subtitle-translator"
SOURCE_LANG="en"
TARGET_LANG="pl"
YT_DLP_PATH="/usr/local/bin/yt-dlp"
YT_DLP_OUTPUT_NAME="ytDownloadedFile"
TRANSLATION_BATCH_SIZES="[3,5]"

# ============================================
# FUNCTIONS
# ============================================

show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Video translation script using Whisper and LM Studio

OPTIONS:
    --file <file>           Translate local video file
    --net <url>             Download and translate video from URL (using yt-dlp)
    --skip-whisper          Skip Whisper transcription (use existing .srt file)
    --update-ytdlp          Update yt-dlp to latest version
    -h, --help              Show this help message

ENVIRONMENT:
    DEBUG=TRUE              Enable debug output

EXAMPLES:
    # Translate local file
    $0 --file video.mp4

    # Download and translate from YouTube
    $0 --net https://youtube.com/watch?v=...

    # Use existing subtitles (skip Whisper)
    $0 --file video.mp4 --skip-whisper

    # Update yt-dlp
    $0 --update-ytdlp

    # Debug mode
    DEBUG=TRUE $0 --file video.mp4

CONFIGURATION:
    Edit the script to modify:
    - WHISPER_MODEL (default: large)
    - OPENAI_ENDPOINT (default: http://localhost:20000/v1)
    - OPENAI_MODEL (default: qwen3-30b-a3b-instruct-2507)
    - SOURCE_LANG (default: en)
    - TARGET_LANG (default: pl)
    - TRANSLATION_BATCH_SIZES (default: [5,10])

EOF
}

debug() {
    if [ "$DEBUG" = "TRUE" ]; then
        echo "[DEBUG] $1" >&2
    fi
}

update_ytdlp() {
    echo "=== Updating yt-dlp ===" >&2
    sudo wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O "$YT_DLP_PATH"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to download yt-dlp" >&2
        exit 1
    fi
    
    sudo chmod a+rx "$YT_DLP_PATH"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to set permissions on yt-dlp" >&2
        exit 1
    fi
    
    echo "yt-dlp updated successfully" >&2
    "$YT_DLP_PATH" --version
    exit 0
}

download_video() {
    local url="$1"
    local output_dir="$2"
    
    echo "=== Downloading video from URL ===" >&2
    debug "URL: $url"
    debug "Output directory: $output_dir"
    
    if [ ! -x "$YT_DLP_PATH" ]; then
        echo "Error: yt-dlp not found at $YT_DLP_PATH" >&2
        echo "Run: $0 --update-ytdlp" >&2
        exit 1
    fi
    
    # Remove old downloaded file if exists
    rm -f "$output_dir/${YT_DLP_OUTPUT_NAME}".* 2>/dev/null
    
    # Download video with fixed filename
    "$YT_DLP_PATH" -o "$output_dir/${YT_DLP_OUTPUT_NAME}.%(ext)s" "$url" >&2
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to download video" >&2
        exit 1
    fi
    
    # Find the downloaded file
    local downloaded_file=$(ls -t "$output_dir/${YT_DLP_OUTPUT_NAME}".* 2>/dev/null | head -1)
    
    if [ -z "$downloaded_file" ]; then
        echo "Error: Could not find downloaded video file" >&2
        exit 1
    fi
    
    debug "Downloaded file: $downloaded_file"
    
    # Return only the file path
    echo "$downloaded_file"
}

# ============================================
# PARSE ARGUMENTS
# ============================================

SKIP_WHISPER=false
VIDEO_FILE=""
VIDEO_URL=""
MODE=""

# Show help if no arguments
if [ $# -eq 0 ]; then
    show_help
    exit 1
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --file)
            MODE="file"
            VIDEO_FILE="$2"
            shift 2
            ;;
        --net)
            MODE="net"
            VIDEO_URL="$2"
            shift 2
            ;;
        --skip-whisper)
            SKIP_WHISPER=true
            shift
            ;;
        --update-ytdlp)
            update_ytdlp
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown option: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
done

# Validate arguments
if [ -z "$MODE" ]; then
    echo "Error: Must specify either --file or --net"
    echo ""
    show_help
    exit 1
fi

debug "Script started"
debug "Mode: $MODE"

# ============================================
# HANDLE VIDEO SOURCE
# ============================================

if [ "$MODE" = "net" ]; then
    # Download video from URL
    DOWNLOAD_DIR="$HOME/Downloads"
    mkdir -p "$DOWNLOAD_DIR"
    
    VIDEO_FILE=$(download_video "$VIDEO_URL" "$DOWNLOAD_DIR")
    if [ -z "$VIDEO_FILE" ]; then
        echo "Error: Failed to download video"
        exit 1
    fi
    echo "Downloaded: $VIDEO_FILE"
elif [ "$MODE" = "file" ]; then
    # Use local file
    if [ ! -f "$VIDEO_FILE" ]; then
        echo "Error: File not found: $VIDEO_FILE"
        exit 1
    fi
fi

# Get full path to video file
VIDEO_DIR=$(dirname "$VIDEO_FILE")
VIDEO_NAME=$(basename "$VIDEO_FILE" | sed 's/\.[^.]*$//')

debug "Video directory: $VIDEO_DIR"
debug "Video name (no ext): $VIDEO_NAME"

# Paths to subtitle files
SRT_EN="${VIDEO_DIR}/${VIDEO_NAME}.srt"
SRT_TRANSLATED="${VIDEO_DIR}/${VIDEO_NAME}_${TARGET_LANG}.srt"

debug "English SRT path: $SRT_EN"
debug "Translated SRT path: $SRT_TRANSLATED"

# ============================================
# STEP 1: WHISPER TRANSCRIPTION
# ============================================

if [ "$SKIP_WHISPER" = false ]; then
    echo "=== Step 1: Generating ${SOURCE_LANG} subtitles with Whisper ==="
    debug "Running Whisper with model: $WHISPER_MODEL, language: $WHISPER_LANGUAGE"
    
    whisper "$VIDEO_FILE" \
        --model "$WHISPER_MODEL" \
        --language "$WHISPER_LANGUAGE" \
        --output_dir "$VIDEO_DIR" \
        --output_format srt

    if [ ! -f "$SRT_EN" ]; then
        echo "Error: Whisper failed to generate subtitles"
        debug "Expected file not found: $SRT_EN"
        exit 1
    fi
    debug "Whisper completed successfully"
else
    echo "=== Step 1: Skipping Whisper (using existing subtitles) ==="
    if [ ! -f "$SRT_EN" ]; then
        echo "Error: Subtitle file not found: $SRT_EN"
        debug "Existing SRT file not found"
        exit 1
    fi
    debug "Using existing SRT file: $SRT_EN"
fi

# ============================================
# STEP 2: TRANSLATION
# ============================================

echo "=== Step 2: Translating subtitles to ${TARGET_LANG} ==="
export OPENAI_API_KEY="$OPENAI_API_KEY"
export OPENAI_BASE_URL="$OPENAI_ENDPOINT"

debug "OpenAI endpoint: $OPENAI_ENDPOINT"
debug "OpenAI model: $OPENAI_MODEL"
debug "Translation: $SOURCE_LANG -> $TARGET_LANG"
debug "Batch sizes: $TRANSLATION_BATCH_SIZES"
debug "Translator path: ${TRANSLATOR_PATH}/cli/translator.mjs"
debug "Input file: $SRT_EN"
debug "Output file: $SRT_TRANSLATED"

node "${TRANSLATOR_PATH}/cli/translator.mjs" \
    --from "$SOURCE_LANG" \
    --to "$TARGET_LANG" \
    --model "$OPENAI_MODEL" \
    --input "$SRT_EN" \
    --output "$SRT_TRANSLATED" \
    --no-use-moderator \
    --batch-sizes "$TRANSLATION_BATCH_SIZES"

TRANSLATION_EXIT_CODE=$?
debug "Translation exit code: $TRANSLATION_EXIT_CODE"

# Check if translation created output file
if [ ! -f "$SRT_TRANSLATED" ]; then
    echo "Error: Translation failed - output file not found"
    debug "Expected output file: $SRT_TRANSLATED"
    debug "Listing files in output directory:"
    debug "$(ls -la "$VIDEO_DIR"/*.srt 2>/dev/null)"
    exit 1
fi

debug "Translation completed successfully"

# ============================================
# DONE
# ============================================

echo ""
echo "=== Done! ==="
echo "Video file: $VIDEO_FILE"
echo "English subtitles: $SRT_EN"
echo "Translated subtitles: $SRT_TRANSLATED"

debug "Script finished"
