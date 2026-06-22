#!/bin/sh
# Re-creates core/static/vendor/ (gitignored) by downloading pinned, self-hosted
# copies of the libraries that used to be loaded from CDNs (see README.md
# remediation notes). Safe to run repeatedly: every file is skipped if it
# already exists, so this only does network work on a fresh checkout/volume.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENDOR_DIR="$PROJECT_ROOT/core/static/vendor"

mkdir -p "$VENDOR_DIR/js" "$VENDOR_DIR/css"

fetch() {
    # $1 = path relative to vendor dir, $2 = source URL
    dest="$VENDOR_DIR/$1"
    if [ -f "$dest" ]; then
        return 0
    fi
    echo "fetch_vendor_assets: downloading $1"
    curl -sfL -o "$dest" "$2"
}

fetch js/jquery-3.6.0.min.js "https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"
fetch js/flatpickr.min.js "https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.js"
fetch css/flatpickr.min.css "https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.css"
fetch js/select2.min.js "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"
fetch css/select2.min.css "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css"
fetch js/sweetalert2.min.js "https://cdn.jsdelivr.net/npm/sweetalert2@11.26.25/dist/sweetalert2.all.min.js"
fetch css/sweetalert2.min.css "https://cdn.jsdelivr.net/npm/sweetalert2@11.26.25/dist/sweetalert2.min.css"
fetch js/fullcalendar.min.js "https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.js"
fetch js/sortable.min.js "https://cdn.jsdelivr.net/npm/sortablejs@1.15.3/Sortable.min.js"
fetch js/html5-qrcode.min.js "https://cdn.jsdelivr.net/npm/html5-qrcode@2.0.3/minified/html5-qrcode.min.js"
fetch js/signature_pad.umd.min.js "https://cdn.jsdelivr.net/npm/signature_pad@4.0.0/dist/signature_pad.umd.min.js"
fetch css/jquery.dataTables.min.css "https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css"
fetch css/buttons.dataTables.min.css "https://cdn.datatables.net/buttons/2.3.6/css/buttons.dataTables.min.css"
fetch js/jquery.dataTables.min.js "https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"
fetch js/dataTables.buttons.min.js "https://cdn.datatables.net/buttons/2.3.6/js/dataTables.buttons.min.js"
fetch js/buttons.html5.min.js "https://cdn.datatables.net/buttons/2.3.6/js/buttons.html5.min.js"
fetch js/jszip.min.js "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"
fetch js/pdfmake.min.js "https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.7/pdfmake.min.js"
fetch js/vfs_fonts.js "https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.7/vfs_fonts.js"

# Tailwind CSS is built locally (not downloaded) since it needs to be purged
# against this project's actual templates. Pinned to v3.4.17 to match the
# version the old cdn.tailwindcss.com play script was serving.
TAILWIND_CSS="$VENDOR_DIR/css/tailwind.css"
if [ ! -f "$TAILWIND_CSS" ]; then
    echo "fetch_vendor_assets: building tailwind.css"
    TAILWIND_BIN="/tmp/tailwindcss-cli"
    if [ ! -f "$TAILWIND_BIN" ]; then
        curl -sfL -o "$TAILWIND_BIN" "https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64"
        chmod +x "$TAILWIND_BIN"
    fi
    "$TAILWIND_BIN" \
        -i "$PROJECT_ROOT/core/static/css/tailwind-input.css" \
        -o "$TAILWIND_CSS" \
        -c "$PROJECT_ROOT/tailwind.config.js" \
        --minify
fi

echo "fetch_vendor_assets: done"
