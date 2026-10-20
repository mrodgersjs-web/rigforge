# rigforge usage guide

Depth beyond the README front page: the CLI surface, configuration, agent integration over MCP, spec-bound proofs, the merge gate, the swarm verdict board, and the public-attestation composition path. Everything here runs offline unless a section says otherwise.

## CLI reference

```bash
rigforge init                    # scaffold a project
rigforge doctor                  # diagnose env, layout, contracts, CI, lint readiness
rigforge status                  # phase status        (--json for machine-readable)
rigforge run N [--dry-run]       # run phase N's deterministic gate bundle
rigforge seal N --artifact PATH [--spec FILE]      # seal a phase (optionally spec-bound)
rigforge verify [--strict] [--require-signature]   # re-check sealed phases
rigforge spec-check --proof P --spec S             # prove a build matched its spec
rigforge resume                  # resume the most recent failed/unfinished phase
rigforge benchmark               # the honesty benchmark (false-done-caught rate)
rigforge demo                    # live tamper-detection demo
rigforge verdicts                # swarm verdict board: per-agent accept/reject + trust%
rigforge trace N                 # run a phase with OpenTelemetry tracing
rigforge cockpit                 # serve the mission-control UI (127.0.0.1:8770)
rigforge mcp-serve               # expose tools to AI agents over MCP
rigforge contract list|create|validate|inspect
```

`--json` works everywhere it makes sense. `--cwd PATH` overrides project-root discovery.

## Configuration (`rigforge.yaml`)

`rigforge init` scaffolds a typed config (`rigforge.config.RigForgeConfig`):

| Section | Purpose |
|---------|---------|
| `budgets` | Cost / token / runtime ceilings, enforced by the harness |
| `mcp` | MCP transport (`http` or `stdio`), services, bearer-token auth |
| `scheduler` | Parallel gate scheduling, agent catalog |
| `signing` | HMAC-SHA256 ProofPacket signing + `require_on_verify` |
| `cockpit` | Cockpit UI host/port |

Env overrides: `RIGFORGE_SIGNING_KEY[_FILE]`, `RIGFORGE_MCP_TOKEN[_FILE]`, `RIGFORGE_MAX_PARALLEL_GATES`. `rigforge doctor` validates the file.

## Works with your stack

**Your agent.** rigforge exposes its contract and proof tools over MCP, so Claude Code, Codex, Cursor, and OpenCode can seal and verify proofs directly:

```bash
rigforge mcp-serve --transport stdio                   # preferred by Claude Code and similar
rigforge mcp-serve --auth-token "$RIGFORGE_MCP_TOKEN"  # HTTP, bearer-token auth
```

Claude Desktop stdio: install the package in the Python environment Claude Desktop uses, then register it:

```json
{
  "mcpServers": {
    "rigforge": {
      "command": "rigforge",
      "args": ["mcp-serve", "--transport", "stdio"],
      "cwd": "/path/to/rigforge"
    }
  }
}
```

Agents feed the swarm verdict board with one MCP call. The signing key stays server-side, so an agent cannot forge its own verdict:

```jsonc
// tools/call -> gev.seal_and_verify
{ "agent": "claude-code", "name": "auth refactor", "artifacts": ["src/auth.py"] }
// -> { "accepted": true, "integrity_ok": true, "signature_ok": true, ... }
```

**Your observability.** rigforge emits OpenTelemetry spans per phase and gate. Point it at an existing collector and traces drop into Langfuse, Phoenix or Jaeger. With no collector set, spans print as OTLP-JSON to stdout. Without the packages installed it is a clean no-op:

```bash
pip install -e ".[telemetry]"
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 rigforge trace 1
```

## The swarm verdict board

One agent you can eyeball; a fleet you cannot. Every seal and verify lands on a per-agent board, so you can see which agents to trust:

```bash
rigforge verdicts          # or open the cockpit at :8770 for the live grid
```

```
        RIGForge · swarm verdict board (by actor)
┃ actor        ┃ accepted ┃ rejected ┃ trust ┃
│ claude-code  │        5 │        1 │   83% │
│ cursor-agent │        3 │        0 │  100% │
│ rogue-bot    │        0 │        4 │    0% │   <- caught
```

## Spec-bound proofs: did the build match the spec?

Integrity proves the artifact is unchanged. Spec-bound proofs go further: they prove the build satisfied the acceptance criteria of the exact spec the agent was given. Bind a spec when you seal, a markdown checklist or a YAML `criteria:` list, and:

- the criteria are signed into the packet; a dropped or edited criterion breaks the signature;
- verification rejects unless every criterion has a passing gate, even if the artifact is intact;
- a swapped spec is caught by hash mismatch.

```bash
rigforge seal 1 --artifact build.out --spec spec.md
rigforge spec-check --proof proofs/phase1_proof.json --spec spec.md
#  spec-check: PASS   met: login works, tests pass, lint clean
```

Skip a requirement and the verdict flips:

```
spec-check: FAIL
   MISSING: lint clean
```

## Merge gate: block unsigned proofs before they land

Your CI workflow runs `rigforge verify --require-signature` as a required check. The agent seals work before opening the PR; the gate re-verifies the seal on push. An unsigned or tampered proof fails the check, and the PR stays open:

```yaml
# .github/workflows/ci.yml -- required check for PRs
- name: Verify proof
  run: rigforge verify --require-signature
```

The signing key stays in CI secrets, where the agent never sees it.

## Public attestation: compose with Sigstore, in-toto, SLSA

The HMAC signature is symmetric: the same key seals and verifies. It proves integrity to you, but a third party cannot check it without the key (which would also let them forge). For public verifiability, compose with asymmetric attestation:

| Layer | What it does | rigforge role |
|-------|-------------|---------------|
| [Sigstore](https://www.sigstore.dev/) (`cosign`) | Keyless signing with short-lived certificates and a public transparency log | rigforge decides what is true about the run; Sigstore makes that decision publicly checkable |
| [in-toto](https://in-toto.io/) | Signed attestations about supply-chain steps | the ProofPacket is the attestation content; in-toto wraps it in a signed supply-chain layout |
| [SLSA](https://slsa.dev/) | Provenance framework built on in-toto | rigforge seals the provenance; SLSA carries it through the build pipeline |

rigforge does not do asymmetric signing or public attestation natively. See [`SECURITY.md`](../SECURITY.md) for the full HMAC limitation and the compose path.

## Video walkthrough

- Script: [`video-script.md`](video-script.md)
- Recording: [`../assets/demo.mp4`](../assets/demo.mp4) (75s captioned)
- Preview: [`../assets/demo.gif`](../assets/demo.gif)
