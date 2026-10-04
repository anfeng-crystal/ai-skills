from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from kddt_common import (detect_project, fail, load_job, md5_file, normalize_url,
                         now_id, now_text, save_job, sha256_file)
from kddt_resources import apply_job, rollback_backup


def http_get(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "kingdee-cosmic-devtools/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def url_join(base: str, *parts: str) -> str:
    cleaned = [base.rstrip("/")]
    cleaned.extend(part.strip("/") for part in parts if part)
    return "/".join(cleaned)


def job_root(cosmic_home: Path) -> Path:
    return cosmic_home / ".kddt-staging"


def job_path(cosmic_home: Path, job_id: str) -> Path:
    return job_root(cosmic_home) / job_id / "job.json"


def latest_job_file(cosmic_home: Path) -> Path:
    root = job_root(cosmic_home)
    candidates = sorted(root.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        fail(f"no jobs found under {root}")
    return candidates[0]


def resolve_cosmic_home(args: argparse.Namespace, project: Path | None = None) -> Path:
    value = args.cosmic_home or ""
    if not value and project:
        value = detect_project(project).get("cosmic_home", "")
    if not value:
        value = os.environ.get("COSMIC_HOME", "")
    if not value:
        fail("COSMIC_HOME is required; pass --cosmic-home or configure project gradle.properties")
    return Path(value).expanduser().resolve()


def resolve_res_url(args: argparse.Namespace, project: Path | None = None) -> str:
    value = args.res_url or ""
    if not value and project:
        value = detect_project(project).get("res_url", "")
    if not value:
        fail("resource URL is required; pass --res-url or configure cosmic.json")
    return normalize_url(value)


def parse_update_json(base_url: str, data: bytes) -> list[dict[str, Any]]:
    payload = json.loads(data.decode("utf-8"))
    items: list[dict[str, Any]] = []
    webapp = payload.get("webapp") or {}
    web_path = webapp.get("path") or ""
    for name, md5 in (webapp.get("files") or {}).items():
        items.append({"name": name, "type": "web", "target": "static", "md5": md5, "url": url_join(base_url, web_path, name)})
    appstore = payload.get("appstore") or {}
    app_path = appstore.get("path") or ""
    for lib_type in ("biz", "bos", "trd", "cus"):
        for name, md5 in (appstore.get(lib_type) or {}).items():
            items.append({"name": name, "type": lib_type, "target": f"lib/{lib_type}", "md5": md5, "url": url_join(base_url, app_path, lib_type, name)})
    if not items:
        fail("update.json contains no downloadable zip items")
    return items


def parse_update_md5(base_url: str) -> list[dict[str, Any]]:
    mc_style = "appstore" in base_url
    if mc_style:
        packages = [("cosmic.zip", "legacy-libs"), ("webapp.zip", "legacy-static")]
    else:
        packages = [("apppackage-cosmic.zip", "legacy-libs"), ("static-file-service.zip", "legacy-static")]
    return [{"name": name, "type": "package", "target": target, "md5": "", "url": url_join(base_url, name)} for name, target in packages]


def prepare_manifest(job: dict[str, Any]) -> None:
    base_url = normalize_url(job["res_url"])
    try:
        data = http_get(url_join(base_url, "update.json"))
        job["manifest_type"] = "update.json"
        job["items"] = parse_update_json(base_url, data)
    except Exception as json_error:
        try:
            job["remote_update_md5"] = http_get(url_join(base_url, "update.md5")).decode("utf-8", errors="replace").strip()
        except Exception:
            job["remote_update_md5"] = ""
        job["manifest_type"] = "update.md5"
        job["manifest_warning"] = str(json_error)
        job["items"] = parse_update_md5(base_url)


def download_with_resume(url: str, dest: Path, expected_md5: str = "", timeout: int = 60) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and (not expected_md5 or md5_file(dest).lower() == expected_md5.lower()):
        return
    part = dest.with_name(dest.name + ".part")
    existing = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": "kingdee-cosmic-devtools/0.1"}
    if existing:
        headers["Range"] = f"bytes={existing}-"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            mode = "ab" if existing and status == 206 else "wb"
            with part.open(mode) as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and part.exists():
            part.replace(dest)
        else:
            raise
    if part.exists():
        part.replace(dest)
    if expected_md5 and md5_file(dest).lower() != expected_md5.lower():
        dest.unlink(missing_ok=True)
        fail(f"md5 mismatch after download: {dest.name}")


def worker_run(job_file: Path) -> None:
    job = load_job(job_file)
    try:
        job["status"] = "running"
        job["phase"] = "manifest"
        save_job(job)
        if not job.get("items"):
            prepare_manifest(job)
            save_job(job)
        cache = Path(job["cosmic_home"]) / ".kddt-cache"
        stage_downloads = Path(job["job_dir"]) / "downloads"
        for item in job["items"]:
            if job.get("cancel_requested"):
                job["status"] = "canceled"
                job["phase"] = "canceled"
                save_job(job)
                return
            item["status"] = "downloading"
            job["phase"] = f"download:{item['name']}"
            save_job(job)
            cache_name = hashlib.sha256(item["url"].encode("utf-8")).hexdigest()[:16] + "-" + item["name"]
            cache_file = cache / cache_name
            download_with_resume(item["url"], cache_file, item.get("md5", ""))
            staged_file = stage_downloads / item["type"] / item["name"]
            staged_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cache_file, staged_file)
            item["cache_path"] = str(cache_file)
            item["staged_path"] = str(staged_file)
            item["sha256"] = sha256_file(staged_file)
            item["status"] = "downloaded"
            save_job(job)
        job["status"] = "completed"
        job["phase"] = "ready_to_apply"
        save_job(job)
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        save_job(job)
        raise


def create_job(args: argparse.Namespace) -> dict[str, Any]:
    project = Path(args.project).expanduser().resolve() if args.project else None
    cosmic_home = resolve_cosmic_home(args, project)
    res_url = resolve_res_url(args, project)
    job_id = now_id()
    jdir = job_root(cosmic_home) / job_id
    jdir.mkdir(parents=True, exist_ok=True)
    job = {
        "job_id": job_id,
        "status": "pending",
        "phase": "created",
        "created_at": now_text(),
        "updated_at": now_text(),
        "project": str(project) if project else "",
        "cosmic_home": str(cosmic_home),
        "res_url": res_url,
        "job_dir": str(jdir),
        "job_file": str(jdir / "job.json"),
        "items": [],
    }
    save_job(job)
    return job


def spawn_worker(job: dict[str, Any]) -> None:
    log_path = Path(job["job_dir"]) / "worker.log"
    with log_path.open("ab") as log:
        subprocess.Popen([sys.executable, str(Path(__file__).with_name("kddt_devtools.py")), "update-env", "_worker", "--job-file", job["job_file"]], stdout=log, stderr=log)
    job["worker_log"] = str(log_path)
    save_job(job)


def cmd_update_env(args: argparse.Namespace) -> None:
    action = args.env_action
    if action == "start":
        job = create_job(args)
        if args.foreground:
            worker_run(Path(job["job_file"]))
            job = load_job(Path(job["job_file"]))
        else:
            spawn_worker(job)
        print(json.dumps({"ok": True, "job_id": job["job_id"], "job_file": job["job_file"], "status": job["status"]}, ensure_ascii=False, indent=2))
        return
    if action == "_worker":
        worker_run(Path(args.job_file))
        return
    cosmic_home = resolve_cosmic_home(args, Path(args.project).expanduser().resolve() if args.project else None)
    jf = Path(args.job_file) if args.job_file else (job_path(cosmic_home, args.job_id) if args.job_id else latest_job_file(cosmic_home))
    if action == "status":
        print(json.dumps(load_job(jf), ensure_ascii=False, indent=2))
    elif action == "resume":
        job = load_job(jf)
        job["cancel_requested"] = False
        job["status"] = "pending"
        save_job(job)
        if args.foreground:
            worker_run(jf)
        else:
            spawn_worker(job)
        print(json.dumps({"ok": True, "job_id": job["job_id"], "job_file": str(jf)}, ensure_ascii=False, indent=2))
    elif action == "cancel":
        job = load_job(jf)
        job["cancel_requested"] = True
        save_job(job)
        print(json.dumps({"ok": True, "job_id": job["job_id"], "status": "cancel_requested"}, ensure_ascii=False, indent=2))
    elif action == "apply":
        apply_job(jf)
    elif action == "rollback":
        if args.backup:
            rollback_backup(Path(args.backup).expanduser().resolve())
        else:
            job = load_job(jf)
            backup = job.get("backup_dir")
            if not backup:
                fail("no backup_dir on job; pass --backup")
            rollback_backup(Path(backup))
    else:
        fail(f"unknown update-env action: {action}")
