# AGENTS.md — RIGForge

## Mission
Deterministic agentic engineering platform and ProofPacket engine

## Hard rules
1. Evidence before claims. If smoke fails, the claim is false.
2. Do not add secrets, PII, prospect data, or client confidential material.
3. Do not weaken public-boundary.md.
4. Prefer updating smoke over writing aspirational README text.
5. Builder ≠ Verifier for completion claims.

## Default commands
```bash
bash scripts/smoke.sh
```

## Load order
1. Profile README (mrodgersjs-web)
2. doctrine (if relevant)
3. this AGENTS.md
4. docs/public-boundary.md

## Repository quick reference

RIGForge turns agent completion claims into signed, replayable ProofPackets and rejects tampered evidence.

- `rigforge/`: Python package, CLI, proof, verification, and service code.
- `contracts/v1/`: public versioned contracts.
- `examples/`: integrations and demonstrations.
- `scripts/`: smoke entry point.
- `docs/`: architecture, threat model, deployment, and extension guidance.
- `graft/`: generated context; read when useful and preserve unchanged.

Bootstrap from the repository root:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Test and smoke:

```bash
bash scripts/smoke.sh
```

Run the public demonstration:

```bash
rigforge demo
```

Always run the smoke command before claiming done.
