# Contributing to RIGForge

Thanks for considering it. RIGForge is a proof-of-integrity tool, so the bar is
simple: **every change keeps the tool honest and the suite green.**

## Setup

```bash
git clone https://github.com/mrodgersjs-web/rigforge.git
cd rigforge
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"     # add ".[dev,mcp]" to run the MCP/web tests too
pytest                       # should be all green before you start
```

## The one rule that matters here: tests must be non-vacuous

This project ships a `ProofPacket` whose whole job is to catch tampering, so a test
that can't fail is worse than no test. When you add a guarantee, **plant the failure
first**: confirm the test fails on the broken/old code, then make it pass with your
fix. (The bug that made `rigforge benchmark` hang forever shipped *because the suite
was green without ever running it* — don't recreate that.)

If you add a feature with a runnable surface (a CLI command, a benchmark, a loop),
add a test that **actually executes it**, not just imports it.

## Workflow

1. Open an issue first for anything non-trivial — especially changes to the trust
   model (see [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md)).
2. Branch, make focused commits (conventional commits: `fix:`, `feat:`, `chore:`…).
3. `pytest` green + `ruff check rigforge/ contracts/` clean.
4. Open a PR describing what you changed and how you proved it.

## Merge gate — your PR must carry a valid proof

CI runs `rigforge verify --require-signature` as a **required check**. Your PR
does not merge until it passes. This is not negotiable — RIGForge's core promise
is that every landed change is cryptographically proven, and the merge gate is how
that promise is enforced.

What this means in practice:

- Your changes must pass all gates in the phase bundle (pytest, ruff, schema
  validation).
- If you're adding a new phase or modifying gate behavior, seal the relevant
  phase and verify before pushing: `rigforge seal N --artifact ... && rigforge
  verify --require-signature`.
- The signing key is in CI secrets — you don't need it locally. CI re-seals on
  merge if needed.

If the gate fails, the PR stays open. Fix the issue, not the gate.

## Public attestation — what happens to your proofs

RIGForge's signature is **symmetric** (HMAC-SHA256): it proves integrity to the
team that holds the key, but a third party can't verify it without the key.

If your contribution needs to be publicly verifiable — downstream consumers, auditors,
or a transparency log — compose with:

- **[Sigstore](https://www.sigstore.dev/)** — keyless signing with a public
  transparency log. The ProofPacket becomes the attestation content; Sigstore
  makes it publicly checkable.
- **[in-toto](https://in-toto.io/)** — signed supply-chain layouts. Wrap the
  ProofPacket in an in-toto attestation for end-to-end provenance.
- **[SLSA](https://slsa.dev/)** — provenance framework built on in-toto. Carries
  the sealed proof through the build pipeline.

RIGForge does not do asymmetric signing natively. It does the part nobody else
does — *proving the run itself is untampered* — and hands off to a mature
attestation layer for public verifiability. See [`SECURITY.md`](SECURITY.md) for
the full HMAC limitation and compose path.

## Good first contributions

- New benchmark attack scenarios (more forgery classes → a stronger honesty gate).
- More OTel span attributes / exporter coverage.
- MCP tool surface for additional agents.
- Docs: sharper examples in `examples/`.

## Security

Found a way to forge a proof that `verify --require-signature` accepts? That's a real
vulnerability — please report it privately to **security@rodgersintelligence.com**
rather than opening a public issue, and we'll credit you.

MIT-licensed. By contributing you agree your work ships under the same license.
