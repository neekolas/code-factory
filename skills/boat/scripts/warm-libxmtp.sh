#!/usr/bin/env bash
# Run as the regular user on a fully restored, credential-free libxmtp builder.
set -euo pipefail
[[ $(id -u) != 0 ]] || { echo 'Run as the regular build user, not root.' >&2; exit 1; }
repo=${1:-$HOME/libxmtp}
repo=$(cd -- "$repo" && pwd -P)
cd "$repo"
[[ -z $(git status --porcelain) ]] || { echo 'Builder checkout must be clean.' >&2; exit 1; }
[[ $(git branch --show-current) == main ]] || { echo 'Builder must be on main.' >&2; exit 1; }
git fetch origin main
git merge --ff-only origin/main
[[ $(git rev-parse HEAD) == "$(git rev-parse origin/main)" ]] || {
  echo 'Builder has local commits; do not publish them as a main snapshot.' >&2; exit 1;
}
cache_root=$HOME/.local/share/code-factory/libxmtp
export KACHE_CACHE_DIR=$cache_root/kache
export CARGO_TARGET_DIR=$repo/target
mkdir -p "$KACHE_CACHE_DIR"
# Persist the location for native agents too, even when their shell is not a login shell.
python3 - "$KACHE_CACHE_DIR" <<'PY'
from pathlib import Path
import json,re,sys
p=Path.home()/'.config/kache/config.toml'
p.parent.mkdir(parents=True,exist_ok=True)
s=p.read_text() if p.exists() else ''
line='local_store = '+json.dumps(sys.argv[1])+'\n'
m=re.search(r'(?m)^\[cache\]\s*$',s)
if m:
    end=re.search(r'(?m)^\[',s[m.end():])
    stop=m.end()+end.start() if end else len(s)
    section=s[m.end():stop]
    section=re.sub(r'(?m)^local_store\s*=.*\n?',line,section) if re.search(r'(?m)^local_store\s*=',section) else '\n'+line+section
    s=s[:m.end()]+section+s[stop:]
else:
    s=s.rstrip()+'\n\n[cache]\n'+line
p.write_text(s)
PY
dev/nix-shell 'kache daemon restart'
started=$(date +%s)
{
  dev/nix-shell 'just check'
  dev/nix-shell 'just test workspace --no-run'
  dev/nix-shell 'just test crate xmtp_common'
  dev/nix-shell 'kache stats --full'
} 2>&1 | tee "$cache_root/warm.log"
python3 - "$cache_root" "$(git rev-parse HEAD)" "$started" "$CARGO_TARGET_DIR" <<'PY'
from pathlib import Path
import json,sys,time
root,revision,started,target=sys.argv[1:]
data={'repository':'https://github.com/xmtp/libxmtp','revision':revision,
      'commands':['just check','just test workspace --no-run','just test crate xmtp_common'],
      'started_at_unix':int(started),'finished_at_unix':int(time.time()),
      'cargo_target_dir':target,'kache_dir':str(Path(root)/'kache'),'status':'passed'}
(Path(root)/'warm.json').write_text(json.dumps(data,indent=2)+'\n')
PY
