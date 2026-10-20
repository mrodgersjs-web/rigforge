"""Tests for the intent-routing subsystem (lattice model, parser, router,
forge engine, and the standalone forge/status commands) plus the telemetry
no-op fallback.

These modules shipped without direct tests; every public entry point they
expose is exercised here offline, with no network and no model calls.
"""

from __future__ import annotations

import json

from click.testing import CliRunner

from rigforge.commands.forge import forge_cmd
from rigforge.commands.status import status_cmd
from rigforge.forge import ForgeResult, forge
from rigforge.forge import main as forge_main
from rigforge.intents.intent_parser import Intent, IntentParser
from rigforge.intents.troika import (
    Coder,
    Tester,
    Troika,
    TroikaReport,
    TroikaResult,
    Verifier,
)
from rigforge.lattice.router import LatticeRouter
from rigforge.triple_diamond import (
    CHIEF_BLOCK,
    LATTICE,
    Cell,
    Diamond,
    LatticeConfig,
    Level,
    Mode,
    Step,
    cell,
    i1,
    l3d2a4,
    mode_from_bms,
    parse_cell_id,
)

# ── lattice model ─────────────────────────────────────────────────────────


def test_lattice_has_all_588_cells():
    # 7 levels x 3 diamonds x 4 modes x 7 workflow steps
    assert len(LATTICE) == 588
    assert all(isinstance(c, Cell) for c in LATTICE.values())


def test_cell_id_round_trip():
    c = Cell(level=Level.L3, diamond=Diamond.D2, mode=Mode.A4, step=Step.I1)
    assert c.cell_id == "L3-D2-A4-I1"
    assert str(c) == "L3-D2-A4-I1"
    assert cell("L3-D2-A4-I1") is LATTICE["L3-D2-A4-I1"]
    assert parse_cell_id("L3-D2-A4-I1") == c
    assert parse_cell_id("not-a-cell") is None


def test_with_step_returns_same_cell_family():
    c = Cell(level=Level.L2, diamond=Diamond.D1, mode=Mode.A2, step=Step.I1)
    moved = c.with_step(Step.P)
    assert moved.level == c.level and moved.diamond == c.diamond and moved.mode == c.mode
    assert moved.step == Step.P
    assert moved.cell_id == "L2-D1-A2-P"


def test_mode_from_bms_boundaries():
    assert mode_from_bms(0.75) == Mode.A1
    assert mode_from_bms(0.45) == Mode.A2
    assert mode_from_bms(0.25) == Mode.A3
    assert mode_from_bms(0.24) == Mode.A4
    assert mode_from_bms(1.0) == Mode.A1
    assert mode_from_bms(0.0) == Mode.A4


def test_chief_block_and_shortcuts():
    assert "L3-D2-A4-I1" in CHIEF_BLOCK
    assert l3d2a4().cell_id == "L3-D2-A4-I1"
    assert i1(Level.L1, Diamond.D1, Mode.A1).cell_id == "L1-D1-A1-I1"


def test_lattice_config_defaults():
    cfg = LatticeConfig()
    assert cfg.tools == []
    assert cfg.requires_proof is True
    assert cfg.human_override is False
    assert cfg.gate_threshold == 0.8


# ── intent parser ─────────────────────────────────────────────────────────


def test_parser_extracts_action_domain_target():
    parsed = IntentParser().parse("build a proof gate for the law domain")
    assert parsed.action == "build"
    assert parsed.domain == "law"
    assert parsed.target  # last token of the phrase
    assert parsed.raw.startswith("build a proof gate")


def test_parser_scores_actions_differently():
    p = IntentParser()
    assert p.parse("build a website").bms_score >= 0.35
    assert p.parse("verify the packet").bms_score >= 0.65
    assert p.parse("research the corpus").bms_score <= 0.15
    assert p.parse("frobnicate the widget").bms_score == 0.20
    assert p.parse("frobnicate the widget").action == "unknown"


def test_parser_domain_adds_to_score_and_archetype_names_mode():
    p = IntentParser()
    with_domain = p.parse("test the healthcare pipeline")
    without_domain = p.parse("test the pipeline")
    assert with_domain.bms_score > without_domain.bms_score
    assert with_domain.archetype().endswith("_archetype")


def test_parser_caches_by_text():
    p = IntentParser()
    first = p.parse("run the benchmark")
    assert p.parse("run the benchmark") is first


def test_intent_default_is_empty():
    empty = Intent()
    assert empty.raw == "" and empty.action == "unknown" and empty.cell is None


# ── lattice router ────────────────────────────────────────────────────────


def test_router_maps_keywords_to_deterministic_cells():
    r = LatticeRouter()
    route = r.route("migrate the sqlite database")
    assert route.cell.level == Level.L1
    assert route.cell.diamond == Diamond.D1
    assert route.cell.mode == Mode.A1
    assert route.bms_score >= 0.75
    assert route.confidence == "high"
    assert route.evidence_required is False  # high determinism needs no extra evidence


