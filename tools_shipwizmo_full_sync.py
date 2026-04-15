#!/usr/bin/env python3
"""ShipWizmo Daily Full Sync

Runs two checks:
1) "Memory" check: looks for new likely-app directories in workspace compared to last run snapshot
   and verifies whether portal HTML already mentions them.
2) Source code sync: diffs core files between live app dirs and migration-kit dirs using sync-config.json.

Outputs JSON summaries into tracking_dir, keeping latest pointers and a dated archive.
"""

import argparse, json, os, re, subprocess, hashlib
from datetime import datetime, timezone
from pathlib import Path

CORE_EXTS = {".py", ".js", ".ts", ".tsx", ".html", ".css", ".json", ".md"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".next"}

INTENTIONAL_PATTERNS = [
    r"os\.environ\.get\(",
    r"ADMIN_DEFAULT_PASSWORD",
    r"HUBSPOT_PAT",
    r"GOOGLE_CLIENT_SECRET",
    r"GOOGLE_CLIENT_ID",
    r"CORS_ORIGINS",
    r"allow_origins=\[\"\*\"\]",
    r"pplx\.app",
    r"44489437",
    r"6282372",
    r"StaticFiles",
    r"FileResponse",
    r"MIGRATION:",
    r"SECURITY:",
]

KNOWN_LIVE_DIRS = [
    "/home/user/workspace/broad-reach-portal",
    "/home/user/workspace/broad_reach_app",
    "/home/user/workspace/customs-portal-reconstruction",
    "/home/user/workspace/exports",
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_core_file(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in CORE_EXTS


def iter_core_files(root: Path):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            p = Path(dp) / f
            if is_core_file(p):
                yield p


def run_diff(a: Path, b: Path) -> str:
    # unified diff with minimal noise
    proc = subprocess.run(["diff", "-u", str(a), str(b)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.stdout


def classify_diff(diff_text: str) -> str:
    if not diff_text.strip():
        return "no_diff"
    # If diff contains only env-var/security/hosting patterns, call it intentional
    lines = [ln for ln in diff_text.splitlines() if ln.startswith(('+', '-')) and not ln.startswith(('+++', '---'))]
    if not lines:
        return "whitespace_only"
    meaningful = "\n".join(lines)
    for pat in INTENTIONAL_PATTERNS:
        if re.search(pat, meaningful):
            return "likely_intentional"
    return "needs_review"


def snapshot_workspace_dirs() -> dict:
    root = Path("/home/user/workspace")
    dirs = []
    for p in root.iterdir():
        if not p.is_dir():
            continue
        name = p.name
        if name in {"cron_tracking", "skills"}:
            continue
        dirs.append({"name": name, "mtime": p.stat().st_mtime})
    dirs.sort(key=lambda x: x["mtime"], reverse=True)
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "dirs": dirs[:50]}


def portal_mentions(portal_html: str, token: str) -> bool:
    return token.lower() in portal_html.lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracking_dir", required=True)
    ap.add_argument("--portal_html", required=True)
    ap.add_argument("--sync_config", required=True)
    args = ap.parse_args()

    tracking = Path(args.tracking_dir)
    tracking.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    run_id = now.strftime("run%Y%m%d")

    portal_text = Path(args.portal_html).read_text(encoding="utf-8", errors="ignore")
    sync_cfg = json.loads(Path(args.sync_config).read_text())

    # Part 1: memory/workspace check
    ws_snapshot = snapshot_workspace_dirs()
    prev_snapshot_path = tracking / "workspace_snapshot.json"
    prev_snapshot = json.loads(prev_snapshot_path.read_text()) if prev_snapshot_path.exists() else {"dirs": []}
    prev_names = {d["name"] for d in prev_snapshot.get("dirs", [])}

    new_dirs = [d for d in ws_snapshot["dirs"] if d["name"] not in prev_names]
    likely_new_apps = [d for d in new_dirs if d["name"] not in {Path(p).name for p in KNOWN_LIVE_DIRS}]

    portal_check = {
        "generated_at": now.isoformat(),
        "new_workspace_dirs": likely_new_apps,
        "portal_missing": [d for d in likely_new_apps if not portal_mentions(portal_text, d["name"])],
    }

    # Part 2: diff live vs kit
    raw_diffs = {}
    classification = {}
    new_live_files = {}

    apps_obj = sync_cfg.get("apps", {})
    for name, app in apps_obj.items():
        live_dir = app.get("live_dir")
        kit_dir = app.get("kit_dir")
        if not live_dir:
            continue
        live_root = Path(live_dir)
        kit_root = Path(kit_dir)
        if not live_root.exists() or not kit_root.exists():
            continue

        live_files = {str(p.relative_to(live_root)): p for p in iter_core_files(live_root)}
        kit_files = {str(p.relative_to(kit_root)): p for p in iter_core_files(kit_root)}

        # new files in live not in kit
        live_only = sorted(set(live_files.keys()) - set(kit_files.keys()))
        if live_only:
            new_live_files[name] = live_only

        # compare overlapping
        for rel in sorted(set(live_files.keys()) & set(kit_files.keys())):
            a = live_files[rel]
            b = kit_files[rel]
            if sha256_file(a) == sha256_file(b):
                continue
            d = run_diff(a, b)
            if d.strip():
                key = f"{name}:{rel}"
                raw_diffs[key] = d
                classification[key] = classify_diff(d)

    # write outputs
    (tracking / "workspace_snapshot.json").write_text(json.dumps(ws_snapshot, indent=2))
    (tracking / f"workspace_dirs_recent_{run_id}.json").write_text(json.dumps(ws_snapshot, indent=2))

    (tracking / f"portal_tool_check_{run_id}.json").write_text(json.dumps(portal_check, indent=2))
    (tracking / "portal_tool_check_latest.json").write_text(json.dumps(portal_check, indent=2))

    (tracking / f"raw_diffs_{run_id}.json").write_text(json.dumps(raw_diffs, indent=2))
    (tracking / "raw_diffs_latest.json").write_text(json.dumps(raw_diffs, indent=2))

    (tracking / f"diff_classification_{run_id}.json").write_text(json.dumps(classification, indent=2))
    (tracking / "diff_classification_latest.json").write_text(json.dumps(classification, indent=2))

    (tracking / f"new_files_in_live_{run_id}.json").write_text(json.dumps(new_live_files, indent=2))
    (tracking / "new_files_in_live_latest.json").write_text(json.dumps(new_live_files, indent=2))

    summary = {
        "generated_at": now.isoformat(),
        "run_id": run_id,
        "portal_missing_new_dirs": portal_check["portal_missing"],
        "diff_counts": {
            "total": len(classification),
            "likely_intentional": sum(1 for v in classification.values() if v == "likely_intentional"),
            "needs_review": sum(1 for v in classification.values() if v == "needs_review"),
        },
        "new_live_files_apps": list(new_live_files.keys()),
    }
    (tracking / "last_run.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
