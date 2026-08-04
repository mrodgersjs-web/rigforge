#!/usr/bin/env bash
# ─── RIGForge  ·  seal-or-fail.sh ───────────────────────────────────────
#
# Run `rigforge verify --strict --require-signature` against all sealed
# phases, then seal the current phase ONLY when every gate passes.  Exit
# non-zero on any failure — safe for CI, pre-commit, or deploy gates.
#
# Usage:
#   bash examples/hooks/seal-or-fail.sh           # auto-detect next phase
#   RIGFORGE_PHASE=3 bash examples/hooks/seal-or-fail.sh  # explicit phase
#
# Exit codes:
#   0  — all sealed phases verified, current phase sealed successfully
#   1  — verification failed (tamper, missing signature, gate failure)
#   2  — environment error (rigforge not installed, no project, bad phase)
# ──────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────

PHASE="${RIGFORGE_PHASE:-}"
SIGNING_KEY="${RIGFORGE_SIGNING_KEY:-}"
SIGNING_KEY_FILE="${RIGFORGE_SIGNING_KEY_FILE:-}"
REQUIRE_SIGNATURE="${RIGFORGE_REQUIRE_SIGNATURE:-1}"  # 1 = on (default)

# ── Helpers ─────────────────────────────────────────────────────────────

die() { echo "❌ seal-or-fail: $*" >&2; exit 2; }
info() { echo "▸ $*"; }

# Resolve the signing key from env or file.  If neither is set, rigforge
# falls back to `.rigforge/signing.key` (ensure_signing_key).  We only
# block if the user explicitly asked for signatures and no key is available.
resolve_signing_key() {
    if [[ -n "$SIGNING_KEY" ]]; then
        echo "$SIGNING_KEY"
    elif [[ -n "$SIGNING_KEY_FILE" ]]; then
        if [[ ! -f "$SIGNING_KEY_FILE" ]]; then
            die "signing key file not found: $SIGNING_KEY_FILE"
        fi
        cat "$SIGNING_KEY_FILE"
    else
        # Let rigforge handle the default path
        local key_path=".rigforge/signing.key"
        if [[ -f "$key_path" ]]; then
            cat "$key_path"
        else
            echo ""
        fi
    fi
}

# Detect the next unsealed phase from `rigforge status --json`.
detect_next_phase() {
    local status_json
    status_json=$(rigforge status --json 2>/dev/null) || {
        die "rigforge status failed — is the project initialized? (rigforge init)"
    }

    # Find the first phase that is not sealed.
    local next
    next=$(echo "$status_json" | python3 -c "
import json, sys
data = json.load(sys.stdin)
phases = data.get('phases', data.get('status', {}))
if isinstance(phases, dict):
    for p in sorted(phases.keys(), key=int):
        info = phases[p]
        sealed = info.get('sealed', False) if isinstance(info, dict) else False
        if not sealed:
            print(p)
            sys.exit(0)
    print('')  # all sealed
else:
    print('')
" 2>/dev/null) || next=""

    echo "$next"
}

# ── Pre-flight checks ──────────────────────────────────────────────────

info "checking environment..."

if ! command -v rigforge &>/dev/null; then
    die "rigforge CLI not found — install with: pip install -e ."
fi

if ! command -v python3 &>/dev/null; then
    die "python3 required but not found"
fi

if [[ ! -f "rigforge.yaml" ]] && [[ ! -f "pyproject.toml" ]]; then
    die "no rigforge.yaml or pyproject.toml found — run 'rigforge init' first"
fi

# ── Step 1: Verify all sealed phases ───────────────────────────────────

info "verifying sealed phases (--strict --require-signature)..."

VERIFY_ARGS=("--strict")
if [[ "$REQUIRE_SIGNATURE" == "1" ]]; then
    VERIFY_ARGS+=("--require-signature")
fi

if ! rigforge verify "${VERIFY_ARGS[@]}" 2>&1; then
    echo ""
    echo "🚨 SEAL BLOCKED — existing sealed phases failed verification."
    echo "   Fix the tampered or unsigned proofs before sealing new work."
    exit 1
fi

info "all sealed phases verified ✓"

# ── Step 2: Determine which phase to seal ──────────────────────────────

if [[ -n "$PHASE" ]]; then
    if ! [[ "$PHASE" =~ ^[1-7]$ ]]; then
        die "invalid phase: $PHASE (must be 1-7)"
    fi
    info "sealing phase $PHASE (from RIGFORGE_PHASE)"
else
    PHASE=$(detect_next_phase)
    if [[ -z "$PHASE" ]]; then
        info "all phases sealed — nothing to do"
        exit 0
    fi
    info "auto-detected next unsealed phase: $PHASE"
fi

# ── Step 3: Run the phase gates ────────────────────────────────────────

info "running phase $PHASE gate bundle..."

if ! rigforge run "$PHASE" 2>&1; then
    echo ""
    echo "🚨 SEAL BLOCKED — phase $PHASE gates failed."
    echo "   Fix the gate failures, then re-run this hook."
    exit 1
fi

info "phase $PHASE gates passed ✓"

# ── Step 4: Seal the phase ─────────────────────────────────────────────

SEAL_ARGS=("$PHASE")
SEAL_ARGS+=("--evidence" "sealed by seal-or-fail hook at $(date -u +%Y-%m-%dT%H:%M:%SZ)")
SEAL_ARGS+=("--verifier" "seal-or-fail.sh/$(whoami)")

info "sealing phase $PHASE..."

if ! rigforge seal "${SEAL_ARGS[@]}" 2>&1; then
    echo ""
    echo "🚨 SEAL FAILED — rigforge seal returned non-zero."
    exit 1
fi

# ── Step 5: Post-seal verification ─────────────────────────────────────

info "post-seal verification..."

if ! rigforge verify "${VERIFY_ARGS[@]}" 2>&1; then
    echo ""
    echo "🚨 POST-SEAL VERIFICATION FAILED — the seal was written but did not verify."
    echo "   This should never happen. Check proofs/phase${PHASE}_proof.json manually."
    exit 1
fi

echo ""
echo "✅ phase $PHASE sealed and verified"
echo "   proof: proofs/phase${PHASE}_proof.json"
exit 0
