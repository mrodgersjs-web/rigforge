# Copilot instructions

## Repository purpose

RIGForge is a deterministic agentic-engineering platform and ProofPacket engine. It turns completion claims into signed artifacts that another verifier can replay and reject when tampered with.

## Work map

- `rigforge/`: Python package, CLI, proof, verification, and service surfaces.
- `contracts/v1/`: versioned public contracts.
- `examples/`: minimal integrations and demonstrations.
- `scripts/`: deterministic smoke entry point.
- `docs/`: architecture, threat model, deployment, and extension guidance.
- `graft/`: generated context; read when needed and leave unchanged.

## Commands

Bootstrap from the repository root:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Test and smoke:

```bash
bash scripts/smoke.sh
```

Run the public tamper-detection demo:

```bash
rigforge demo
```

## Editing rules

- Evidence precedes completion claims. Builder and verifier remain separate roles.
- Preserve signature checks and `docs/public-boundary.md`.
- Keep secrets, PII, prospect data, and confidential client material out of the repository.
- Prefer executable smoke coverage over aspirational README claims.
- Always run the smoke command before claiming done.
