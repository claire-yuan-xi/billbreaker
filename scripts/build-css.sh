#!/usr/bin/env sh
# Rebuilds billbreaker/static/css/app.css from input.css with the standalone
# Tailwind binary (pip install pytailwindcss). Add --watch while editing.
set -e
cd "$(dirname "$0")/.."
TAILWINDCSS_VERSION=v4.3.3 tailwindcss -i billbreaker/static/css/input.css -o billbreaker/static/css/app.css --minify "$@"
