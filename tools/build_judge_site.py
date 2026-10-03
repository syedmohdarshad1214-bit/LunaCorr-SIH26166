"""Build a small, read-only LunaCorr site for static hosting.

The scientific decision is copied only after the same frozen source checksum
checks used by the FastAPI endpoint pass. No raw science products are published.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCIENCE = ROOT / "data/derived/REALPAIR005_science_v1"
REJECTED = ROOT / "data/derived/REALPAIR001_adjusted_registration_v5"
PREVIEW = ROOT / "data/derived/REALPAIR001_camera_audit_v2"
OUT = ROOT / "output/judge-site"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_audit(folder: Path, name: str) -> None:
    for line in (folder / name).read_text().splitlines():
        expected, relative = line.split("  ", 1)
        path = folder / relative
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"Frozen scientific audit check failed: {path}")


def copy(source: Path, relative: str) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    target = OUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> None:
    verify_audit(SCIENCE, "aligned_middle_sha256_v2.txt")
    verify_audit(SCIENCE / "full_strip_tiles", "audit_sha256.txt")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    frontend = ROOT / "frontend"
    copy(frontend / "index.html", "index.html")
    for name in ("explorer.css", "evidence-panel.css", "explorer.js", "startup-loader.html", "startup-loader.js", "vendor/three-r128.min.js"):
        copy(frontend / name, f"static/{name}")
    for source in (frontend / "assets/reports").iterdir():
        if source.is_file():
            copy(source, f"static/assets/reports/{source.name}")
    # The only live API used by this read-only workbench becomes a frozen JSON.
    js = OUT / "static/explorer.js"
    source_js = js.read_text()
    assert source_js.count('fetch("/api/science-proof")') == 1
    js.write_text(source_js.replace('fetch("/api/science-proof")',
                                    'fetch("/api/science-proof.json")'))

    for source in (SCIENCE / "globe-assets").iterdir():
        if source.is_file():
            copy(source, f"science-evidence/globe-assets/{source.name}")

    science_files = [
        "ALIGNED_MIDDLE_SCIENTIFIC_VERIFICATION.md",
        "aligned_middle_decision.json", "aligned_middle_sha256_v2.txt",
        "science_roi_aligned_middle/tmc_ortho_5m.png",
        "science_roi_aligned_middle/ohrc_projected_5m.png",
        "aligned_middle_evidence/local_affine_overlay.png",
        "negative_controls_aligned_middle/metrics.json",
    ]
    for algo in ("SIFT", "AKAZE"):
        science_files += [
            f"science_roi_aligned_middle_test/{algo}/inliers_preview.png",
            f"science_roi_aligned_middle_test/{algo}/metrics.json",
            f"science_roi_aligned_middle_test/{algo}/inliers.csv",
        ]
    controls = json.loads((SCIENCE / "negative_controls_aligned_middle/metrics.json").read_text())
    science_files += [f"negative_controls_aligned_middle/{run['control']}.png"
                      for run in controls["runs"]]
    for relative in sorted(set(science_files)):
        copy(SCIENCE / relative, f"science-evidence/{relative}")

    for relative in ("audit_summary.json", "SCIENTIFIC_REPORT.md", "checksums.sha256"):
        copy(REJECTED / relative, f"rejected-evidence/{relative}")
    copy(PREVIEW / "science_comparison.png", "rejected-preview/science_comparison.png")

    proof = {
        "decision": json.loads((SCIENCE / "aligned_middle_decision.json").read_text()),
        "full_strip_summary": json.loads((SCIENCE / "full_strip_tiles/summary.json").read_text()),
        "full_strip_decision": json.loads((SCIENCE / "full_strip_tiles/decision.json").read_text()),
        "geometry": json.loads((SCIENCE / "xml_footprint_intersection.json").read_text()),
        "sift": json.loads((SCIENCE / "science_roi_aligned_middle_test/SIFT/metrics.json").read_text()),
        "akaze": json.loads((SCIENCE / "science_roi_aligned_middle_test/AKAZE/metrics.json").read_text()),
        "projection": json.loads((SCIENCE / "science_roi_aligned_middle/projection.json").read_text()),
        "integrity": "VERIFIED",
        "integrity_scope": "Frozen source artifacts verified at build time",
    }
    target = OUT / "api/science-proof.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(proof, indent=2) + "\n")

    assets = sorted(path for path in OUT.rglob("*") if path.is_file())
    checksums = "".join(f"{sha256(path)}  {path.relative_to(OUT)}\n" for path in assets)
    (OUT / "SHA256SUMS.txt").write_text(checksums)
    print(f"Built {len(assets)} files at {OUT}")
    print(f"Total bytes: {sum(path.stat().st_size for path in assets):,}")


if __name__ == "__main__":
    main()
