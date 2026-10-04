from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from kddt_common import KddtError, fail, load_job, load_json, now_text, save_job, save_json


TARGETS = {"static", "legacy-static", "legacy-libs", "lib/biz", "lib/bos", "lib/trd", "lib/cus"}
UPDATER_DIRS = (".kddt-staging", ".kddt-cache", ".kddt-backups")


def _inside(path: Path, root: Path) -> bool:
    return path != root and root in path.parents


def _resource_path(home: Path, path: Path) -> Path:
    """Reject tool state and symlink traversal before any resource mutation."""
    if not _inside(path, home):
        fail("resource path must be below COSMIC_HOME")
    relative = path.relative_to(home)
    top = home / relative.parts[0]
    if (relative.parts[0].startswith(".kddt-")
            or (top.exists() and any((home / name).exists() and top.samefile(home / name)
                                     for name in UPDATER_DIRS))):
        fail("resource archive cannot write updater state")
    cursor = home
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            fail(f"resource path traverses a symlink: {relative}")
    if not _inside(path.resolve(), home):
        fail(f"resource path escapes COSMIC_HOME: {relative}")
    return path


def _zip_relative(info: zipfile.ZipInfo) -> Path:
    name = info.filename
    path = PurePosixPath(name)
    if (not path.parts or path.is_absolute() or ".." in path.parts or "\\" in name
            or PureWindowsPath(name).drive or any(":" in part for part in path.parts)):
        fail(f"unsafe zip entry: {name}")
    if stat.S_ISLNK(info.external_attr >> 16):
        fail(f"zip symlink is not a resource file: {name}")
    return Path(*path.parts)


def _destination(home: Path, target: str, relative: Path) -> tuple[Path, Path]:
    parts = relative.parts
    if target == "legacy-libs":
        if parts[:2] == ("cosmic", "apppackage-cosmic"):
            component = home / "mservice-cosmic" / "lib"
            return component.joinpath(*parts[2:]), component
        if parts[:2] == ("mservice-cosmic", "lib"):
            component = home / "mservice-cosmic" / "lib"
            return home / relative, component
        return home / relative, home / parts[0]
    if target in {"static", "legacy-static"}:
        component = home / "static-file-service"
        if target == "legacy-static":
            if parts[:2] == ("webapp", "static-file-service"):
                parts = parts[2:]
            elif parts[:1] == ("static-file-service",):
                parts = parts[1:]
        return component.joinpath(*parts), component
    component = home / "mservice-cosmic" / "lib" / target.split("/", 1)[1]
    return component / relative, component


def _validate_job(job_file: Path, job: dict[str, Any]) -> tuple[Path, Path]:
    if job.get("status") not in {"completed", "applied"}:
        fail(f"job is not ready to apply: {job.get('status')}")
    for key in ("job_id", "cosmic_home", "job_dir", "job_file"):
        if not isinstance(job.get(key), str) or not job[key]:
            fail(f"job is missing {key}")
    home = Path(job["cosmic_home"]).expanduser().resolve()
    stage = Path(job["job_dir"]).resolve()
    if (not home.is_dir() or not _inside(stage, home / ".kddt-staging")
            or stage / "job.json" != job_file.resolve()
            or Path(job["job_file"]).resolve() != job_file.resolve()):
        fail("job paths do not match this COSMIC_HOME staging job")
    if not isinstance(job.get("items"), list) or not job["items"]:
        fail("job contains no resource items")
    return home, stage


