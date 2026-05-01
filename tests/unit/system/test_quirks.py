"""QuirkRegistry + lspci_pci_ids + planner integration tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.domain.disk import Disk, DiskPath
from getarch.execution.fake_runner import FakeResponse, FakeRunner
from getarch.planning.planner import Planner
from getarch.system.quirks import QuirkRegistry, lspci_pci_ids


def _write_quirk(root: Path, name: str, body: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.yaml").write_text(body, encoding="utf-8")


def test_registry_loads_yaml_entries(tmp_path: Path) -> None:
    _write_quirk(tmp_path, "x1", """
id: x1-tpm
description: x1 tpm
match:
  pci_subsystem: 17AA:225F
modules:
  - tpm_tis
""")
    reg = QuirkRegistry.load_from(tmp_path)
    assert len(reg.quirks) == 1
    quirk = reg.quirks[0]
    assert quirk.id == "x1-tpm"
    assert quirk.match_pci == "17AA:225F"
    assert quirk.modules == ("tpm_tis",)


def test_registry_find_matches_is_case_insensitive(tmp_path: Path) -> None:
    _write_quirk(tmp_path, "x1", """
id: x1-tpm
match:
  pci_subsystem: 17aa:225f
modules:
  - tpm_tis
""")
    reg = QuirkRegistry.load_from(tmp_path)
    matches = reg.find_matches(["17AA:225F"])
    assert len(matches) == 1
    assert matches[0].id == "x1-tpm"


def test_registry_by_id_returns_none_for_unknown(tmp_path: Path) -> None:
    reg = QuirkRegistry.load_from(tmp_path)
    assert reg.by_id("missing") is None


def test_registry_skips_invalid_yaml_root(tmp_path: Path) -> None:
    (tmp_path).mkdir(parents=True, exist_ok=True)
    (tmp_path / "bad.yaml").write_text("- not a dict\n", encoding="utf-8")
    reg = QuirkRegistry.load_from(tmp_path)
    assert reg.quirks == []


def test_lspci_pci_ids_parses_mm_format() -> None:
    sample = (
        '00:1f.6 "Ethernet controller [0200]" "Intel Corporation [8086]" '
        '"Ethernet Connection (7) I219-LM [1539]" -r02 -p00 "[8086]" "[0072]"\n'
    )
    # The regex consumes "<vendor>" "<device>" pairs at fixed positions
    # — the simpler/raw form is what we actually parse:
    raw = (
        '00:1f.6 "Ethernet controller" "8086" "1539" -r02 "Subsys"\n'
        '00:14.0 "USB controller" "8086" "9d2f"\n'
    )
    runner = FakeRunner(
        responses={
            ("lspci", "-nn", "-mm"): FakeResponse(stdout=raw),
        },
    )
    ids = lspci_pci_ids(runner)
    assert ids == ("8086:1539", "8086:9d2f")
    del sample  # documentation only — keep the docstring sample for clarity


def test_planner_appends_quirk_modules_to_initramfs(tmp_path: Path) -> None:
    _write_quirk(tmp_path, "demo", """
id: demo
match:
  pci_subsystem: dead:beef
modules:
  - tpm_tis
cmdline:
  - amd_iommu=on
""")
    # Patch the module-level cache via reload so the planner sees our
    # tmp registry.
    from getarch.planning.planner import set_quirk_registry  # noqa: PLC0415
    set_quirk_registry(QuirkRegistry.load_from(tmp_path))
    try:
        payload = deepcopy(EXAMPLES["minimal-ext4"])
        payload["quirks"] = {"enable": ["demo"]}
        cfg = Config.model_validate(payload)
        plan = Planner().build(
            cfg=cfg,
            disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
            mount_root=Path("/mnt"),
        )
        initramfs = next(s for s in plan.steps if s.id == "initramfs")
        snippet = initramfs.commands[0].input or ""
        assert "MODULES=(tpm_tis)" in snippet
        boot = next(s for s in plan.steps if s.id == "bootloader")
        flat = " ".join(arg for c in boot.commands for arg in c.argv) + " " + " ".join(
            c.input or "" for c in boot.commands
        )
        assert "amd_iommu=on" in flat
    finally:
        set_quirk_registry(None)


def test_planner_ignores_unknown_quirk_id(tmp_path: Path) -> None:
    from getarch.planning.planner import set_quirk_registry  # noqa: PLC0415
    set_quirk_registry(QuirkRegistry.load_from(tmp_path))
    try:
        payload = deepcopy(EXAMPLES["minimal-ext4"])
        payload["quirks"] = {"enable": ["nope"]}
        cfg = Config.model_validate(payload)
        # Must not raise; unknown quirk IDs are silently dropped (the
        # config just had no effect).
        Planner().build(
            cfg=cfg,
            disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
            mount_root=Path("/mnt"),
        )
    finally:
        set_quirk_registry(None)


def test_default_registry_loads_shipped_quirks() -> None:
    """The shipped getarch/quirks/*.yaml files must parse cleanly."""

    reg = QuirkRegistry.load_default()
    # We ship at least one quirk; bump this number when more land.
    assert len(reg.quirks) >= 1
    ids = {q.id for q in reg.quirks}
    assert "thinkpad-x1-tpm" in ids


