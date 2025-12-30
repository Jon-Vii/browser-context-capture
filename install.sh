#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/src/capture.py"
OUTPUT_DIR="$HOME/memex/browser"
PLIST_NAME="com.memex.browser-capture.plist"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "Installing Browser Context Capture..."

# Create output directory
mkdir -p "$OUTPUT_DIR"
echo "✓ Created $OUTPUT_DIR"

# Unload existing job if present
if launchctl list | grep -q "com.memex.browser-capture"; then
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    echo "✓ Unloaded existing launchd job"
fi

# Create plist with correct paths
sed -e "s|__SCRIPT_PATH__|$SCRIPT_PATH|g" \
    -e "s|__OUTPUT_DIR__|$OUTPUT_DIR|g" \
    "$PLIST_SRC" > "$PLIST_DST"
echo "✓ Installed launchd plist to $PLIST_DST"

# Load the job
launchctl load "$PLIST_DST"
echo "✓ Loaded launchd job"

# Write source location to output dir for clarity
echo "$SCRIPT_DIR" > "$OUTPUT_DIR/.installed-from"
echo "✓ Recorded source location"

# Run initial capture (backfill)
echo "Running initial capture (this may take a moment)..."
python3 "$SCRIPT_PATH"
echo "✓ Initial capture complete"

echo ""
echo "Installation complete!"
echo "  - History digests: $OUTPUT_DIR"
echo "  - Script source:   $SCRIPT_DIR"
echo "  - Script runs hourly in the background"
echo ""
echo "To uninstall:"
echo "  launchctl unload $PLIST_DST"
echo "  rm $PLIST_DST"
echo ""
echo "Note: Do not delete $SCRIPT_DIR - the hourly job depends on it."
