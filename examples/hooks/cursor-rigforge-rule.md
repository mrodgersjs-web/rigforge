# RIGForge Integration Rule

This rule ensures AI coding agents working in Cursor produce verifiable,
proof-backed work instead of unverifiable "done" claims.

Copy to: `.cursor/rules/rigforge.md`

---

## Core Law

**No gate, no seal. No ProofPacket, it did not happen.**

Every time you finish a meaningful task — a feature, a fix, a refactor — you
MUST produce a RIGForge ProofPacket before claiming "done." The proof seals
your work with a SHA-256 integrity hash and an HMAC-SHA256 signature so
anyone can re-verify your claim with one command. A "✅ done" in chat is
not evidence. A ProofPacket is.

## Before You Claim "Done"

Run these checks and report the output. If any check fails, fix the failure
before proceeding.

```bash
# 1. Run the current phase's deterministic gate bundle
rigforge run $PHASE

# 2. Verify all sealed phases — integrity + signature
rigforge verify --strict --require-signature

# 3. If both pass, seal the phase
rigforge seal $PHASE \
  --artifact <your-output-file> \
  --evidence "completed <task description>" \
  --verifier "cursor-agent"

# 4. Post-seal: re-verify the proof you just wrote
rigforge verify --strict --require-signature
```

Replace `$PHASE` with the appropriate phase number (1-7). If you don't know
which phase, run `rigforge status` to see what's sealed and what's pending.

## Rules

### 1. Seal every completed phase

After completing any non-trivial task, seal the phase:

```bash
rigforge seal $PHASE --artifact <path> --evidence "<what you did>"
```

Do NOT claim "BUILD COMPLETE" or "all tests pass" without a corresponding
sealed ProofPacket. The seal is the evidence, not your words.

### 2. Verify before sealing

Always run gates before sealing. A seal without passing gates records
failures in the ProofPacket — that's better than silence, but a green seal
is what you want:

```bash
rigforge run $PHASE          # run gates first
rigforge seal $PHASE ...     # then seal
```

### 3. Verify after sealing

Post-seal verification catches write errors and tamper. Always run it:

```bash
rigforge verify --strict --require-signature
```

### 4. Never forge a seal

Do NOT:
- Edit `proofs/phase*_proof.json` by hand
- Re-seal a phase with a different artifact without running gates
- Claim a phase is sealed when `rigforge verify` says it isn't
- Use `--force` to skip gate failures (the ProofPacket records the skip)

### 5. Use spec-bound proofs when available

If the task has a spec (a markdown checklist or YAML `criteria:` list),
bind it to the proof:

```bash
rigforge seal $PHASE --artifact <path> --spec <spec-file>
rigforge spec-check --proof proofs/phase${PHASE}_proof.json --spec <spec-file>
```

This proves your build matched the acceptance criteria — not just that the
artifact is intact.

### 6. Report gate failures honestly

If `rigforge run $PHASE` fails, report the failure:

```
Phase 5 gates FAILED:
  ❌ pytest: 3 test(s) failed
  ❌ contract_schema: contracts/v1/bad.yaml — missing 'verifier_package'
  ✅ repo_layout: OK
```

Do NOT mask failures or rerun silently until green. The ledger records
every run.

## Integration Checklist

When starting a session on a RIGForge project:

- [ ] Confirm `rigforge.yaml` exists (`rigforge doctor`)
- [ ] Confirm signing key exists (`.rigforge/signing.key`)
- [ ] Run `rigforge status` to see current phase state
- [ ] Identify which phase you're working on

When finishing a session:

- [ ] Run `rigforge run $PHASE` (gates pass)
- [ ] Run `rigforge seal $PHASE --artifact ... --evidence ...`
- [ ] Run `rigforge verify --strict --require-signature` (proof verifies)
- [ ] Report the seal result in your summary

## What the ProofPacket Contains

When you seal, the ProofPacket records:

- **Phase number** and name
- **Artifacts**: SHA-256 hash + size of every file you touched
- **Gates**: pass/fail + severity + detail for every quality check
- **RunEnvelope**: your identity, command, environment fingerprint, timestamp
- **Signature**: HMAC-SHA256 over the integrity hash (requires signing key)
- **Evidence**: your human-readable summary of what was done

Anyone can re-verify your work with:

```bash
rigforge verify --strict --require-signature
```

If the signature is valid, your "done" is proven. If it fails, the lie is
caught. That's the whole point.

## Quick Reference

| Command | Purpose |
|---------|---------|
| `rigforge status` | See what's sealed, what's pending |
| `rigforge run N` | Run phase N's gate bundle |
| `rigforge seal N --artifact F --evidence "..."` | Seal phase N with an artifact |
| `rigforge seal N --spec spec.md` | Seal with spec-bound proof |
| `rigforge verify --strict --require-signature` | Verify all sealed proofs |
| `rigforge spec-check --proof P --spec S` | Check spec-bound proof |
| `rigforge benchmark` | Run the honesty benchmark |
| `rigforge doctor` | Diagnose project health |

## Further Reading

- [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) — full platform design
- [`docs/THREAT_MODEL.md`](../../docs/THREAT_MODEL.md) — trust boundaries
- [`docs/EXTENDING.md`](../../docs/EXTENDING.md) — adding custom gates
- [`examples/verify_agent_done.py`](../verify_agent_done.py) — minimal integration
