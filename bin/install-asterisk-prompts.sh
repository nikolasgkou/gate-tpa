#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${repo_root}/infra/asterisk/sounds/en/gate"
target_dir="/usr/share/asterisk/sounds/en/gate"

sudo install -d -o asterisk -g asterisk -m 0755 "${target_dir}"
sudo install -o asterisk -g asterisk -m 0644 "${source_dir}"/*.ulaw "${target_dir}/"
