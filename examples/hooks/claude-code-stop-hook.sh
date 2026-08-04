#!/usr/bin/env bash
# ─── RIGForge  ·  claude-code-stop-hook.sh ──────────────────────────────
#
# A Claude Code Stop hook that automatically seals a ProofPacket when the
# agent finishes its session.  This guarantees that every "done" claim is
# backed by a cryptographically signed proof — not just a chat message.
#
# Wire it into .claude/settings.json:
#
#   {
#     "hooks": {
#       "Stop": ["bash", "examples/hooks/claude-code-stop-hook.sh"]
#     }
#   }
#
# Claude Code passes the following environment variables to hooks:
#   CLAUDE_PROJECT_DIR   — project root (where .claude/ lives)
#   CLAUDE_SESSION_ID    — unique session identifier
#   CLAUDE_EXIT_CODE     — 0 if the agent exited normally
#
# Exit codes:
#   0  — proof sealed successfully (or nothing to seal)
#   1  — seal failed (gates failed or crypto error)
#   2  — environment error
#
# This hook NEVER blocks the agent from exiting.  A failed seal is logged
# but the agent is not held hostage — RIGForge's model is "prove it, don't
# trap it."  A missing proof is its own audit signal.
# ──────────────────────────────────────────────────────────────────────────

set -uo pipefail

# ── Config ──────────────────────────────────────────────────────────────

# Override which phase to seal.  When empty, the hook seals the next
# unsealed phase (auto-detect).  Set RIGFORGE_STOP_PHASE in your env to
# pin a specific phase.
STOP_PHASE="${RIGFORGE_STOP_PHASE:-}"

# Require HMAC signature verification on the post-seal check.
# Set to "0" if you haven't configured signing yet.
REQUIRE_SIG="${RIGFORGE_REQUIRE_SIGNATURE:-1}"

# Maximum seconds to wait for rigforge commands before giving up.
TIMEOUT="${RIGFORGE_STOP_TIMEOUT:-60}"

# ── Helpers ─────────────────────────────────────────────────────────────

log() { echo "[rigforge stop hook] $*"; }
warn() { echo "[rigforge stop hook] ⚠ $*" >&2; }

# ── Resolve project directory ──────────────────────────────────────────

# Claude Code provides CLAUDE_PROJECT_DIR.  Fall back to working directory.
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

if [[ ! -d "$PROJECT_DIR" ]]; then
    warn "project directory not found: $PROJECT_DIR"
    exit 2
fi

cd "$PROJECT_DIR" || { warn "cannot cd to $PROJECT_DIR"; exit 2; }

# ── Pre-flight ──────────────────────────────────────────────────────────

if ! command -v rigforge &>/dev/null; then
    warn "rigforge not installed — skipping seal"
    exit 0
fi

if [[ ! -f "rigforge.yaml" ]] && [[ ! -f "pyproject.toml" ]]; then
    warn "not a RIGForge project — skipping seal"
    exit 0
fi

SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
EXIT_CODE="${CLAUDE_EXIT_CODE:-unknown}"

log "session=$SESSION_ID exit=$EXIT_CODE"

# ── Verify existing proofs first ───────────────────────────────────────

log "verifying existing sealed phases..."

VERIFY_ARGS=("--strict")
if [[ "$REQUIRE_SIG" == "1" ]]; then
    VERIFY_ARGS+=("--require-signature")
fi

# Best-effort: if verification fails, warn but don't block the seal attempt.
# The seal will record its own gate outcomes regardless.
timeout "$TIMEOUT" rigforge verify "${VERIFY_ARGS[@]}" 2>&1 || {
    warn "existing proofs failed verification — sealing anyway (gates record outcome)"
}

# ── Determine phase ────────────────────────────────────────────────────

if [[ -n "$STOP_PHASE" ]]; then
    PHASE="$STOP_PHASE"
    if ! [[ "$PHASE" =~ ^[1-7]$ ]]; then
        warn "invalid phase: $PHASE — skipping seal"
        exit 0
    fi
else
    # Auto-detect: find the first unsealed phase.
    PHASE=$(rigforge status --json 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    phases = data.get('phases', data.get('status', {}))
    if isinstance(phases, dict):
        for p in sorted(phases.keys(), key=int):
            info = phases[p]
            sealed = info.get('sealed', False) if isinstance(info, dict) else False
            if not sealed:
                print(p)
                sys.exit(0)
except Exception:
    pass
print('')
" 2>/dev/null) || PHASE=""

    if [[ -z "$PHASE" ]]; then
        log "all phases already sealed — nothing to do"
        exit 0
    fi
fi

log "target phase: $PHASE"

# ── Run gates ──────────────────────────────────────────────────────────

log "running phase $PHASE gate bundle..."

if ! timeout "$TIMEOUT" rigforge run "$PHASE" 2>&1; then
    warn "phase $PHASE gates failed — seal will record failures"
    # We still seal: a failed seal with gate evidence is more useful than
    # silence.  The ProofPacket records every gate outcome, so the verifier
    # can see exactly what failed.
fi

# ── Seal ────────────────────────────────────────────────────────────────

VERIFIER="claude-code/stop-hook"
if [[ "$EXIT_CODE" == "0" ]]; then
    EVIDENCE="agent session $SESSION_ID completed normally"
else
    EVIDENCE="agent session $SESSION_ID exited with code $EXIT_CODE"
fi

SEAL_ARGS=(
    "$PHASE"
    "--evidence" "$EVIDENCE"
    "--verifier" "$VERIFIER"
)

log "sealing phase $PHASE..."

if timeout "$TIMEOUT" rigforge seal "${SEAL_ARGS[@]}" 2>&1; then
    log "sealed ✓ → proofs/phase${PHASE}_proof.json"
else
    warn "seal failed — phase $PHASE proof not written"
    # Don't exit non-zero: the agent is stopping, and blocking it here
    # achieves nothing.  The missing proof is the audit signal.
    exit 0
fi

# ── Post-seal verify ───────────────────────────────────────────────────

log "post-seal verification..."

if timeout "$TIMEOUT" rigforge verify "${VERIFY_ARGS[@]}" 2>&1; then
    log "verified ✓"
else
    warn "post-seal verification failed — check proofs/phase${PHASE}_proof.json"
fi

log "done"
exit 0