def test_router_falls_back_to_strategic_cell():
    route = LatticeRouter().route("frobnicate the widget")
    assert route.cell.cell_id == "L3-D2-A4-I1"
    assert route.bms_score == 0.20
    assert route.confidence == "low"
    assert route.evidence_required is True


def test_router_tools_and_mcp_hint_follow_mode():
    r = LatticeRouter()
    a1 = r.route("sqlite database")
    a3 = r.route("build an app")
    assert "terminal" in a1.tools_enabled
    assert "delegation" in a3.tools_enabled
    assert a1.mcp_hint == "codex"


def test_router_caches_and_exposes_chief_block():
    r = LatticeRouter()
    first = r.route("verify the proof")
    assert r.route("verify the proof") is first
    assert r.chief_block() == CHIEF_BLOCK
    assert r.chief_block() is not CHIEF_BLOCK  # a copy, not the shared set
    assert r.cell_is_strategic("L3-D2-A4-I1")
    assert not r.cell_is_strategic("L1-D1-A1-I1")
    assert isinstance(r.tools_for_cell(first.cell), list)


# ── troika triad ──────────────────────────────────────────────────────────


def test_troika_runs_all_three_roles_and_passes():
    report = Troika().run("seal the proof", {"model": "local"})
    assert isinstance(report, TroikaReport)
    assert [r.role for r in report.results] == ["coder", "verifier", "tester"]
    assert report.ok is True
    assert report.passed_count() == 3
    assert all(r.stdout.startswith(f"[{r.role}]") for r in report.results)


def test_troika_report_reflects_member_failures():
    failing = TroikaReport(
        results=[
            TroikaResult(role="coder", passed=True),
            TroikaResult(role="verifier", passed=False, stderr="gate failed"),
        ]
    )
    assert failing.ok is False
    assert failing.passed_count() == 1


def test_troika_member_roles_are_distinct():
    assert {Coder().role, Verifier().role, Tester().role} == {"coder", "verifier", "tester"}


# ── forge engine ──────────────────────────────────────────────────────────


def test_forge_dry_run_routes_without_executing():
    result = forge("migrate the sqlite database", dry_run=True)
    assert isinstance(result, ForgeResult)
    assert result.ok is True
    assert result.troika_ok is True
    assert result.troika_passed == 0  # the triad never ran
    assert result.cell_id == "L1-D1-A1-I1"
    assert result.proof_hash == ""


def test_forge_runs_triad_when_not_dry_run():
    result = forge("verify the proof gate")
    assert result.troika_ok is True
    assert result.troika_passed == 3
    assert result.archetype.endswith("_archetype")
    assert set(result.as_dict()) == {
        "ok", "cell_id", "bms_score", "archetype", "tools",
        "troika_ok", "troika_passed", "artifact", "proof_hash",
    }


def test_forge_module_main_is_runnable(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["forge", "run", "the", "benchmark"])
    forge_main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True and "cell_id" in payload


# ── standalone commands (unregistered click commands) ─────────────────────


def test_forge_cmd_dry_run_and_json():
    runner = CliRunner()
    res = runner.invoke(forge_cmd, ["--dry-run", "build", "an", "app"], obj={})
    assert res.exit_code == 0, res.output
    assert "L" in res.output  # a routed lattice cell id

    res_json = runner.invoke(forge_cmd, ["--dry-run", "build", "app"], obj={"json": True})
    assert res_json.exit_code == 0, res_json.output
    assert json.loads(res_json.output)["ok"] is True


def test_status_cmd_reports_lattice_counts():
    runner = CliRunner()
    res = runner.invoke(status_cmd, [], obj={})
    assert res.exit_code == 0, res.output
    assert "lattice cells: 588" in res.output
    assert "status: READY" in res.output


def test_status_cmd_reads_and_rejects_cells():
    runner = CliRunner()
    ok = runner.invoke(status_cmd, ["--cell", "L3-D2-A4-I1"], obj={})
    assert ok.exit_code == 0, ok.output
    assert "level:   L3" in ok.output

    bad = runner.invoke(status_cmd, ["--cell", "L9-D9-A9-I1"], obj={})
    assert bad.exit_code == 1
    assert "cell not found" in bad.output


# ── telemetry fallback (no OpenTelemetry installed) ───────────────────────


def test_telemetry_noop_without_otel():
    from rigforge import telemetry

    assert telemetry.is_enabled() is False
    assert telemetry.enable() is False
    with telemetry.root_span(1) as span:
        assert span is None
    with telemetry.gate_span(None, 1) as span:  # type: ignore[arg-type]
        assert span is None
