# RIGForge Hooks

Drop-in integrations that wire RIGForge's proof layer into your agent's
lifecycle. Every file here is self-contained and runnable — copy it, adjust the
config variables at the top, and hook it into the right moment.

| Hook | What it does | When to run |
|------|-------------|-------------|
| [`seal-or-fail.sh`](seal-or-fail.sh) | Runs `rigforge verify --strict --require-signature`; seals the current phase only when all gates pass. Exits non-zero on any failure — CI-safe, pre-commit safe, or gating a deploy. | CI pipeline, pre-commit, deploy gate, or shell wrapper around `rigforge run` |
| [`claude-code-stop-hook.sh`](claude-code-stop-hook.sh) | A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) **Stop hook** that automatically seals a ProofPacket when the agent finishes its session — so the agent's "done" claim is always followed by a cryptographic proof, not just a message. | `.claude/settings.json` → `hooks.Stop` |
| [`cursor-rigforge-rule.md`](cursor-rigforge-rule.md) | A [Cursor](https://cursor.sh/) `.cursor/rules/rigforge.md` rule that instructs the agent to verify proof integrity before claiming "done" and to seal on completion. | `.cursor/rules/rigforge.md` |

## Prerequisites

All hooks require the RIGForge CLI to be installed and a project to be
initialized:

```bash
pip install -e .                       # from the repo root
rigforge init                          # creates proofs/, contracts/, ledger/, rigforge.yaml
rigforge doctor                        # confirm env + layout are healthy
```

## Quick wiring

### CI (GitHub Actions)

```yaml
# .github/workflows/ci.yml — add a gate step after tests
- name: RIGForge verify
  run: bash examples/hooks/seal-or-fail.sh
```

### Claude Code

Add to `.claude/settings.json`:

```jsonc
{
  "hooks": {
    "Stop": ["bash", "examples/hooks/claude-code-stop-hook.sh"]
  }
}
```

### Cursor

Copy the rule into your project:

```bash
cp examples/hooks/cursor-rigforge-rule.md .cursor/rules/rigforge.md
```

## How the proof layer works

```
agent claims "done"
        │
        ▼
seal-or-fail.sh  ───  rigforge verify --strict --require-signature
        │                        │
        │                   FAIL ──── exit 1 (deploy blocked, commit rejected)
        │                        │
        ▼                   PASS
 rigforge seal N             ──────  ProofPacket written to proofs/phase{N}_proof.json
        │
        ▼
  artifact  ──SHA-256──▶  integrity hash  ──HMAC-SHA256──▶  signature
                                                                  │
                                                     rigforge verify re-checks both
```

A **ProofPacket** hashes every artifact with SHA-256 and signs the result with
HMAC-SHA256. Tamper the artifact and re-forge the hash — the signature still
fails. "The build passed" becomes something you re-verify with one command, not
a message in a thread.

## Configuration

The scripts read from `rigforge.yaml` and environment variables:

| Variable | Purpose |
|----------|---------|
| `RIGFORGE_SIGNING_KEY` | HMAC signing key (preferred: `RIGFORGE_SIGNING_KEY_FILE` pointing to a file) |
| `RIGFORGE_MCP_TOKEN` | Bearer token for HTTP MCP transport |
| `RIGFORGE_PHASE` | Override which phase to seal (default: auto-detect next unsealed) |
| `RIGFORGE_SIGNING_KEY_FILE` | Path to the signing key file |

## Security

- **Never hardcode signing keys** in hooks, CI files, or version control.
  Use `RIGFORGE_SIGNING_KEY_FILE` or `rigforge.yaml` with a gitignored key.
- The signing key is stored at `.rigforge/signing.key` by default and is
  automatically added to `.gitignore` by `rigforge init`.
- Hooks are **gate-first**: they verify integrity AND signature before sealing.
  A forged "done" always gets caught.

See [`docs/THREAT_MODEL.md`](../../docs/THREAT_MODEL.md) for the full trust
model and what RIGForge deliberately does not defend against.
