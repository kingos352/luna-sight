#!/usr/bin/env python3
"""Kanonik sözleşme denetleyicisi.

`governance/registry.json` içindeki kuralları depoya karşı doğrular. Yalnızca
standart kütüphane kullanır, bu yüzden bağımlılık kurulmadan da çalışır.

Kullanım:

    python scripts/check_governance.py            # denetle
    python scripts/check_governance.py --json     # makine okunur çıktı

Çıkış kodu 0 ise kanonik sözleşme korunuyor. 1 ise en az bir sert kural
ihlal edilmiş; uyarılar çıkış kodunu etkilemez.

Kurallar `docs/GOVERNANCE.md` içinde gerekçeleriyle yazılıdır. Bir kural
yanlışsa düzeltme yolu kuralı esnetmek değil, GOVERNANCE.md ve bu dosyayı
entegrasyon otoritesinin onayıyla değiştirmektir.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_REPO = Path(__file__).resolve().parent.parent
REPO = DEFAULT_REPO

_REQ_LINE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*(?:\[[^\]]*\])?\s*(?:[=<>!~]=|@|$)")
_ADR_ROW = re.compile(r"^\|\s*(ADR-\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|")
_SOURCE_ID = re.compile(
    r"""(?:SOURCE_ID\s*=|["']source_id["']\s*:|\bsource_id\s*=)\s*["']([^"']+)["']"""
)
_LONGITUDE = re.compile(r"longitude_deg_east\s*=\s*(-?\d+(?:\.\d+)?)")
_ENUM_ASSIGN = re.compile(
    r"""["']?(quality_flag|sun_visible|earth_visible|joint_visible"""
    r"""|sun_reason|earth_reason|joint_reason)["']?\s*(?::|=)\s*["']([a-z_]+)["']"""
)


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)

    def fail(self, rule: str, message: str) -> None:
        self.failures.append(f"[{rule}] {message}")

    def warn(self, rule: str, message: str) -> None:
        self.warnings.append(f"[{rule}] {message}")

    def ok(self, rule: str) -> None:
        self.checked.append(rule)


def _read(path: Path) -> str:
    """Dosyayı kodlamasına bakarak oku.

    UTF-16 kodlu dosyalar ENC-01 ile ayrıca raporlanır; burada doğru
    çözülmeleri gerekir, yoksa içerikleri hiçbir kurala görünmez.
    """
    data = path.read_bytes()
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


def _active_requirement_names(path: Path) -> dict[str, str]:
    """Yorum olmayan satırlardaki paket adlarını döndür: ad -> satır."""
    found: dict[str, str] = {}
    for raw in _read(path).splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        match = _REQ_LINE.match(line)
        if match:
            found[match.group(1).lower()] = line
    return found


def _scan_files(registry: dict) -> list[Path]:
    files: list[Path] = []
    ignore = {REPO / p for p in registry["checker"]["ignore_paths"]}
    for root in registry["checker"]["scan_roots"]:
        base = REPO / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            if path in ignore or "__pycache__" in path.parts:
                continue
            files.append(path)
    return files


def check_python_version(registry: dict, report: Report) -> None:
    rule = "PY-01"
    canon = registry["python"]
    version_file = REPO / canon["version_file"]
    has_setup = any((REPO / name).exists() for name in ("requirements.txt", "pyproject.toml"))
    if not has_setup:
        return  # Kurulum dosyası yoksa sürüm beyanı da beklenmez.
    canonical = canon["canonical_version"]
    if not version_file.exists():
        report.fail(rule, f"{canon['version_file']} yok; kanonik sürüm {canonical} beyan edilmeli.")
        return
    found = _read(version_file).strip()
    if found != canonical:
        report.fail(rule, f"{canon['version_file']} = {found!r}, kanonik {canonical!r}.")
    else:
        report.ok(rule)

    pyproject = REPO / "pyproject.toml"
    if pyproject.exists():
        match = re.search(r'requires-python\s*=\s*"([^"]+)"', _read(pyproject))
        if match and match.group(1).replace(" ", "") not in (f">={canon['min_requires_python']}",):
            report.fail(
                "PY-02",
                f"pyproject.toml requires-python = {match.group(1)!r}; "
                f"kanonik >={canon['min_requires_python']}.",
            )


def check_encoding(registry: dict, report: Report) -> None:
    """Kanonik metin dosyaları UTF-8 olmalı.

    UTF-16 kodlu bir bağımlılık dosyası pip tarafından okunabilse de git
    diff'inde, kabuk araçlarında ve bu denetleyicide metin olarak görünmez;
    `.gitattributes` içindeki `text=auto eol=lf` ile de çelişir.
    """
    files = registry["canonical_files"]
    candidates = [
        files["runtime_deps"],
        files["dev_deps"],
        files["tool_config"],
        registry["python"]["version_file"],
    ]
    for name in candidates:
        path = REPO / name
        if not path.exists():
            continue
        head = path.read_bytes()[:2]
        if head in (b"\xff\xfe", b"\xfe\xff"):
            report.fail(
                "ENC-01",
                f"{name} UTF-16 kodlu. UTF-8 olarak yeniden yaz; aksi halde satırlar "
                "metin araçlarında ve bu denetimde görünmez.",
            )


def check_canonical_files(registry: dict, report: Report) -> None:
    files = registry["canonical_files"]
    for name in files["forbidden"]:
        if (REPO / name).exists():
            report.fail(
                "DEP-01",
                f"{name} yasak: ayarlar tek kanonik dosyada tutulur "
                f"({files['tool_config']} araç ayarı, {files['runtime_deps']} çalışma zamanı, "
                f"{files['dev_deps']} geliştirme).",
            )
    runtime = REPO / files["runtime_deps"]
    dev = REPO / files["dev_deps"]
    if not runtime.exists():
        return  # Henüz kurulum dosyası gelmemiş dal.
    report.ok("DEP-01")

    runtime_name = files["runtime_deps"]
    dev_name = files["dev_deps"]
    active = _active_requirement_names(runtime)
    for package in files["dev_only_packages"]:
        if package.lower() in active:
            report.fail(
                "DEP-02",
                f"{runtime_name} içinde geliştirme paketi var: "
                f"{active[package.lower()]!r}. {dev_name} dosyasına taşı.",
            )
    if dev.exists():
        if f"-r {runtime_name}" not in _read(dev):
            report.fail("DEP-03", f"{dev_name} dosyası '-r {runtime_name}' satırını içermeli.")
    else:
        report.fail("DEP-03", f"{dev_name} yok; test araçları çalışma zamanı dosyasına karışır.")

    for package, meta in registry["proposals"].items():
        if meta["status"] != "accepted" and package.lower() in active:
            report.fail(
                "DEP-04",
                f"{package} ({meta['adr']}) durumu {meta['status']!r}: {meta['rule']} "
                f"Bulunan satır: {active[package.lower()]!r}",
            )


def check_adr(registry: dict, report: Report) -> None:
    spec = registry["adr"]
    path = REPO / spec["file"]
    if not path.exists():
        return
    seen: dict[str, str] = {}
    for line in _read(path).splitlines():
        match = _ADR_ROW.match(line.strip())
        if not match:
            continue
        adr_id, _when, decision, _why, owner = (g.strip() for g in match.groups()[:5])
        if adr_id in seen:
            report.fail(
                "ADR-01",
                f"{adr_id} iki kez tanımlı: {seen[adr_id][:40]!r} ve {decision[:40]!r}.",
            )
            continue
        seen[adr_id] = decision
        if adr_id in spec["grandfathered"]:
            continue
        number = int(adr_id.split("-")[1])
        allowed = spec["ranges"].get(owner) or spec["ranges"].get(owner.split("/")[0])
        if allowed is None:
            report.fail(
                "ADR-02",
                f"{adr_id} sahibi {owner!r} tanımlı aralıklarda yok: {sorted(spec['ranges'])}.",
            )
        elif not allowed[0] <= number <= allowed[1]:
            report.fail(
                "ADR-02",
                f"{adr_id} sahibi {owner}; bu rol {allowed[0]}-{allowed[1]} aralığını kullanır. "
                "Numara çakışmasını yapısal olarak önlemek için aralık dışına çıkılmaz.",
            )
    if seen:
        report.ok("ADR-01")


def check_identifiers(registry: dict, report: Report) -> None:
    ids = registry["identifiers"]
    geo = registry["geometry"]
    allowed_sources = set(ids["source_id"])
    enum_sets = {
        "quality_flag": set(ids["quality_flag"]),
        "sun_visible": set(ids["visibility_state"]),
        "earth_visible": set(ids["visibility_state"]),
        "joint_visible": set(ids["visibility_state"]),
        "sun_reason": set(ids["reason_code"]),
        "earth_reason": set(ids["reason_code"]),
        "joint_reason": set(ids["reason_code"]),
    }
    low, high = geo["longitude_range"]
    scanned = False
    for path in _scan_files(registry):
        scanned = True
        text = _read(path)
        rel = path.relative_to(REPO).as_posix()
        for value in set(_SOURCE_ID.findall(text)):
            if value not in allowed_sources:
                normalised = value.strip().lower().replace("_", "-")
                hint = ""
                if normalised in allowed_sources:
                    hint = f" Kanonik yazim: {normalised!r} (kucuk harf, kebab-case)."
                report.fail(
                    "ID-01",
                    f"{rel}: source_id {value!r} kayıtlı değil.{hint} "
                    "Yeni kaynak için governance/registry.json güncellenir.",
                )
        for column, value in set(_ENUM_ASSIGN.findall(text)):
            if value not in enum_sets[column]:
                report.fail(
                    "ID-02",
                    f"{rel}: {column} = {value!r} sözlük dışında. "
                    f"İzinli: {sorted(enum_sets[column])}.",
                )
        for raw in set(_LONGITUDE.findall(text)):
            value = float(raw)
            if not low <= value <= high:
                report.fail(
                    "GEO-01",
                    f"{rel}: longitude_deg_east = {value} kanonik aralık [{low}, {high}] dışında. "
                    f"Doğu-pozitif yön korunur, değer {value - 360.0:.6f} olarak yazılır.",
                )
    if scanned:
        report.ok("ID-01")


def check_outputs(registry: dict, report: Report) -> None:
    contract = registry["data_contract"]
    required = contract["required_columns"]
    for pattern in registry["checker"]["output_globs"]:
        for path in sorted(REPO.glob(pattern)):
            rel = path.relative_to(REPO).as_posix()
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                try:
                    header = next(reader)
                except StopIteration:
                    report.fail("OUT-01", f"{rel}: boş dosya.")
                    continue
                first = next(reader, None)
            if "site_id" not in header or "timestamp_utc" not in header:
                continue  # Zaman serisi değil (ufuk profili, duyarlılık taraması vb.).
            missing = [column for column in required if column not in header]
            if missing:
                report.fail("OUT-01", f"{rel}: zorunlu kolonlar eksik: {missing}.")
            if first and contract["parameters_format"] == "json-object" and "parameters" in header:
                value = first[header.index("parameters")].strip()
                if value and not value.startswith("{"):
                    report.warn(
                        "OUT-02",
                        f"{rel}: parameters alanı JSON nesnesi değil ({value[:40]!r}). "
                        f"{contract['parameters_grace']}",
                    )
    report.ok("OUT-01")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="makine okunur çıktı")
    parser.add_argument(
        "--repo",
        type=Path,
        default=DEFAULT_REPO,
        help="denetlenecek depo kökü (varsayılan: bu betiğin deposu)",
    )
    args = parser.parse_args(argv)

    global REPO
    REPO = args.repo.resolve()
    registry_path = REPO / "governance" / "registry.json"
    if not registry_path.exists():
        registry_path = DEFAULT_REPO / "governance" / "registry.json"
    registry = json.loads(_read(registry_path))
    report = Report()
    check_python_version(registry, report)
    check_encoding(registry, report)
    check_canonical_files(registry, report)
    check_adr(registry, report)
    check_identifiers(registry, report)
    check_outputs(registry, report)

    if args.json:
        payload = {"failures": report.failures, "warnings": report.warnings}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        authority = registry["authority"]
        who = f"{authority['integrator']} ({authority['role']})"
        print(f"Kanonik sözleşme denetimi - otorite: {who}")
        print(f"Kural metni: {authority['document']}\n")
        for message in report.warnings:
            print(f"UYARI   {message}")
        for message in report.failures:
            print(f"IHLAL   {message}")
        if not report.failures:
            print(f"\nSonuc: gecti. {len(report.warnings)} uyari.")
        else:
            print(f"\nSonuc: {len(report.failures)} ihlal, {len(report.warnings)} uyari.")
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
