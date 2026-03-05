#!/usr/bin/env bash
# LocalTaskClaw — full uninstall
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

INSTALL_DIR="$HOME/.localtaskclaw"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo ""
echo -e "${BOLD}${RED}LocalTaskClaw — Uninstall${NC}"
echo ""

# Show what will be removed
echo -e "${BOLD}Will be removed:${NC}"
echo ""

[[ -d "$INSTALL_DIR" ]] && echo -e "  ${YELLOW}~/.localtaskclaw/${NC}  (app, venv, DB, secrets, workspace)"
[[ -L "$HOME/bin/ltc" ]] && echo -e "  ${YELLOW}~/bin/ltc${NC}  (CLI symlink)"
[[ -L "/usr/local/bin/ltc" ]] && echo -e "  ${YELLOW}/usr/local/bin/ltc${NC}  (CLI symlink)"

if [[ "$(uname -s)" == "Darwin" ]]; then
  for f in "$LAUNCH_DIR"/io.localtaskclaw.*.plist; do
    [[ -f "$f" ]] && echo -e "  ${YELLOW}$(basename "$f")${NC}  (LaunchAgent)" && break
  done
else
  for f in "$SYSTEMD_DIR"/localtaskclaw-*.service; do
    [[ -f "$f" ]] && echo -e "  ${YELLOW}$(basename "$f")${NC}  (systemd unit)" && break
  done
fi

echo ""
echo -e "${RED}${BOLD}This is irreversible! All data, secrets and workspace will be deleted.${NC}"
echo ""
echo -ne "${BOLD}Continue? [y/N]${NC}: "
read -r CONFIRM
[[ "$CONFIRM" =~ ^[Yy] ]] || { echo "Cancelled."; exit 0; }

echo ""

# 1. Stop services
echo -e "[1/5] ${BOLD}Stopping services...${NC}"

if [[ "$(uname -s)" == "Darwin" ]]; then
  for f in "$LAUNCH_DIR"/io.localtaskclaw.*.plist; do
    if [[ -f "$f" ]]; then
      launchctl unload "$f" 2>/dev/null || true
      echo "  unloaded $(basename "$f")"
    fi
  done
else
  systemctl --user stop localtaskclaw-core localtaskclaw-bot 2>/dev/null || true
  systemctl --user disable localtaskclaw-core localtaskclaw-bot 2>/dev/null || true
  echo "  stopped systemd services"
fi

pkill -f '\.localtaskclaw/.*main\.py' 2>/dev/null || true
pkill -f '\.localtaskclaw/.*uvicorn' 2>/dev/null || true

# 2. Remove LaunchAgent / systemd files
echo -e "[2/5] ${BOLD}Removing autostart...${NC}"

if [[ "$(uname -s)" == "Darwin" ]]; then
  rm -f "$LAUNCH_DIR"/io.localtaskclaw.*.plist 2>/dev/null
  echo "  removed LaunchAgent plists"
else
  rm -f "$SYSTEMD_DIR"/localtaskclaw-*.service 2>/dev/null
  systemctl --user daemon-reload 2>/dev/null || true
  echo "  removed systemd units"
fi

# 3. Remove CLI symlink
echo -e "[3/5] ${BOLD}Removing CLI...${NC}"

for link in "$HOME/bin/ltc" "/usr/local/bin/ltc"; do
  if [[ -L "$link" ]]; then
    rm -f "$link"
    echo "  removed $link"
  fi
done

# 4. Remove install directory
echo -e "[4/5] ${BOLD}Removing files...${NC}"

if [[ -d "$INSTALL_DIR" ]]; then
  rm -rf "$INSTALL_DIR"
  echo "  removed $INSTALL_DIR"
else
  echo "  $INSTALL_DIR not found (already removed?)"
fi

# 5. Clean up logs
echo -e "[5/5] ${BOLD}Cleaning logs...${NC}"
rm -f /tmp/localtaskclaw-core.log /tmp/localtaskclaw-bot.log 2>/dev/null
echo "  removed /tmp/localtaskclaw-*.log"

echo ""
echo -e "${GREEN}${BOLD}LocalTaskClaw fully removed.${NC}"
echo ""
