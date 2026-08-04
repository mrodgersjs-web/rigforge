# Merge Gate

A **merge gate** is a CI enforcement layer that blocks a pull request from
merging until RIGForge's deterministic quality gates pass for the phases you
care about.  It replaces the vague "CI is green" with a cryptographically
grounded assertion: *these specific checks ran, on this code, and every
hard-block gate passed.*

RIGForge provides a composite GitHub Action that runs inside any workflow,
seals tamper-evident ProofPackets, and produces machine-readable outputs you
can gate on.

---

## Quick start

### 1. Add the composite action

The composite action lives in the repo:

```
.github/actions/rigforge-gate/action.yml
```

No installation step — it's already part of the source tree.

### 2. Copy the example workflow

```bash
cp examples/github-actions/rigforge-gate.yml .github/workflows/rigforge-gate.yml
```

This installs RIGForge, runs all 7 phase gates in a matrix, and aggregates
them into a single `gate-verdict` required status check.

### 3. Add a required status check

In your repo's **Settings → Branch protection rules → main**:

1. Enable **Require status checks to pass before merging**
2. Add `gate-verdict` as a required check
3. Optionally require the individual phase checks (`rigforge gate (phase N)`)
   if you want per-phase visibility

### 4. Push a PR

Every PR to `main` now runs the gate.  Merge is blocked until all phases
pass.

---

## How it works

### Gate execution

The composite action runs these steps:

1. **Set up Python** — uses `actions/setup-python` with the requested version
2. **Install RIGForge** — `pip install -e ".[dev]"` (configurable via
   `install-extras`)
3. **Run gates** — executes `rigforge run <phase> --json` which runs the
   deterministic gate bundle for that phase
4. **Optional seal** — if `seal: true`, writes a ProofPacket to
   `proofs/phase{N}_proof.json` and appends to `ledger/execution.jsonl`
5. **Optional strict verify** — if `strict: true`, runs
   `rigforge verify --strict` to enforce phase-order continuity

### Gate bundles per phase

Each phase maps to a fixed set of gates (see `rigforge/gates.py`):

| Phase | Gates | What it validates |
| --- | --- | --- |
| 1 | `python_version`, `repo_layout` | Python >=3.11, canonical directory structure |
| 2 | `python_version`, `repo_layout`, `ci_workflow` | Phase 1 + CI workflow present |
| 3 | `repo_layout`, `contracts_present` | Canonical layout + contracts directory |
| 4 | `contracts_present`, `contract_schema` | Contracts exist and validate against schema |
| 5 | `contract_schema`, `pytest` | Contracts valid + test suite green |
| 6 | `contracts_present`, `pytest` | Contracts present + tests green |
| 7 | `pytest`, `ci_workflow` | Tests green + CI workflow present |

### Severity levels

Every gate has a severity that determines whether a failure blocks the merge:

| Severity | Blocks merge? | Behavior |
| --- | --- | --- |
| `hard_block` | **Yes** | Phase cannot be sealed without `--force` |
| `soft_block` | No | Recorded in the ProofPacket, never blocks `ok` |
| `advisory` | No | Informational only (e.g., `ruff` lint) |

A merge gate **only fails the PR** when a `hard_block` gate returns
`passed: false`.  Soft-block and advisory failures appear in the step summary
for visibility but do not block the merge.

### Action outputs

The composite action emits structured outputs for downstream use:

| Output | Type | Description |
| --- | --- | --- |
| `ok` | `string` | `"true"` if all hard-block gates passed |
| `phase` | `string` | Phase number that was evaluated |
| `gate-count` | `string` | Total gates executed |
| `passed-count` | `string` | Gates that passed |
| `failed-count` | `string` | Gates that failed (any severity) |
| `blocking-failed-count` | `string` | Hard-block gates that failed |
| `sealed` | `string` | Whether a ProofPacket was sealed |
| `proof-path` | `string` | Path to the sealed packet |
| `gate-summary` | `string` | Markdown table of all gate results |

Use these in conditional steps:

```yaml
- name: Custom action on failure
  if: steps.gate.outputs.ok == 'false'
  run: echo "Phase ${{ steps.gate.outputs.phase }} has blocking failures"
```

---

## Configuration

### Inputs reference

All inputs are optional except `phase`:

| Input | Default | Description |
| --- | --- | --- |
| `phase` | *(required)* | Phase number (1–7) |
| `seal` | `true` | Write a ProofPacket after gates pass |
| `force` | `false` | Seal even if hard-block gates failed |
| `strict` | `false` | Run strict phase-order verify after sealing |
| `spec` | `""` | Path to a spec file to bind into the packet |
| `evidence` | `""` | Human-readable evidence summary for the packet |
| `python-version` | `3.13` | Python version to set up |
| `install-extras` | `[dev]` | pip extras to install |
| `working-directory` | `""` | Override project root (default: auto-discover) |

### Selective phase gating

You don't have to gate on all 7 phases.  For a new project, gate on the
structural phases only:

```yaml
matrix:
  phase: [1, 2, 3]
```

As your project matures, add phases 4–7 (contract validation, tests, CI).

### Spec-bound gating

If your project uses acceptance specs (`rigforge spec-check`), bind a spec
file into the sealed packet:

```yaml
- name: Gate with spec
  uses: ./.github/actions/rigforge-gate
  with:
    phase: 5
    spec: specs/phase5-acceptance.yml
    seal: true
```

