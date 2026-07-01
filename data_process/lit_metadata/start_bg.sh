#!/usr/bin/env bash
# Start lit_metadata crawler in tmux session.
# Usage: bash start_bg.sh

set -euo pipefail

SESSION="lit_crawl"

cd "$(dirname "$0")"

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Session '$SESSION' already exists. Attach: tmux attach -t $SESSION"
    exit 1
fi

tmux new-session -d -s "$SESSION" "python main.py; echo '--- Crawl finished ---'; exec bash"
echo "Crawler started in tmux session '$SESSION'"
echo "  Attach: tmux attach -t $SESSION"
echo "  Detach: Ctrl+b d"
echo "  Kill:   tmux kill-session -t $SESSION"
