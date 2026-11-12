#!/usr/bin/env python3
"""Read-only source benchmark. Writes only to the disposable runner and its output folder."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import time
import urllib.parse
from datetime import datetime, timezone


def run(label: str, argv: list[str], cwd: pathlib.Path | None = None,
        timeout: int = 900, env: dict[str, str] | None = None) -> dict:
    started = time.perf_counter()
    try:
        p = subprocess.run(
            argv, cwd=str(cwd) if cwd else None, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, check=False, env=env
        )
        return {
            "label": label, "command": argv, "exit_code": p.returncode,
            "seconds": round(time.perf_counter() - started, 3),
            "stdout_bytes": len(p.stdout.encode()),
            "stderr_bytes": len(p.stderr.encode()),
            "stdout": p.stdout[-12000:], "stderr": p.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "label": label, "command": argv, "exit_code": None,
            "seconds": round(time.perf_counter() - started, 3),
            "timed_out": True,
            "stdout": (exc.stdout or b"").decode(errors="replace")[-12000:] if isinstance(exc.stdout, bytes) else str(exc.stdout or "")[-12000:],
            "stderr": (exc.stderr or b"").decode(errors="replace")[-4000:] if isinstance(exc.stderr, bytes) else str(exc.stderr or "")[-4000:],
        }
    except FileNotFoundError as exc:
        return {"label": label, "command": argv, "exit_code": None,
                "seconds": round(time.perf_counter() - started, 3),
                "error": str(exc)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    config = json.loads(pathlib.Path(args.targets).read_text())
    root = pathlib.Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "agentic-benchmark-work"
    root.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "runner": {"os": os.uname().sysname, "machine": os.uname().machine},
        "tools": config["tools"],
        "targets": [],
        "notes": [
            "This is a structural retrieval/indexing benchmark, not an LLM-agent quality benchmark.",
            "Source repositories are fetched at pinned commits into disposable runner directories.",
            "Tool-generated files are confined to disposable clones; no source repository refs are modified.",
            "A command failure is retained as a failure and is not treated as a zero-time success."
        ]
    }

    for target in config["targets"]:
        name = target["name"]
        work = root / name
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        clone = run("fetch_pinned_source", [
            "git", "clone", "--no-checkout", target["repository"], str(work)
        ], timeout=300)
        if clone.get("exit_code") == 0:
            fetch = run("fetch_exact_commit", [
                "git", "-C", str(work), "fetch", "--depth", "1", "origin", target["commit"]
            ], timeout=300)
            checkout = run("checkout_detached", [
                "git", "-C", str(work), "checkout", "--detach", "FETCH_HEAD"
            ], timeout=120)
        else:
            fetch, checkout = {"label": "fetch_exact_commit", "exit_code": None, "skipped": True}, {"label": "checkout_detached", "exit_code": None, "skipped": True}

        entry = {
            "name": name, "repository": target["repository"],
            "pinned_commit": target["commit"], "purpose": target["purpose"],
            "source_setup": [clone, fetch, checkout], "baseline": [],
            "codebase_memory_mcp": [], "graft_structural": []
        }
        if checkout.get("exit_code") != 0:
            entry["status"] = "source_checkout_failed"
            report["targets"].append(entry)
            continue

        # Baseline: repeatable literal repository searches, with no agent/model.
        patterns = ["supabase", "auth", "test", "risk"]
        for pattern in patterns:
            entry["baseline"].append(run(
                "ripgrep_" + pattern,
                ["rg", "-n", "--hidden", "--glob", "!.git/**", pattern, "."],
                cwd=work, timeout=120
            ))

        # Codebase Memory MCP: pinned native package; all indexing is local/no API key.
        cbm_env = os.environ.copy()
        cbm_env["CBM_CACHE_DIR"] = str(root / "cbm-cache" / name)
        cbm_env["DO_NOT_TRACK"] = "1"
        entry["codebase_memory_mcp"].append(run(
            "index_repository",
            ["codebase-memory-mcp", "cli", "--progress", "index_repository", "--repo-path", str(work)],
            cwd=work, timeout=1200, env=cbm_env
        ))
        entry["codebase_memory_mcp"].append(run(
            "list_projects",
            ["codebase-memory-mcp", "cli", "--quiet", "list_projects", "--format", "json", "--detail", "stats"],
            cwd=work, timeout=120, env=cbm_env
        ))

        # Graft (now Trail-code): structural map only. No init, hooks, agent config,
        # LLM summaries, provider key, or global installation changes.
        graft_env = os.environ.copy()
        graft_env["DO_NOT_TRACK"] = "1"
        graft_env["GRAFT_NO_REFRESH"] = "1"
        entry["graft_structural"].append(run(
            "graft_build",
            ["graft", "build", "--no-reuse"],
            cwd=work, timeout=1200, env=graft_env
        ))
        for pattern in patterns:
            entry["graft_structural"].append(run(
                "graft_grep_" + pattern,
                ["graft", "grep", pattern],
                cwd=work, timeout=120, env=graft_env
            ))

        entry["status"] = "completed_with_command_failures" if any(
            x.get("exit_code") not in (0, None) or x.get("timed_out")
            for group in (entry["baseline"], entry["codebase_memory_mcp"], entry["graft_structural"])
            for x in group
        ) else "commands_completed"
        report["targets"].append(entry)

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "output": str(out),
        "targets": [{"name": x["name"], "status": x["status"]} for x in report["targets"]]
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