def _verify_digest(stream: Any, item: dict[str, Any]) -> None:
    expected = item.get("sha256")
    md5 = item.get("md5", "")
    if not isinstance(expected, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
        fail("resource item is missing a valid recorded SHA256")
    if not isinstance(md5, str) or (md5 and not re.fullmatch(r"[a-fA-F0-9]{32}", md5)):
        fail("resource item has an invalid MD5")
    sha_hash, md5_hash = hashlib.sha256(), hashlib.md5()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        sha_hash.update(chunk)
        md5_hash.update(chunk)
    if sha_hash.hexdigest() != expected.lower() or (md5 and md5_hash.hexdigest() != md5.lower()):
        fail("staged resource digest does not match the verified job")
    stream.seek(0)


def _check_destination_names(writes: list, home: Path, prepared: Path) -> None:
    """Let the destination volume's naming rules detect aliases in the plan."""
    mirror = prepared / "destination-names"
    mirror.mkdir()
    for name in UPDATER_DIRS:
        (mirror / name).mkdir()
    device = mirror.stat().st_dev
    for source, destination in writes:
        existing = destination
        while not existing.exists():
            existing = existing.parent
        if existing.stat().st_dev != device:
            fail("resource targets and staging must use the same filesystem for path verification")
        candidate = mirror / destination.relative_to(home)
        top = mirror / destination.relative_to(home).parts[0]
        if top.exists() and any(top.samefile(mirror / name) for name in UPDATER_DIRS):
            fail("resource archive cannot alias updater state")
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            if source is None:
                candidate.mkdir(exist_ok=True)
            else:
                # Exclusive creation detects case/Unicode aliases on this volume,
                # while retaining distinct names on a case-sensitive volume.
                with candidate.open("xb"):
                    pass
        except OSError as exc:
            raise KddtError(f"resource paths conflict on the target filesystem: {destination.relative_to(home)}") from exc


def _prepare(job: dict[str, Any], home: Path, stage: Path, prepared: Path) -> tuple[list, list[Path]]:
    writes: list[tuple[Path | None, Path]] = []
    components: set[Path] = set()
    file_destinations: set[Path] = set()
    for index, item in enumerate(job["items"]):
        if not isinstance(item, dict) or item.get("target") not in TARGETS or item.get("status") != "downloaded":
            fail("resource item has an invalid target or download status")
        if not isinstance(item.get("staged_path"), str) or not item["staged_path"]:
            fail("resource item is missing its staged file")
        staged = Path(item["staged_path"]).resolve()
        if not _inside(staged, stage / "downloads") or not staged.is_file():
            fail("staged resource file is missing or outside job downloads")
        files = 0
        with staged.open("rb") as stream:
            _verify_digest(stream, item)
            with zipfile.ZipFile(stream) as archive:
                for ordinal, info in enumerate(archive.infolist()):
                    relative = _zip_relative(info)
                    # Wrapper directories have no independent resource semantics.
                    if info.is_dir() and ((item["target"] == "legacy-libs" and relative.parts == ("cosmic",))
                            or (item["target"] == "legacy-static" and relative.parts == ("webapp",))):
                        continue
                    destination, component = _destination(home, item["target"], relative)
                    _resource_path(home, destination)
                    _resource_path(home, component)
                    components.add(component)
                    if info.is_dir():
                        writes.append((None, destination))
                        continue
                    if destination in file_destinations:
                        fail(f"resource packages contain a duplicate file: {destination.relative_to(home)}")
                    file_destinations.add(destination)
                    local = prepared / f"{index}-{ordinal}"
                    with archive.open(info) as source, local.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    mode = (info.external_attr >> 16) & 0o777
                    if mode:
                        local.chmod(mode)
                    writes.append((local, destination))
                    files += 1
        if not files:
            fail("resource ZIP contains no files")
    for source, destination in writes:
        if ((source is not None and destination.is_dir())
                or (source is None and (destination.is_file() or destination in file_destinations))):
            fail(f"resource file/directory conflict: {destination.relative_to(home)}")
        for parent in destination.parents:
            if parent == home:
                break
            if parent in file_destinations or (parent.exists() and not parent.is_dir()):
                fail(f"resource parent is not a directory: {parent.relative_to(home)}")
    _check_destination_names(writes, home, prepared)
    # Keep one recovery unit when legacy and modern entries overlap.
    roots = [path for path in sorted(components) if not any(parent in components for parent in path.parents)]
    return writes, roots


def _backup(home: Path, components: list[Path]) -> Path:
    root = home / ".kddt-backups"
    if root.is_symlink():
        fail("backup directory must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    backup_dir = Path(tempfile.mkdtemp(prefix="apply-", dir=root))
    manifest: dict[str, Any] = {"created_at": now_text(), "cosmic_home": str(home), "components": []}
    for target in components:
        _resource_path(home, target)
        destination = backup_dir / "files" / target.relative_to(home)
        if _inside(destination, target) or target == destination:
            fail("backup destination must not be inside its source")
        component = {"target": str(target), "backup": str(destination), "existed": target.exists()}
        manifest["components"].append(component)
        if target.is_dir():
            shutil.copytree(target, destination, symlinks=True)
        elif target.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
    save_json(backup_dir / "backup.json", manifest)
    return backup_dir


def apply_job(job_file: Path) -> None:
    job = load_job(job_file)
    home, stage = _validate_job(job_file, job)
    try:
        # Every archive is fully read before any resource backup or mutation.
        # Applying these prepared files never reopens a mutable staged ZIP.
        with tempfile.TemporaryDirectory(prefix="apply-verify-", dir=stage) as temporary:
            writes, components = _prepare(job, home, stage, Path(temporary))
            backup_dir = _backup(home, components)
            job["backup_dir"] = str(backup_dir)
            job["phase"] = "applying"
            save_job(job)
            for source, destination in writes:
                if source is None:
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
        job["status"] = "applied"
        job["phase"] = "applied"
        job.pop("error", None)
        save_job(job)
    except Exception as exc:
        job["status"] = "failed"
        job["phase"] = "apply_failed" if job.get("phase") == "applying" else "verification_failed"
        job["error"] = str(exc)
        save_job(job)
        if isinstance(exc, KddtError):
            raise
        raise KddtError(f"resource apply failed; inspect job status and its backup: {exc}") from exc
    print(json.dumps({"ok": True, "job_id": job["job_id"], "backup_dir": str(backup_dir)}, ensure_ascii=False, indent=2))


def rollback_backup(backup_dir: Path) -> None:
    backup_dir = backup_dir.resolve()
    manifest = load_json(backup_dir / "backup.json")
    if not isinstance(manifest.get("components"), list) or not manifest["components"]:
        fail("backup manifest contains no components")
    # Previously written manifests locate their home through this standard directory.
    fallback = backup_dir.parent.parent if backup_dir.parent.name == ".kddt-backups" else None
    home_value = manifest.get("cosmic_home") or fallback
    if not home_value:
        fail("backup manifest does not identify COSMIC_HOME")
    home = Path(home_value).resolve()
    if not _inside(backup_dir, home / ".kddt-backups"):
        fail("backup is outside this COSMIC_HOME backup directory")
    checked = []
    for component in manifest["components"]:
        if (not isinstance(component, dict) or not isinstance(component.get("target"), str)
                or not isinstance(component.get("backup"), str) or not isinstance(component.get("existed"), bool)):
            fail("backup component is incomplete")
        target = _resource_path(home, Path(component["target"]))
        backup = Path(component["backup"])
        if not _inside(backup.resolve(), backup_dir / "files") or backup.is_symlink():
            fail("backup component source is outside the backup files directory")
        if component["existed"] and not backup.exists():
            fail("backup component is missing; no resources were moved")
        if target == backup_dir or _inside(backup_dir, target):
            fail("cannot roll back a root containing the active backup")
        checked.append((target, backup, component["existed"]))
    if any(a != b and _inside(a, b) for a, _, _ in checked for b, _, _ in checked):
        fail("backup components overlap")
    replaced = Path(tempfile.mkdtemp(prefix="replaced-", dir=backup_dir))
    for target, backup, existed in checked:
        if target.exists():
            held = replaced / target.relative_to(home)
            held.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(held))
        if existed:
            if backup.is_dir():
                shutil.copytree(backup, target, symlinks=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
    print(json.dumps({"ok": True, "backup_dir": str(backup_dir)}, ensure_ascii=False, indent=2))
