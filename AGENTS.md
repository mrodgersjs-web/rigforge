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