The sealed packet carries a signed hash of the spec.  Later, anyone can verify
the work satisfied the *exact* spec:

```bash
rigforge spec-check --proof proofs/phase5_proof.json --spec specs/phase5-acceptance.yml
```

### Force-sealing

Use `force: true` to seal a ProofPacket even when hard-block gates failed.
The failures are recorded *in* the packet — the seal is honest about what
passed and what didn't.  This is useful for:

- Capturing evidence of a known failure state
- Running the gate in advisory mode during development
- Sealing a "not done yet" packet for audit purposes

```yaml
- name: Capture evidence
  uses: ./.github/actions/rigforge-gate
  with:
    phase: 5
    seal: true
    force: true
    evidence: "Intentional force-seal to capture failure state"
```

---

## Architecture

### Why composite action, not reusable workflow?

GitHub Actions has two reuse mechanisms:

| Mechanism | Runs in | Can be conditional? | Shares runner? |
| --- | --- | --- | --- |
| Reusable workflow (`workflow_call`) | Its own job | No — always spins up | No |
| Composite action | Caller's job | Yes — step-level `if` | Yes |

A composite action runs **inside the caller's job**, sharing the runner
environment.  This means:

- **One pip install** for all phases (not N jobs each installing)
- **Step-level conditionals** — you can skip phases based on file changes
- **Same runner context** — artifacts, caches, and env are shared

The composite action pattern also means you can use it from *any* workflow,
not just the example — deploy pipelines, nightly builds, release gates, or
ad-hoc verification runs.

### ProofPacket on merge

The recommended pattern is:

1. **PRs:** Run gates with `seal: false` — validate without writing proofs
2. **Merge to main:** Run gates with `seal: true` and `strict: true` —
   validate, seal, and verify phase continuity
3. **On seal success:** Commit the proof and ledger back to main

This keeps the proofs directory clean — only merged work generates sealed
packets.  See the commented-out `seal-on-merge` workflow in
`examples/github-actions/rigforge-gate.yml` for the full pattern.

### Gate result flow

```
PR opened
    │
    ▼
┌─────────────────────────────┐
│  rigforge-gate matrix job   │
│  phase 1 .. 7               │
│                             │
│  for each phase:            │
│    install rigforge         │
│    rigforge run <phase>     │
│    (optional) rigforge seal │
│    output: ok, gates, ...   │
│                             │
│  each step:                 │
│    pass → ✅                │
│    fail → ❌ (exits non-0) │
└─────────┬───────────────────┘
          │
          ▼
┌─────────────────────────────┐
│  gate-verdict aggregation   │
│  needs: [rigforge-gate]     │
│                             │
│  if any phase failed →      │
│    exit 1 (blocks merge)    │
└─────────────────────────────┘
          │
          ▼
   Branch protection checks
   gate-verdict must be green
```

---

## Troubleshooting

### "phase must be 1–7"

The `phase` input must be a single digit from 1 to 7.  Check your matrix
definition.

### Gates pass locally but fail in CI

Common causes:

1. **Missing dependencies.**  The action installs `.[dev]` by default, which
   includes `pytest`, `fastapi`, `httpx`, and `ruff`.  If your project
   needs additional dependencies, use the `install-extras` input.

2. **Python version mismatch.**  CI defaults to 3.13.  If your project
   requires a different version, set `python-version`.

3. **Missing CI workflow.**  `gate_ci_workflow` checks for
   `.github/workflows/ci.yml`.  If your CI file has a different name,
   create a symlink or adjust the gate (see `EXTENDING.md`).

4. **Contract validation.**  `gate_contract_schema` validates every YAML in
   `contracts/` against the `DoneContract` schema.  Malformed YAML or
   schema mismatches will fail.

### "sealed: false" even with `seal: true`

Sealing is skipped when:

- Hard-block gates failed (and `force: false`)
- The `rigforge seal` command itself errored

Check the step output for the specific error.  If you want to seal despite
failures, use `force: true`.

### Verifying a sealed packet

After a PR merges with sealing enabled:

```bash
# Verify all sealed phases
rigforge verify --strict

# Check a specific packet's integrity
rigforge verify

# Verify spec binding
rigforge spec-check --proof proofs/phase5_proof.json --spec specs/phase5-acceptance.yml
```

### Updating the action

The composite action is a normal file in the repo.  To update it:

1. Edit `.github/actions/rigforge-gate/action.yml`
2. The change takes effect on the next workflow run — no action registry to
   update

---

## Security model

The merge gate inherits RIGForge's security properties:

- **No secrets required.**  The composite action reads no `secrets.*`.  It
  runs identically on fork PRs as on internal PRs.
- **No network beyond pip install.**  The test suite opens no sockets.
  `pip install` is the only network access.
- **Actions pinned to SHA.**  `actions/checkout` and `actions/setup-python`
  are pinned to full commit SHAs (Dependabot bumps these weekly).
- **Tamper-evident proofs.**  When sealing, the ProofPacket's integrity hash
  and HMAC signature make tampering detectable — the same guarantees as
  `rigforge demo`.

---

## Further reading

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — the 7-phase model, gates, and
  ProofPacket design
- [`EXTENDING.md`](./EXTENDING.md) — how to add custom gates to a phase
- [`DEPLOY.md`](./DEPLOY.md) — running the CLI, MCP server, and cockpit
- [`SECURITY.md`](../SECURITY.md) — threat model and signing design
