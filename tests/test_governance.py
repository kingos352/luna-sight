"""Kanonik sözleşme denetleyicisinin kendi testleri.

Kuralı zorlayan araç test edilmezse, sessizce yeşil kalıp kapıyı açık
bırakabilir. Her test geçici bir depo kökü kurar ve `--repo` ile denetler.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_governance

CANONICAL_RUNTIME = "numpy==2.5.4\npandas==3.1.1\n"
CANONICAL_DEV = "-r requirements.txt\n\npytest==9.2.0\nruff==0.17.5\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Sözleşmeye uyan en küçük depo."""
    (tmp_path / "governance").mkdir()
    shutil.copy(REPO_ROOT / "governance" / "registry.json", tmp_path / "governance" / "registry.json")
    (tmp_path / "requirements.txt").write_text(CANONICAL_RUNTIME, encoding="utf-8")
    (tmp_path / "requirements-dev.txt").write_text(CANONICAL_DEV, encoding="utf-8")
    (tmp_path / ".python-version").write_text("3.12\n", encoding="utf-8")
    return tmp_path


def run(repo: Path) -> int:
    return check_governance.main(["--repo", str(repo)])


def test_canonical_repo_passes(repo: Path) -> None:
    assert run(repo) == 0


def test_forbidden_pytest_ini_fails(repo: Path) -> None:
    """pytest.ini, pyproject ayarını sessizce ezdiği için yasak."""
    (repo / "pytest.ini").write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
    assert run(repo) == 1


def test_wrong_python_version_fails(repo: Path) -> None:
    (repo / ".python-version").write_text("3.11\n", encoding="utf-8")
    assert run(repo) == 1


def test_utf16_requirements_fails(repo: Path) -> None:
    (repo / "requirements.txt").write_bytes(CANONICAL_RUNTIME.encode("utf-16"))
    assert run(repo) == 1


def test_dev_package_in_runtime_fails(repo: Path) -> None:
    (repo / "requirements.txt").write_text(CANONICAL_RUNTIME + "pytest==9.2.0\n", encoding="utf-8")
    assert run(repo) == 1


def test_unapproved_proposal_fails(repo: Path) -> None:
    """ADR-006 onaylanmadan pandera kanonik dosyaya giremez."""
    (repo / "requirements.txt").write_text(CANONICAL_RUNTIME + "pandera[pandas]==0.36.0\n", encoding="utf-8")
    assert run(repo) == 1


def test_duplicate_adr_id_fails(repo: Path) -> None:
    (repo / "docs").mkdir()
    (repo / "docs" / "DECISIONS.md").write_text(
        "| ID | Zaman | Karar | Gerekçe | Sahip | Alan |\n"
        "|---|---|---|---|---|---|\n"
        "| ADR-300 | t | A kararı | x | K3 | y |\n"
        "| ADR-300 | t | B kararı | x | K3 | y |\n",
        encoding="utf-8",
    )
    assert run(repo) == 1


def test_adr_out_of_role_range_fails(repo: Path) -> None:
    (repo / "docs").mkdir()
    (repo / "docs" / "DECISIONS.md").write_text(
        "| ID | Zaman | Karar | Gerekçe | Sahip | Alan |\n"
        "|---|---|---|---|---|---|\n"
        "| ADR-250 | t | K3 kararı yanlış aralıkta | x | K3 | y |\n",
        encoding="utf-8",
    )
    assert run(repo) == 1


def test_adr_in_role_range_passes(repo: Path) -> None:
    (repo / "docs").mkdir()
    (repo / "docs" / "DECISIONS.md").write_text(
        "| ID | Zaman | Karar | Gerekçe | Sahip | Alan |\n"
        "|---|---|---|---|---|---|\n"
        "| ADR-003 | t | Devralınan karar | x | K2 | y |\n"
        "| ADR-310 | t | K3 kendi aralığında | x | K3 | y |\n",
        encoding="utf-8",
    )
    assert run(repo) == 0


def test_longitude_outside_canonical_range_fails(repo: Path) -> None:
    source = repo / "src" / "luna_sight" / "terrain"
    source.mkdir(parents=True)
    (source / "sites.py").write_text(
        "SITE = dict(site_id='Site01', longitude_deg_east=222.510447)\n", encoding="utf-8"
    )
    assert run(repo) == 1


def test_unregistered_source_id_fails(repo: Path) -> None:
    source = repo / "src" / "luna_sight" / "ephemeris"
    source.mkdir(parents=True)
    (source / "horizons.py").write_text('SOURCE_ID = "jpl_horizons"\n', encoding="utf-8")
    assert run(repo) == 1


def test_registered_source_id_passes(repo: Path) -> None:
    source = repo / "src" / "luna_sight" / "ephemeris"
    source.mkdir(parents=True)
    (source / "horizons.py").write_text('SOURCE_ID = "jpl-horizons"\n', encoding="utf-8")
    assert run(repo) == 0


def test_missing_contract_column_fails(repo: Path) -> None:
    outputs = repo / "outputs" / "k3"
    outputs.mkdir(parents=True)
    (outputs / "Site01_visibility.csv").write_text(
        "site_id,timestamp_utc,sun_az_deg\nSite01,2026-11-14T00:00:00+00:00,1.0\n", encoding="utf-8"
    )
    assert run(repo) == 1


def test_horizon_profile_is_not_a_contract_table(repo: Path) -> None:
    """Ufuk profili zaman serisi değil; sözleşme kolonları beklenmez."""
    outputs = repo / "outputs" / "k2"
    outputs.mkdir(parents=True)
    (outputs / "Site01_horizon_2000m.csv").write_text(
        "azimuth_deg,horizon_deg\n0.0,1.27\n", encoding="utf-8"
    )
    assert run(repo) == 0


def test_non_json_parameters_is_warning_only(repo: Path) -> None:
    outputs = repo / "outputs" / "k3"
    outputs.mkdir(parents=True)
    columns = json.loads((REPO_ROOT / "governance" / "registry.json").read_text(encoding="utf-8"))
    header = columns["data_contract"]["required_columns"]
    row = ["x"] * len(header)
    row[header.index("parameters")] = "hours=168.0;step_minutes=5.0"
    (outputs / "Site01_visibility.csv").write_text(
        ",".join(header) + "\n" + ",".join(row) + "\n", encoding="utf-8"
    )
    assert run(repo) == 0
