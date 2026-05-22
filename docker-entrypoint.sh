#!/bin/sh
set -eu

if [ "${UPDATE_YTDLP_ON_START:-true}" = "true" ]; then
  echo "Updating yt-dlp before startup..."
  python -m pip install --no-cache-dir --upgrade yt-dlp
fi

python -m yt_dlp --version
exec "$@"
