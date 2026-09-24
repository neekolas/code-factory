#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 1 || ( $# -eq 1 && $1 != --uninstall ) ]]; then
  echo "Usage: $0 [--uninstall]" >&2
  exit 2
fi

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
config=${OPENCODE_CONFIG_DIR:-"$HOME/.config/opencode"}
action=${1:-install}

link_one() {
  local source=$1 destination=$2
  if [[ $action == --uninstall ]]; then
    if [[ -L $destination && $(readlink "$destination") == "$source" ]]; then
      rm -- "$destination"
      echo "removed $destination"
    fi
    return
  fi
  if [[ -L $destination && $(readlink "$destination") == "$source" ]]; then
    return
  fi
  if [[ -e $destination || -L $destination ]]; then
    echo "Refusing to replace $destination" >&2
    exit 1
  fi
  mkdir -p -- "$(dirname "$destination")"
  ln -s -- "$source" "$destination"
  echo "linked $destination"
}

for source in "$repo"/skills/*; do
  [[ -d $source ]] || continue
  link_one "$source" "$config/skills/$(basename "$source")"
done

for source in "$repo"/opencode/agents/*.md; do
  [[ -f $source ]] || continue
  link_one "$source" "$config/agents/$(basename "$source")"
done
