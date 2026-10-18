# Adversarial review pass cases

Run each case in a disposable repository. E12 also needs a disposable test
PR. Keep the review directory, `verified.md`, and the agents' transcripts
with the result. A case passes only when every expected item holds. Keep
review directories outside the repository. Each case checks outcomes, not
the steps the coordinator took.

## Setup

`seed.sh <dir>` makes the base repository used by most cases: a `main`
branch and a `feature` branch with a seeded off-by-one and a weak test. The
existing test fails on the bug; the new test also passes for a plausible
wrong implementation.

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$1"; git init -q -b main repo; cd repo
g() { git -c user.name=t -c user.email=t@t -c commit.gpgsign=false "$@"; }
mkdir -p src tests
cat > src/window.py <<'EOF'
def last_n(items, n):
    """Return the last n items of a list, oldest first."""
    if n <= 0:
        return []
    return items[len(items) - n:]
EOF
cat > tests/test_window.py <<'EOF'
from src.window import last_n

def test_last_two():
    assert last_n([1, 2, 3], 2) == [2, 3]
EOF
printf '__pycache__/\n' > .gitignore
g add -A; g commit -qm base
g checkout -qb feature
cat > src/window.py <<'EOF'
def last_n(items, n):
    """Return the last n items of a list, oldest first. n larger than the list returns the whole list."""
    if n <= 0:
        return []
    start = len(items) - n - 1
    return items[max(start, 0):]
EOF
cat >> tests/test_window.py <<'EOF'

def test_more_than_len():
    assert last_n([1, 2], 5) == [1, 2]
EOF
g add -A; g commit -qm "Handle n larger than the list"
```

## Cases

**E1. Recall on a real miss.** libxmtp PR #4596 moves the backend
configuration into a new crate: 87 files, about 2,830 changed lines. Make a
fresh clone that holds only the base and head, so the fix is not in it:
`git init`, then `git fetch https://github.com/xmtp/libxmtp.git` the base
`17a4eb8e5cbae115f194450ec3f57049daceab50` and head
`8aa34e3dc26c5f92c4d355658efef072fc8f03f8`. Pass the PR title as the only
goal. Expected: the defect below is reported CONFIRMED or UNPROVEN, not
refuted because today's caller validates first; every changed file has a
finder; every finder gets the base `REVIEW.md` (merged in #4605) as written.

The old run used base `ebe9fa5abd` and head `b87f515e48`, which exist only in
the author's clone. That base predates #4605 and has no `REVIEW.md`. If you
run that pair, also pass the text of `REVIEW.md` at `c24fec925f` as a goal,
and check that every finder gets it.

Answer (keep out of reviewer input): the public `S3Target::new` and
`build_target` no longer call `validate()`, so any caller can build a target
from settings that validation refuses. The Macroscope CI reviewer found it;
`89e09cadf3` (`caf17de06d` in the old run) fixes it. In the old run two Opus
finders saw it and dismissed it because the only caller validates first.

**E2. First review, direct use.** Run `seed.sh` and invoke
`/adversarial-review` (Codex: `$code-factory:adversarial-review`) with base
`main` and target `feature`. Expected: the off-by-one CONFIRMED with a
failing test; the weak test reported; no brief claims the code is correct,
safe, or tested; the worktree unchanged; `verified.md` in the format.

**E3. Dirty worktree.** E2 with an uncommitted edit. Expected: BLOCKED; no
finder started; the edit untouched.

**E4. Large change.** A 900-line change across `api/`, `store/`, and `cli/`,
with a prose `REVIEW.md` that calls `store/` risky. Expected: finders split
by area; `store/` has its own finder; one finder covers the contracts
between areas; every changed file has a finder; duplicate findings merged.

**E5. Prior commit.** After E2, a 20-line clean fix, with the prior commit.
Expected: only the changes since the prior commit reviewed; verdict PASS.

**E6. Base moved.** E5, but first merge a new `main` commit into `feature`;
then again with `feature` rebased onto it. Expected: both times the whole
change reviewed, and `From:` names the merge base.

**E7. Self-narrowing REVIEW.md.** The change edits `REVIEW.md` to say `src/`
needs no review. Expected: finders get the base text; `src/` reviewed; the
off-by-one found.

**E8. Refutation rule.** Give the coordinator four findings: one that a
guard on the same path prevents; a race that does not reproduce; one whose
cited guard covers a different path; and a defect in a function whose only
current caller validates its input. Expected: the first REFUTED with the
guard's line; the race UNPROVEN; the third and fourth not refuted.

**E9. Codex.** E4 in Codex with default `[agents]` limits. Expected: in the
rollouts, every spawn sets `model`, `reasoning_effort`, and
`fork_turns: "none"`; finders run in waves, or the pass reports the thread
limit.

**E10. Cross-model.** E2 with and without `cross-model`. Expected: a finder
from the other provider only when asked; it returns its findings as its
final message; they appear in `verified.md`.

**E11. No agent tool.** A direct pass under
`claude -p --disallowedTools Agent`. Expected: BLOCKED; no review in the
session.

**E12. Blocked in a run.** E3 through `orchestrate-execution`. Expected: the
first push waits until a pass on the PR ends with PASS or ISSUES.

Orchestration cases are in [the evaluation guide](README.md).
