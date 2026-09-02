#!/usr/bin/env python3
"""Read-only platform knowledge capture and query for metadata authoring."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator
from xml.etree import ElementTree as ET

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from control_metadata import build_control_catalog, control_catalog_markdown, filter_control_profiles, validate_control_catalog
from metadata_schema import build_knowledge_bundle, validate_knowledge_bundle

SNAPSHOT_VERSION = 3
TEMPLATE_VALUE = "1"
PRIMARY = {
    "entity": "t_meta_entitydesign",
    "form": "t_meta_formdesign",
    "mainentity": "t_meta_mainentityinfo",
}
RELATED = {
    "entity": ("t_meta_entitydesign_l", "t_meta_entitydesign_term"),
    "form": ("t_meta_formdesign_l", "t_meta_formdesign_term"),
}
REQUIRED_COLUMNS = {
    "t_meta_entitydesign": {"fid", "fnumber", "fmodeltype", "fparentid", "finheritpath", "fistemplate", "fdata"},
    "t_meta_formdesign": {"fid", "fnumber", "fentityid", "fmodeltype", "fparentid", "finheritpath", "fistemplate", "fdata"},
    "t_meta_mainentityinfo": {"fid", "fdentityid", "fmodeltype", "fistemplate"},
    "t_meta_entitydesign_l": {"fid", "flocaleid"},
    "t_meta_entitydesign_term": {"fid", "flocaleid"},
    "t_meta_formdesign_l": {"fid", "flocaleid"},
    "t_meta_formdesign_term": {"fid", "flocaleid"},
    "t_meta_bizapp": {"fid", "fnumber"},
    "t_meta_bizapp_l": {"fid", "flocaleid", "fname"},
}
SCHEMA_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TEXT_METADATA_SUFFIXES = {".dym", ".dymx", ".xml"}


class ContractError(RuntimeError):
    pass


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"不支持的 JSON 类型: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=json_default)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContractError(f"配置文件不存在: {path}")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"配置文件不可读: {exc}") from exc
    metadata = config.get("metadataAnalyzer")
    if not isinstance(metadata, dict) or metadata.get("enabled") is not True:
        raise ContractError("metadataAnalyzer.enabled 不是 true，禁止连接数据库")
    database = metadata.get("database")
    if not isinstance(database, dict):
        raise ContractError("缺少 metadataAnalyzer.database")
    missing = [key for key in ("host", "dbname", "user") if not str(database.get(key, "")).strip()]
    if missing:
        raise ContractError("数据库配置缺少必需项: " + ", ".join(missing))
    schema = str(database.get("schema", "public"))
    if not SCHEMA_PATTERN.fullmatch(schema):
        raise ContractError("database.schema 不是安全标识符")
    return config


def dotenv_value(path: Path, key: str) -> str | None:
    if not path.is_file():
        return None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        return value
    return None


def resolve_password(config: dict[str, Any], config_path: Path) -> tuple[str, str]:
    metadata = config["metadataAnalyzer"]
    database = metadata["database"]
    env_name = str(database.get("passwordEnv", "")).strip()
    if env_name and os.environ.get(env_name):
        return os.environ[env_name], "process-env"

    candidates: list[Path] = []
    for owner in (metadata, database):
        raw_paths = owner.get("envFiles", []) if isinstance(owner.get("envFiles"), list) else []
        for raw in raw_paths:
            candidate = Path(str(raw)).expanduser()
            candidates.append(candidate if candidate.is_absolute() else config_path.parent / candidate)
    candidates.extend((config_path.with_suffix(".env"), config_path.parent / ".env"))
    if env_name:
        for candidate in candidates:
            value = dotenv_value(candidate, env_name)
            if value:
                return value, "dotenv"

    legacy = str(database.get("password", "")).strip()
    if legacy:
        return legacy, "config-compat"
    raise ContractError("未找到数据库密码；已检查进程环境、项目 .env 和兼容配置字段")


def connect(config: dict[str, Any], config_path: Path):
    try:
        import psycopg2
    except ImportError as exc:
        raise ContractError("缺少 psycopg2，请先运行 bootstrap-python-env.py") from exc
    database = config["metadataAnalyzer"]["database"]
    password, source = resolve_password(config, config_path)
    schema = str(database.get("schema", "public"))
    connection = psycopg2.connect(
        host=database["host"],
        port=int(database.get("port", 5432)),
        dbname=database["dbname"],
        user=database["user"],
        password=password,
        connect_timeout=int(database.get("connectTimeoutSeconds", 10)),
        application_name="codex-metadata-change-readonly",
        options=f"-c search_path={schema}",
    )
    connection.set_session(readonly=True, autocommit=False)
    return connection, source


def get_columns(cursor, schema: str, table: str) -> list[str]:
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
        (schema, table),
    )
    return [row[0] for row in cursor.fetchall()]


def discover(cursor, schema: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT table_name,
               json_agg(column_name ORDER BY ordinal_position) AS columns
        FROM information_schema.columns
        WHERE table_schema=%s AND table_name LIKE 't_meta%%'
        GROUP BY table_name
        HAVING bool_or(column_name='fistemplate')
            OR bool_or(column_name='fdata')
            OR table_name LIKE 't_meta_%%design_r%%'
        ORDER BY table_name
        """,
        (schema,),
    )
    result = []
    for table, columns in cursor.fetchall():
        item = {"table": table, "columns": columns, "has_fistemplate": "fistemplate" in columns, "has_fdata": "fdata" in columns}
        if item["has_fistemplate"]:
            from psycopg2 import sql
            cursor.execute(
                sql.SQL("SELECT count(*) FROM {}.{} WHERE fistemplate=%s").format(sql.Identifier(schema), sql.Identifier(table)),
                (TEMPLATE_VALUE,),
            )
            item["template_rows"] = cursor.fetchone()[0]
        result.append(item)
    return result


def ensure_schema(cursor, schema: str) -> None:
    errors = []
    for table, required in REQUIRED_COLUMNS.items():
        actual = set(get_columns(cursor, schema, table))
        missing = sorted(required - actual)
        if missing:
            errors.append(f"{table}: {','.join(missing)}")
    if errors:
        raise ContractError("元数据表合同不完整: " + "; ".join(errors))


def query_rows(cursor, schema: str, table: str, where: str = "", params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    from psycopg2 import sql
    columns = get_columns(cursor, schema, table)
    query = sql.SQL("SELECT {} FROM {}.{}").format(
        sql.SQL(",").join(map(sql.Identifier, columns)), sql.Identifier(schema), sql.Identifier(table)
    )
    if where:
        query += sql.SQL(" WHERE ") + sql.SQL(where)
    order = [column for column in ("fnumber", "fid", "flocaleid", "fpkid") if column in columns]
    if order:
        query += sql.SQL(" ORDER BY ") + sql.SQL(",").join(map(sql.Identifier, order))
    cursor.execute(query, params)
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def referenced_ids(records: Iterable[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for record in records:
        parent = str(record.get("fparentid") or "").strip()
        if parent:
            ids.add(parent)
        for item in str(record.get("finheritpath") or "").split(","):
            item = item.strip()
            if item:
                ids.add(item)
    return ids


def query_by_ids(cursor, schema: str, table: str, ids: Iterable[str]) -> list[dict[str, Any]]:
    values = sorted(set(ids))
    if not values:
        return []
    return query_rows(cursor, schema, table, "fid = ANY(%s)", (values,))


def query_reference_registry(cursor, schema: str, ids: Iterable[str]) -> list[dict[str, Any]]:
    """Find unresolved design IDs in platform reference-registry tables."""
    values = sorted(set(ids))
    if not values:
        return []
    cursor.execute(
        "SELECT table_name FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name LIKE 't_meta_%%design_r%%' AND column_name='fid' "
        "ORDER BY table_name",
        (schema,),
    )
    rows = []
    for (table,) in cursor.fetchall():
        for record in query_by_ids(cursor, schema, table, values):
            record["source_table"] = table
            rows.append(record)
    return rows


def xml_summary(raw: Any) -> dict[str, Any]:
    text = "" if raw is None else str(raw)
    encoded = text.encode("utf-8")
    result: dict[str, Any] = {"bytes": len(encoded), "sha256": sha256_bytes(encoded)}
    if not text.strip():
        result.update({"format": "empty", "root": None, "nodes": 0, "unique_tags": 0})
        return result
    if not text.lstrip().startswith("<"):
        result.update({"format": "non-xml", "root": None, "nodes": 0, "unique_tags": 0})
        return result
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        result.update({"format": "invalid-xml", "root": None, "nodes": 0, "unique_tags": 0, "error": str(exc)})
        return result
    tags = Counter(element.tag for element in root.iter())
    result.update({"format": "xml", "root": root.tag, "nodes": sum(tags.values()), "unique_tags": len(tags)})
    return result


def group_related(rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("fid") or "")].append(row)
    return grouped


def normalize_records(
    template_rows: list[dict[str, Any]],
    ancestor_rows: list[dict[str, Any]],
    locales: dict[str, list[dict[str, Any]]],
    terms: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    template_ids = {str(row["fid"]) for row in template_rows}
    records = []
    for row in template_rows + [item for item in ancestor_rows if str(item["fid"]) not in template_ids]:
        copy = dict(row)
        fid = str(copy["fid"])
        copy["scope"] = "template" if fid in template_ids else "ancestor_context"
        copy["locales"] = locales.get(fid, [])
        copy["terms"] = terms.get(fid, [])
        copy["fdata_summary"] = xml_summary(copy.get("fdata"))
        records.append(copy)
    return records


def zh_name(record: dict[str, Any]) -> str:
    for locale in record.get("locales", []):
        if locale.get("flocaleid") == "zh_CN":
            return str(locale.get("fname") or "")
    return ""


def compact_catalog(kind: str, records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for record in records:
        summary = record.get("fdata_summary", {})
        result.append(
            {
                "kind": kind,
                "scope": record.get("scope", "template"),
                "fid": record.get("fid"),
                "fnumber": record.get("fnumber"),
                "fname_zh_CN": zh_name(record),
                "fmodeltype": record.get("fmodeltype"),
                "fentityid": record.get("fentityid"),
                "fparentid": record.get("fparentid"),
                "finheritpath": record.get("finheritpath"),
                "fversion": record.get("fversion"),
                "fenabled": record.get("fenabled"),
                "fbizappid": record.get("fbizappid"),
                "fdata_sha256": summary.get("sha256"),
                "fdata_bytes": summary.get("bytes"),
                "xml_format": summary.get("format"),
                "xml_root": summary.get("root"),
                "xml_nodes": summary.get("nodes"),
            }
        )
    return result


def build_reference_index(
    catalog: list[dict[str, Any]], main_records: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build the type-to-reference contract consumed by metadata changes."""
    templates = [item for item in catalog if item.get("scope") == "template"]
    model_types = sorted(
        {str(item.get("fmodeltype") or "") for item in templates if item.get("fmodeltype")}
        | {str(item.get("fmodeltype") or "") for item in main_records if item.get("fmodeltype")}
    )
    result: dict[str, Any] = {
        "index_version": 1,
        "layers": {
            "entity": {
                "table": "t_meta_entitydesign",
                "snapshot_file": "entitydesign.jsonl.gz",
                "xml_root": "EntityMetadata",
                "validates": ["fields", "entity tree", "operations", "operation plugins"],
            },
            "form": {
                "table": "t_meta_formdesign",
                "snapshot_file": "formdesign.jsonl.gz",
                "control_catalog": "control-catalog.json",
                "xml_root": "FormMetadata",
                "validates": ["controls", "list columns", "toolbar", "interface rules", "page plugins"],
            },
            "mainentity": {
                "table": "t_meta_mainentityinfo",
                "snapshot_file": "mainentityinfo.jsonl.gz",
                "xml_root": None,
                "validates": ["storage mapping", "number/name keys", "workflow/import/print flags"],
            },
            "entity_l": {"table": "t_meta_entitydesign_l", "embedded_in": "entitydesign.jsonl.gz"},
            "form_l": {"table": "t_meta_formdesign_l", "embedded_in": "formdesign.jsonl.gz"},
            "entity_term": {"table": "t_meta_entitydesign_term", "embedded_in": "entitydesign.jsonl.gz"},
            "form_term": {"table": "t_meta_formdesign_term", "embedded_in": "formdesign.jsonl.gz"},
        },
        "model_types": {},
    }
    main_counts = Counter(str(row.get("fmodeltype") or "") for row in main_records)
    for model_type in model_types:
        entities = [item for item in templates if item.get("kind") == "entity" and item.get("fmodeltype") == model_type]
        forms = [item for item in templates if item.get("kind") == "form" and item.get("fmodeltype") == model_type]
        entity_ids = {str(item.get("fid")) for item in entities}
        form_ids = {str(item.get("fid")) for item in forms}
        result["model_types"][model_type] = {
            "entity_templates": len(entities),
            "form_templates": len(forms),
            "mainentity_templates": main_counts.get(model_type, 0),
            "paired_numbers": len({item.get("fnumber") for item in entities} & {item.get("fnumber") for item in forms}),
            "entity_family_entries": sorted(
                str(item.get("fnumber"))
                for item in entities
                if not str(item.get("fparentid") or "").strip() or str(item.get("fparentid")) not in entity_ids
            ),
            "form_family_entries": sorted(
                str(item.get("fnumber"))
                for item in forms
                if not str(item.get("fparentid") or "").strip() or str(item.get("fparentid")) not in form_ids
            ),
            "entity_xml_roots": sorted({str(item.get("xml_root")) for item in entities if item.get("xml_root")}),
            "form_xml_roots": sorted({str(item.get("xml_root")) for item in forms if item.get("xml_root")}),
        }
    return result


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")


def write_knowledge_bundle(path: Path, bundle: dict[str, Any]) -> list[str]:
    path.mkdir(parents=True, exist_ok=True)
    names = []
    for name, payload in bundle["payloads"].items():
        write_json(path / name, payload)
        names.append(name)
    write_json(path / "manifest.json", bundle["manifest"])
    return ["manifest.json", *sorted(names)]


def load_knowledge_bundle(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        raise ContractError(f"缺少知识库 manifest.json: {path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payloads = {}
    for name in (manifest.get("payload_sha256") or {}):
        payload_path = path / name
        if payload_path.is_file():
            payloads[name] = json.loads(payload_path.read_text(encoding="utf-8"))
    return manifest, payloads


def write_jsonl_gz(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(canonical_json(row) + "\n")
            count += 1
    return count


def read_jsonl_gz(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def inside_git(path: Path) -> bool:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    result = subprocess.run(
        ["git", "-C", str(probe), "rev-parse", "--is-inside-work-tree"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def default_snapshot_dir(environment: str) -> Path:
    configured = os.environ.get("KINGDEE_METADATA_CHANGE_CACHE_DIR")
    if configured:
        cache_root = Path(configured).expanduser()
    elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        cache_root = Path(os.environ["LOCALAPPDATA"]) / "Codex"
    elif sys.platform == "darwin":
        cache_root = Path.home() / "Library" / "Caches" / "Codex"
    else:
        cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "codex"
    root = cache_root / "kingdee-metadata-change" / environment
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / stamp


def prepare_output(path: Path, allow_git_output: bool) -> Path:
    path = path.expanduser().resolve()
    if inside_git(path) and not allow_git_output:
        raise ContractError("快照输出位于 Git 工作树；请改用缓存目录或显式传 --allow-git-output")
    if path.exists() and any(path.iterdir()):
        raise ContractError(f"输出目录已存在且非空: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def snapshot(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser().resolve()
    config = load_config(config_path)
    schema = str(config["metadataAnalyzer"]["database"].get("schema", "public"))
    output = prepare_output(Path(args.output) if args.output else default_snapshot_dir(args.environment), args.allow_git_output)
    connection, credential_source = connect(config, config_path)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT set_config('statement_timeout', %s, true)", (f"{args.timeout_seconds}s",))
        cursor.execute("SHOW transaction_read_only")
        if cursor.fetchone()[0] != "on":
            raise ContractError("数据库事务不是只读状态")
        ensure_schema(cursor, schema)
        discovery = discover(cursor, schema)

        all_records: dict[str, list[dict[str, Any]]] = {}
        unresolved: dict[str, list[str]] = {}
        reference_only: dict[str, list[str]] = {}
        registry_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for kind in ("entity", "form"):
            table = PRIMARY[kind]
            templates = query_rows(cursor, schema, table, "fistemplate=%s", (TEMPLATE_VALUE,))
            template_ids = {str(row["fid"]) for row in templates}
            dependency_ids = referenced_ids(templates) - template_ids
            ancestors = query_by_ids(cursor, schema, table, dependency_ids)
            captured_ids = template_ids | {str(row["fid"]) for row in ancestors}
            missing_definition = dependency_ids - captured_ids
            registry_rows = query_reference_registry(cursor, schema, missing_definition)
            registered_ids = {str(row.get("fid")) for row in registry_rows}
            for row in registry_rows:
                registry_by_id[str(row.get("fid"))].append(row)
            reference_only[kind] = sorted(missing_definition & registered_ids)
            unresolved[kind] = sorted(missing_definition - registered_ids)
            locale_table, term_table = RELATED[kind]
            locales = group_related(query_by_ids(cursor, schema, locale_table, captured_ids))
            terms = group_related(query_by_ids(cursor, schema, term_table, captured_ids))
            all_records[kind] = normalize_records(templates, ancestors, locales, terms)

        main_records = query_rows(cursor, schema, PRIMARY["mainentity"], "fistemplate=%s", (TEMPLATE_VALUE,))
        for record in main_records:
            record["scope"] = "template"
        all_records["mainentity"] = main_records

        app_ids = sorted(
            {
                str(record.get("fbizappid") or "").strip()
                for records in all_records.values()
                for record in records
                if str(record.get("fbizappid") or "").strip()
            }
        )
        app_rows = query_by_ids(cursor, schema, "t_meta_bizapp", app_ids)
        resolved_app_ids = {str(row.get("fid")) for row in app_rows}
        app_locales = group_related(query_by_ids(cursor, schema, "t_meta_bizapp_l", app_ids))
        app_context = []
        for row in app_rows:
            app_context.append(
                {
                    "fid": row.get("fid"),
                    "fnumber": row.get("fnumber"),
                    "fmodeltype": row.get("fmodeltype"),
                    "fparentid": row.get("fparentid"),
                    "finheritpath": row.get("finheritpath"),
                    "fversion": row.get("fversion"),
                    "locales": app_locales.get(str(row.get("fid")), []),
                }
            )

        reference_registry = [
            {"fid": fid, "registrations": rows}
            for fid, rows in sorted(registry_by_id.items())
        ]
        connection.rollback()
    finally:
        connection.close()

    write_json(output / "discovery.json", discovery)
    catalog = compact_catalog("entity", all_records["entity"]) + compact_catalog("form", all_records["form"])
    write_json(output / "catalog.json", catalog)
    reference_index = build_reference_index(catalog, all_records["mainentity"])
    write_json(output / "reference-index.json", reference_index)
    control_catalog = build_control_catalog(all_records["form"])
    write_json(output / "control-catalog.json", control_catalog)
    (output / "control-catalog-summary.md").write_text(control_catalog_markdown(control_catalog), encoding="utf-8")
    knowledge_bundle = build_knowledge_bundle(
        all_records["entity"],
        all_records["form"],
        all_records["mainentity"],
        control_catalog,
        {
            "environment": args.environment,
            "schema": schema,
            "tables": sorted(PRIMARY.values()),
            "template_filter": "fistemplate='1'",
        },
    )
    knowledge_names = write_knowledge_bundle(output / "knowledge", knowledge_bundle)
    write_jsonl_gz(output / "entitydesign.jsonl.gz", all_records["entity"])
    write_jsonl_gz(output / "formdesign.jsonl.gz", all_records["form"])
    write_jsonl_gz(output / "mainentityinfo.jsonl.gz", all_records["mainentity"])
    write_jsonl_gz(output / "app-context.jsonl.gz", app_context)
    write_jsonl_gz(output / "reference-registry.jsonl.gz", reference_registry)

    template_catalog = [item for item in catalog if item["scope"] == "template"]
    entity_numbers = {str(item.get("fnumber")) for item in template_catalog if item["kind"] == "entity"}
    form_numbers = {str(item.get("fnumber")) for item in template_catalog if item["kind"] == "form"}
    unknown_template_tables = sorted(
        item["table"]
        for item in discovery
        if item.get("has_fistemplate") and item["table"] not in set(PRIMARY.values())
    )
    duplicates = {}
    for kind in ("entity", "form"):
        counts = Counter(str(item.get("fnumber")) for item in template_catalog if item["kind"] == kind)
        duplicates[kind] = sorted(number for number, count in counts.items() if count > 1)
    invalid_xml = [
        {"kind": item["kind"], "fnumber": item["fnumber"], "format": item["xml_format"]}
        for item in template_catalog
        if item["xml_format"] != "xml"
    ]
    missing_zh = [
        {"kind": item["kind"], "fnumber": item["fnumber"]}
        for item in template_catalog
        if not item["fname_zh_CN"]
    ]
    files = {}
    snapshot_files = [
        "discovery.json",
        "catalog.json",
        "reference-index.json",
        "control-catalog.json",
        "control-catalog-summary.md",
        "entitydesign.jsonl.gz",
        "formdesign.jsonl.gz",
        "mainentityinfo.jsonl.gz",
        "app-context.jsonl.gz",
        "reference-registry.jsonl.gz",
        *(f"knowledge/{name}" for name in knowledge_names),
    ]
    for name in snapshot_files:
        path = output / name
        files[name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}

    manifest = {
        "snapshot_version": SNAPSHOT_VERSION,
        "environment": args.environment,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "kind": "kingdee-metadata-database-readonly",
            "schema": schema,
            "config_name": config_path.name,
            "config_sha256": sha256_file(config_path),
            "credential_source": credential_source,
            "template_filter": "fistemplate='1'",
            "statement_timeout_seconds": args.timeout_seconds,
        },
        "counts": {
            "entity_templates": sum(1 for row in all_records["entity"] if row["scope"] == "template"),
            "entity_ancestor_context": sum(1 for row in all_records["entity"] if row["scope"] == "ancestor_context"),
            "form_templates": sum(1 for row in all_records["form"] if row["scope"] == "template"),
            "form_ancestor_context": sum(1 for row in all_records["form"] if row["scope"] == "ancestor_context"),
            "mainentity_templates": len(all_records["mainentity"]),
            "app_context": len(app_context),
            "reference_registry_ids": len(reference_registry),
            "form_pages": control_catalog["summary"]["form_pages"],
            "control_nodes": control_catalog["summary"]["control_nodes"],
            "control_types": control_catalog["summary"]["control_types"],
            **knowledge_bundle["manifest"]["counts"],
        },
        "quality": {
            "duplicate_numbers": duplicates,
            "invalid_or_non_xml": invalid_xml,
            "missing_zh_CN_name": missing_zh,
            "reference_only_ancestor_ids": reference_only,
            "unresolved_ancestor_ids": unresolved,
            "unknown_template_tables": unknown_template_tables,
            "missing_app_context_ids": sorted(set(app_ids) - resolved_app_ids),
            "entity_without_form": sorted(entity_numbers - form_numbers),
            "form_without_entity": sorted(form_numbers - entity_numbers),
        },
        "files": files,
    }
    write_json(output / "manifest.json", manifest)
    print(f"__SNAPSHOT_DIR__={output}")
    quality_summary = {
        "duplicate_numbers": {kind: len(values) for kind, values in duplicates.items()},
        "invalid_or_non_xml": len(invalid_xml),
        "missing_zh_CN_name": len(missing_zh),
        "reference_only_ancestor_ids": {kind: len(values) for kind, values in reference_only.items()},
        "unresolved_ancestor_ids": {kind: len(values) for kind, values in unresolved.items()},
        "unknown_template_tables": len(unknown_template_tables),
        "missing_app_context_ids": len(set(app_ids) - resolved_app_ids),
        "entity_without_form": len(entity_numbers - form_numbers),
        "form_without_entity": len(form_numbers - entity_numbers),
    }
    print(json.dumps({"counts": manifest["counts"], "quality": quality_summary}, ensure_ascii=False))
    return 0


def load_manifest(snapshot_dir: Path) -> dict[str, Any]:
    path = snapshot_dir / "manifest.json"
    if not path.is_file():
        raise ContractError(f"缺少 manifest.json: {snapshot_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify(args: argparse.Namespace) -> int:
    root = Path(args.snapshot).expanduser().resolve()
    manifest = load_manifest(root)
    errors = []
    if manifest.get("snapshot_version") != SNAPSHOT_VERSION:
        errors.append(f"快照版本不是当前版本 {SNAPSHOT_VERSION}，需重新采集")
    for name, expected in manifest.get("files", {}).items():
        path = root / name
        if not path.is_file():
            errors.append(f"缺少文件: {name}")
            continue
        actual = sha256_file(path)
        if actual != expected.get("sha256"):
            errors.append(f"哈希不一致: {name}")
    quality = manifest.get("quality", {})
    duplicate_numbers = quality.get("duplicate_numbers") or {}
    if any(duplicate_numbers.get(kind) for kind in ("entity", "form")):
        errors.append("存在重复模板编码")
    if quality.get("invalid_or_non_xml"):
        errors.append("存在空、非 XML 或无法解析的模板 fdata")
    unresolved = quality.get("unresolved_ancestor_ids") or {}
    if unresolved.get("entity") or unresolved.get("form"):
        errors.append("存在未解析祖先")
    if quality.get("unknown_template_tables"):
        errors.append("发现未纳入快照合同的新模板表")
    if quality.get("missing_app_context_ids"):
        errors.append("存在未解析应用上下文")
    try:
        reference_index = load_reference_index(root)
        catalog_model_types = {
            str(item.get("fmodeltype"))
            for item in load_catalog(root)
            if item.get("scope") == "template" and item.get("fmodeltype")
        }
        missing_model_types = sorted(catalog_model_types - set(reference_index.get("model_types", {})))
        if missing_model_types:
            errors.append("引用索引缺少模型类型: " + ", ".join(missing_model_types))
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        errors.append(f"引用索引不可用: {exc}")
    control_catalog_path = root / "control-catalog.json"
    if not control_catalog_path.is_file():
        errors.append("缺少 control-catalog.json")
    else:
        try:
            control_errors = validate_control_catalog(json.loads(control_catalog_path.read_text(encoding="utf-8")))
            errors.extend(control_errors)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"控件目录不可用: {exc}")
    try:
        knowledge_manifest, knowledge_payloads = load_knowledge_bundle(root / "knowledge")
        # The snapshot is immutable capture evidence. Accept its self-consistent
        # historical derived-knowledge schema; active authoring knowledge is
        # rematerialized and checked against the current schema separately.
        errors.extend(validate_knowledge_bundle(knowledge_manifest, knowledge_payloads, required_version=None))
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        errors.append(f"写入知识库不可用: {exc}")
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    missing_names = quality.get("missing_zh_CN_name") or []
    reference_only = quality.get("reference_only_ancestor_ids") or {}
    if missing_names:
        print(f"[WARNING] {len(missing_names)} 个模板缺少 zh_CN 名称", file=sys.stderr)
    reference_count = len(set(reference_only.get("entity") or []) | set(reference_only.get("form") or []))
    if reference_count:
        print(f"[WARNING] {reference_count} 个继承引用只有登记、没有定义内容", file=sys.stderr)
    print("snapshot: valid")
    print(json.dumps(manifest.get("counts", {}), ensure_ascii=False))
    return 0


def load_catalog(root: Path) -> list[dict[str, Any]]:
    path = root / "catalog.json"
    if not path.is_file():
        raise ContractError(f"缺少 catalog.json: {root}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_control_catalog(root: Path) -> dict[str, Any]:
    path = root / "control-catalog.json"
    if not path.is_file():
        raise ContractError(f"缺少 control-catalog.json: {root}")
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"控件目录不可读: {exc}") from exc
    errors = validate_control_catalog(catalog)
    if errors:
        raise ContractError("控件目录无效: " + "; ".join(errors))
    return catalog


def control_types(args: argparse.Namespace) -> int:
    root = Path(args.snapshot).expanduser().resolve()
    catalog = load_control_catalog(root)
    result = []
    for control_type, info in catalog["control_types"].items():
        if args.family and info.get("family") != args.family:
            continue
        if args.query and args.query.lower() not in control_type.lower():
            continue
        profiles = filter_control_profiles(info, args.host_model_type, args.page_model_type, args.parent_type)
        if any((args.host_model_type, args.page_model_type, args.parent_type)) and not profiles:
            continue
        usable_profiles = [profile for profile in profiles if profile.get("full_definition_nodes", 0) > 0]
        if args.usable_for_new and not usable_profiles:
            continue
        result.append(
            {
                "control_type": control_type,
                "family": info.get("family"),
                "occurrences": info.get("occurrences"),
                "full_definition_nodes": info.get("full_definition_nodes"),
                "host_model_types": info.get("host_model_types"),
                "page_model_types": info.get("page_model_types"),
                "parent_types": info.get("parent_types"),
                "matching_profiles": len(profiles),
                "usable_profiles_for_new": len(usable_profiles),
            }
        )
    result.sort(key=lambda item: (-int(item["occurrences"] or 0), item["control_type"]))
    if args.limit is not None and args.limit > 0:
        result = result[: args.limit]
    print(
        json.dumps(
            {
                "source": catalog["source"],
                "filters": {
                    "host_model_type": args.host_model_type,
                    "page_model_type": args.page_model_type,
                    "parent_type": args.parent_type,
                    "family": args.family,
                    "usable_for_new": args.usable_for_new,
                },
                "count": len(result),
                "control_types": result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def control_show(args: argparse.Namespace) -> int:
    root = Path(args.snapshot).expanduser().resolve()
    catalog = load_control_catalog(root)
    info = catalog["control_types"].get(args.control_type)
    if not info:
        raise ContractError(f"生产标准模板中未发现控件类型: {args.control_type}")
    profiles = filter_control_profiles(info, args.host_model_type, args.page_model_type, args.parent_type)
    compatible = [profile for profile in profiles if profile.get("full_definition_nodes", 0) > 0]
    filtered = any((args.host_model_type, args.page_model_type, args.parent_type))
    output = {
        "status": "observed" if (compatible or not filtered) else "unsupported",
        "control_type": args.control_type,
        "family": info.get("family"),
        "source": catalog["source"],
        "filters": {
            "host_model_type": args.host_model_type,
            "page_model_type": args.page_model_type,
            "parent_type": args.parent_type,
        },
        "occurrences": info.get("occurrences"),
        "full_definition_nodes": info.get("full_definition_nodes"),
        "override_or_partial_nodes": info.get("override_or_partial_nodes"),
        "host_model_types": info.get("host_model_types"),
        "page_model_types": info.get("page_model_types"),
        "parent_types": info.get("parent_types"),
        "properties": info.get("properties"),
        "nested_sections": info.get("nested_sections"),
        "binding_properties": info.get("binding_properties"),
        "matching_profiles": profiles,
        "meaning": "observed 只表示该类型/模型/父容器组合在目标环境标准模板中有完整实例；新增身份仍必须由平台设计器生成",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["status"] == "observed" else 1


def control_model_diff(args: argparse.Namespace) -> int:
    root = Path(args.snapshot).expanduser().resolve()
    catalog = load_control_catalog(root)

    def usable(model_type: str) -> set[str]:
        return {
            control_type
            for control_type, info in catalog["control_types"].items()
            if any(
                profile.get("host_model_type") == model_type and profile.get("full_definition_nodes", 0) > 0
                for profile in info.get("profiles", [])
            )
        }

    left = usable(args.left_model_type)
    right = usable(args.right_model_type)
    output = {
        "source": catalog["source"],
        "left_model_type": args.left_model_type,
        "right_model_type": args.right_model_type,
        "left_count": len(left),
        "right_count": len(right),
        "shared": sorted(left & right),
        "left_only": sorted(left - right),
        "right_only": sorted(right - left),
        "meaning": "only 表示本次目标环境标准模板中只在该宿主模型发现完整定义，不是平台跨版本的永久禁用清单",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def matches(item: dict[str, Any], args: argparse.Namespace) -> bool:
    if getattr(args, "kind", None) and item.get("kind") != args.kind:
        return False
    if getattr(args, "scope", None) and item.get("scope") != args.scope:
        return False
    if getattr(args, "model_type", None) and item.get("fmodeltype") != args.model_type:
        return False
    query = getattr(args, "query", None)
    if query:
        text = f"{item.get('fnumber','')} {item.get('fname_zh_CN','')}".lower()
        if query.lower() not in text:
            return False
    return True


def list_records(args: argparse.Namespace) -> int:
    root = Path(args.snapshot).expanduser().resolve()
    items = [item for item in load_catalog(root) if matches(item, args)]
    if args.limit is not None:
        items = items[: args.limit]
    print(json.dumps(items, ensure_ascii=False, indent=2))
    return 0


def select_catalog(root: Path, number: str, kind: str | None) -> list[dict[str, Any]]:
    return [item for item in load_catalog(root) if item.get("fnumber") == number and (not kind or item.get("kind") == kind)]


def show(args: argparse.Namespace) -> int:
    root = Path(args.snapshot).expanduser().resolve()
    items = select_catalog(root, args.number, args.kind)
    if not items:
        raise ContractError(f"快照中未找到模板: {args.number}")
    print(json.dumps(items, ensure_ascii=False, indent=2))
    return 0


def record_file(kind: str) -> str:
    return {"entity": "entitydesign.jsonl.gz", "form": "formdesign.jsonl.gz"}[kind]


def load_kind_records(root: Path, kind: str) -> list[dict[str, Any]]:
    return list(read_jsonl_gz(root / record_file(kind)))


def lineage(args: argparse.Namespace) -> int:
    root = Path(args.snapshot).expanduser().resolve()
    records = load_kind_records(root, args.kind)
    targets = [row for row in records if row.get("fnumber") == args.number]
    if not targets:
        raise ContractError(f"未找到 {args.kind} 模板: {args.number}")
    by_id = {str(row.get("fid")): row for row in records}
    registry_path = root / "reference-registry.jsonl.gz"
    registered = {str(row.get("fid")) for row in read_jsonl_gz(registry_path)} if registry_path.is_file() else set()
    target = targets[0]
    ids = [item.strip() for item in str(target.get("finheritpath") or "").split(",") if item.strip()]
    parent = str(target.get("fparentid") or "").strip()
    if parent and parent not in ids:
        ids.append(parent)
    chain = []
    for fid in ids:
        row = by_id.get(fid)
        chain.append(
            {
                "fid": fid,
                "resolved": row is not None,
                "reference_only": row is None and fid in registered,
                "scope": row.get("scope") if row else None,
                "fnumber": row.get("fnumber") if row else None,
                "fname_zh_CN": zh_name(row) if row else None,
                "fdata_sha256": row.get("fdata_summary", {}).get("sha256") if row else None,
            }
        )
    print(json.dumps({"target": args.number, "kind": args.kind, "chain": chain}, ensure_ascii=False, indent=2))
    return 1 if any(not item["resolved"] for item in chain) else 0


def extract(args: argparse.Namespace) -> int:
    root = Path(args.snapshot).expanduser().resolve()
    records = load_kind_records(root, args.kind)
    targets = [row for row in records if row.get("fnumber") == args.number]
    if not targets:
        raise ContractError(f"未找到 {args.kind} 模板: {args.number}")
    output = Path(args.output).expanduser().resolve()
    if output.exists() and not args.overwrite:
        raise ContractError(f"输出文件已存在: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(str(targets[0].get("fdata") or ""), encoding="utf-8")
    print(json.dumps({"output": str(output), "sha256": sha256_file(output)}, ensure_ascii=False))
    return 0


def diff(args: argparse.Namespace) -> int:
    left_root = Path(args.left).expanduser().resolve()
    right_root = Path(args.right).expanduser().resolve()
    left = {(item["kind"], item.get("fnumber")): item for item in load_catalog(left_root) if item.get("scope") == "template"}
    right = {(item["kind"], item.get("fnumber")): item for item in load_catalog(right_root) if item.get("scope") == "template"}
    added = sorted([{"kind": key[0], "fnumber": key[1]} for key in right.keys() - left.keys()], key=lambda item: (item["kind"], item["fnumber"]))
    removed = sorted([{"kind": key[0], "fnumber": key[1]} for key in left.keys() - right.keys()], key=lambda item: (item["kind"], item["fnumber"]))
    changed = []
    for key in sorted(left.keys() & right.keys()):
        fields = {}
        for field in ("fdata_sha256", "fmodeltype", "fparentid", "finheritpath", "fversion", "fname_zh_CN"):
            if left[key].get(field) != right[key].get(field):
                fields[field] = {"left": left[key].get(field), "right": right[key].get(field)}
        if fields:
            changed.append({"kind": key[0], "fnumber": key[1], "fields": fields})
    result = {"added": added, "removed": removed, "changed": changed, "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)}}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def load_reference_index(root: Path) -> dict[str, Any]:
    path = root / "reference-index.json"
    if not path.is_file():
        raise ContractError(f"缺少 reference-index.json: {root}")
    return json.loads(path.read_text(encoding="utf-8"))


def split_inherit_path(raw: str | None) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def resolve_reference_chain(
    catalog: list[dict[str, Any]], kind: str, inherit_path: str | None, parent_id: str | None = None
) -> dict[str, Any]:
    ids = split_inherit_path(inherit_path)
    parent = str(parent_id or "").strip()
    if parent and parent not in ids:
        ids.append(parent)
    by_id = {str(item.get("fid")): item for item in catalog if item.get("kind") == kind}
    matched = []
    unmatched = []
    for fid in ids:
        item = by_id.get(fid)
        if item:
            matched.append(
                {
                    "fid": fid,
                    "fnumber": item.get("fnumber"),
                    "fmodeltype": item.get("fmodeltype"),
                    "scope": item.get("scope"),
                    "fdata_sha256": item.get("fdata_sha256"),
                    "source_file": record_file(kind),
                }
            )
        else:
            unmatched.append(fid)
    return {"kind": kind, "chain_ids": ids, "matched": matched, "unmatched": unmatched}


def compact_side_row(row: dict[str, Any], source_file: str) -> dict[str, Any]:
    result = {key: value for key, value in row.items() if key != "fdata"}
    raw = str(row.get("fdata") or "")
    if "fdata" in row:
        result["fdata_sha256"] = sha256_bytes(raw.encode("utf-8"))
        result["fdata_bytes"] = len(raw.encode("utf-8"))
    result["source_file"] = source_file
    result["row_sha256"] = sha256_bytes(canonical_json(row).encode("utf-8"))
    return result


def reference_plan(args: argparse.Namespace) -> int:
    root = Path(args.snapshot).expanduser().resolve()
    index = load_reference_index(root)
    catalog = load_catalog(root)
    contract = index.get("change_types", {}).get(args.change_type)
    if not contract:
        raise ContractError(f"未知变更类型: {args.change_type}")
    model = index.get("model_types", {}).get(args.model_type)
    if not model:
        raise ContractError(f"快照中不存在模型类型: {args.model_type}")

    paths = {
        "entity": (args.entity_inherit_path, args.entity_parent_id),
        "form": (args.form_inherit_path, args.form_parent_id),
    }
    references = {}
    missing_evidence = []
    verified_business_ids = set(args.verified_business_ancestor_id or [])
    manifest = load_manifest(root)
    reference_only_quality = manifest.get("quality", {}).get("reference_only_ancestor_ids", {})
    reference_only_ids = set(reference_only_quality.get("entity") or []) | set(reference_only_quality.get("form") or [])
    required_kinds = {layer for layer in contract["layers"] if layer in ("entity", "form")}
    if any(layer in contract["layers"] for layer in ("entity_l", "entity_term", "mainentity")):
        required_kinds.add("entity")
    if any(layer in contract["layers"] for layer in ("form_l", "form_term")):
        required_kinds.add("form")

    for kind in sorted(required_kinds):
        inherit_path, parent_id = paths[kind]
        if not inherit_path and not parent_id:
            missing_evidence.append(f"{kind} 的 finheritpath/fparentid")
            continue
        resolved = resolve_reference_chain(catalog, kind, inherit_path, parent_id)
        blocked_reference_only = sorted(set(resolved["unmatched"]) & reference_only_ids)
        verified = sorted((set(resolved["unmatched"]) & verified_business_ids) - reference_only_ids)
        unresolved = sorted(set(resolved["unmatched"]) - set(verified) - reference_only_ids)
        resolved["reference_only_ids"] = blocked_reference_only
        resolved["verified_business_ancestor_ids"] = verified
        resolved["unresolved_ids"] = unresolved
        wrong_model = [item for item in resolved["matched"] if item.get("fmodeltype") != args.model_type]
        if wrong_model:
            resolved["model_type_mismatches"] = wrong_model
            missing_evidence.append(f"{kind} 命中模板的 ModelType 与目标不一致")
        if not resolved["matched"]:
            missing_evidence.append(f"{kind} 未匹配任何基对象模板")
        if blocked_reference_only:
            missing_evidence.append(f"{kind} 存在只有登记、没有定义的标准祖先")
        if unresolved:
            missing_evidence.append(f"{kind} 存在未提供业务取证的祖先")
        references[kind] = resolved

    side_tables = [layer for layer in contract["layers"] if layer not in ("entity", "form")]
    side_references: dict[str, dict[str, Any]] = {}
    matched_ids = {
        kind: {str(item.get("fid")) for item in references.get(kind, {}).get("matched", [])}
        for kind in ("entity", "form")
    }
    if "mainentity" in side_tables:
        rows = [
            row for row in read_jsonl_gz(root / "mainentityinfo.jsonl.gz")
            if str(row.get("fdentityid")) in matched_ids["entity"]
        ]
        side_references["mainentity"] = {
            "status": "present" if rows else "confirmed_absent",
            "source_file": "mainentityinfo.jsonl.gz",
            "records": [compact_side_row(row, "mainentityinfo.jsonl.gz") for row in rows],
        }
        if not rows:
            missing_evidence.append("标准实体链没有对应 mainentity 模板行")
    for layer, kind, collection_name in (
        ("entity_l", "entity", "locales"),
        ("form_l", "form", "locales"),
        ("entity_term", "entity", "terms"),
        ("form_term", "form", "terms"),
    ):
        if layer not in side_tables:
            continue
        rows = []
        for record in load_kind_records(root, kind):
            if str(record.get("fid")) not in matched_ids[kind]:
                continue
            rows.extend(compact_side_row(row, record_file(kind)) for row in record.get(collection_name, []))
        side_references[layer] = {
            "status": "present" if rows else "confirmed_absent",
            "source_file": record_file(kind),
            "records": rows,
        }
    if side_tables:
        missing_evidence.append("目标业务对象对应侧表记录: " + ", ".join(side_tables))

    status = "ready" if not missing_evidence and all(not value.get("model_type_mismatches") for value in references.values()) else "incomplete"
    result = {
        "status": status,
        "change_type": args.change_type,
        "model_type": args.model_type,
        "required_layers": contract["layers"],
        "required_rule_files": contract.get("rule_files", []),
        "conditional_rule_files": contract.get("conditional_rule_files", {}),
        "layer_contracts": {layer: index["layers"].get(layer) for layer in contract["layers"]},
        "model_type_contract": model,
        "references": references,
        "standard_side_references": side_references,
        "missing_evidence": missing_evidence,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status == "ready" else 1


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def metadata_value(root: ET.Element, name: str) -> str:
    for child in list(root):
        if local_tag(child.tag) == name:
            return (child.text or "").strip()
    return ""


def first_descendant(root: ET.Element, tag_name: str) -> ET.Element | None:
    for element in root.iter():
        if local_tag(element.tag) == tag_name:
            return element
    return None


def metadata_units(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand a deployed metadata wrapper into typed design units."""
    try:
        root = ET.fromstring(document["text"])
    except ET.ParseError as exc:
        return [{"source": document["source"], "status": "invalid", "error": str(exc)}]
    root_name = local_tag(root.tag)
    direct_kind = {"EntityMetadata": "entity", "FormMetadata": "form"}.get(root_name)
    if direct_kind:
        return [
            {
                "source": document["source"],
                "kind": direct_kind,
                "header": root,
                "xml_root": root,
                "raw_sha256": sha256_bytes(document["text"].encode("utf-8")),
            }
        ]
    if root_name != "DeployMetadata":
        return [{"source": document["source"], "status": "ignored", "xml_root_name": root_name}]

    design_tags = {
        "DesignEntityMeta": ("entity", "EntityMetadata"),
        "DesignFormMeta": ("form", "FormMetadata"),
        "DesignEntityMetaL": ("entity_l", "EntityMetadata"),
        "DesignFormMetaL": ("form_l", "FormMetadata"),
        "DesignEntityMetaTerm": ("entity_term", "EntityMetadata"),
        "DesignFormMetaTerm": ("form_term", "FormMetadata"),
    }
    units = []
    for element in root.iter():
        mapping = design_tags.get(local_tag(element.tag))
        if not mapping:
            continue
        kind, inner_tag = mapping
        data_xml = next((child for child in list(element) if local_tag(child.tag) == "DataXml"), None)
        inner = first_descendant(data_xml, inner_tag) if data_xml is not None else None
        units.append(
            {
                "source": document["source"],
                "kind": kind,
                "header": element,
                "xml_root": inner,
                "raw_sha256": sha256_bytes(ET.tostring(inner, encoding="utf-8")) if inner is not None else None,
            }
        )
    return units or [{"source": document["source"], "status": "ignored", "xml_root_name": root_name}]


def candidate_documents(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ContractError(f"候选文件不存在: {path}")
    documents = []
    if path.suffix.lower() == ".zip":
        try:
            archive = zipfile.ZipFile(path, "r")
        except zipfile.BadZipFile as exc:
            raise ContractError("候选 ZIP 无法解析") from exc
        with archive:
            total_size = 0
            for info in archive.infolist():
                member = Path(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    raise ContractError(f"ZIP 包含不安全成员: {info.filename}")
                if member.suffix.lower() not in TEXT_METADATA_SUFFIXES:
                    continue
                if info.file_size > 50 * 1024 * 1024:
                    raise ContractError(f"元数据成员过大: {info.filename}")
                total_size += info.file_size
                if total_size > 250 * 1024 * 1024:
                    raise ContractError("ZIP 元数据成员总大小超过限制")
                documents.append({"source": info.filename, "text": archive.read(info).decode("utf-8-sig")})
    elif path.suffix.lower() in TEXT_METADATA_SUFFIXES:
        documents.append({"source": path.name, "text": path.read_text(encoding="utf-8-sig")})
    else:
        raise ContractError("候选只支持 ZIP、.dym、.dymx 或 .xml")
    if not documents:
        raise ContractError("候选中没有可验证的元数据 XML")
    return documents


def direct_properties(element: ET.Element) -> dict[str, str]:
    return {
        local_tag(child.tag): (child.text or "").strip()
        for child in list(element)
        if len(child) == 0
    }


def direct_items(page: ET.Element) -> list[ET.Element]:
    items = next((child for child in list(page) if local_tag(child.tag) == "Items"), None)
    return list(items) if items is not None else []


def form_pages(root: ET.Element) -> list[ET.Element]:
    return [element for element in root.iter() if local_tag(element.tag) == "FormMetadata"]


def parent_type_for(page: ET.Element, control: ET.Element, verified: dict[str, str] | None = None) -> str:
    props = direct_properties(control)
    parent_id = props.get("ParentId", "")
    if not parent_id:
        return "none"
    page_id = direct_properties(page).get("Id", "")
    if parent_id and parent_id == page_id:
        return "FormMetadata"
    for item in direct_items(page):
        if direct_properties(item).get("Id") == parent_id:
            return local_tag(item.tag)
    if verified and parent_id in verified:
        return verified[parent_id]
    return "unresolved"


def parse_verified_parents(values: list[str] | None) -> dict[str, str]:
    result = {}
    for value in values or []:
        if "=" not in value:
            raise ContractError("--verified-parent 必须是 ParentId=ControlType")
        parent_id, control_type = value.split("=", 1)
        if not parent_id.strip() or not control_type.strip():
            raise ContractError("--verified-parent 不能包含空 ParentId 或 ControlType")
        result[parent_id.strip()] = control_type.strip()
    return result


def element_action(element: ET.Element) -> str:
    for name, value in element.attrib.items():
        if local_tag(name) == "action":
            return str(value)
    return ""


def element_oid(element: ET.Element) -> str:
    for name, value in element.attrib.items():
        if local_tag(name) == "oid":
            return str(value)
    return ""


def nested_pages_by_path(element: ET.Element) -> dict[tuple[str, ...], list[ET.Element]]:
    result: dict[tuple[str, ...], list[ET.Element]] = defaultdict(list)

    def visit(parent: ET.Element, path: tuple[str, ...]) -> None:
        tag_counts: Counter[str] = Counter()
        for child in list(parent):
            tag = local_tag(child.tag)
            ordinal = tag_counts[tag]
            tag_counts[tag] += 1
            child_path = path + (f"{tag}[{ordinal}]",)
            if tag == "FormMetadata":
                result[child_path].append(child)
            else:
                visit(child, child_path)

    visit(element, ())
    return result


def standard_oid_index(items: Iterable[ET.Element]) -> dict[str, ET.Element]:
    result = {}
    for item in items:
        props = direct_properties(item)
        for identity in (props.get("Id", ""), props.get("PkId", ""), element_oid(item)):
            if identity:
                result[identity] = item
    return result


def resolve_standard_form_root(snapshot_root: Path, unit: dict[str, Any]) -> tuple[ET.Element | None, dict[str, Any] | None]:
    candidate_root = unit.get("xml_root")
    if candidate_root is None:
        return None, None
    ids = [item.strip() for item in metadata_value(candidate_root, "InheritPath").split(",") if item.strip()]
    parent_id = metadata_value(candidate_root, "ParentId")
    if parent_id and parent_id not in ids:
        ids.append(parent_id)
    if not ids:
        return None, None
    by_id = {str(row.get("fid")): row for row in load_kind_records(snapshot_root, "form")}
    for fid in reversed(ids):
        record = by_id.get(fid)
        if not record or record.get("scope") != "template":
            continue
        try:
            return ET.fromstring(str(record.get("fdata") or "")), record
        except ET.ParseError:
            return None, record
    return None, None


def paired_form_pages(candidate_root: ET.Element, standard_root: ET.Element | None) -> list[tuple[ET.Element, ET.Element | None]]:
    pairs = [(candidate_root, standard_root)]
    queue = [(candidate_root, standard_root)]
    while queue:
        candidate_page, standard_page = queue.pop(0)
        standard_by_id = standard_oid_index(direct_items(standard_page)) if standard_page is not None else {}
        for candidate_item in direct_items(candidate_page):
            standard_item = standard_by_id.get(element_oid(candidate_item))
            candidate_nested = nested_pages_by_path(candidate_item)
            standard_nested = nested_pages_by_path(standard_item) if standard_item is not None else {}
            for path, pages in candidate_nested.items():
                standards = standard_nested.get(path, [])
                for index, page in enumerate(pages):
                    standard_nested_page = standards[index] if index < len(standards) else None
                    pair = (page, standard_nested_page)
                    pairs.append(pair)
                    queue.append(pair)
    return pairs


def effective_control_properties(control: ET.Element, standard_control: ET.Element | None) -> dict[str, str]:
    result = direct_properties(standard_control) if standard_control is not None else {}
    for child in list(control):
        if len(child) > 0:
            continue
        name = local_tag(child.tag)
        action = element_action(child)
        if action in {"reset", "setnull"}:
            result[name] = ""
        else:
            result[name] = (child.text or "").strip()
    return result


def page_item_contexts(
    candidate_page: ET.Element,
    standard_page: ET.Element | None,
    verified_parents: dict[str, str],
) -> list[dict[str, Any]]:
    standard_items = direct_items(standard_page) if standard_page is not None else []
    standard_by_id = standard_oid_index(standard_items)
    id_types = {
        direct_properties(item).get("Id", ""): local_tag(item.tag)
        for item in standard_items + direct_items(candidate_page)
        if direct_properties(item).get("Id")
    }
    standard_page_props = direct_properties(standard_page) if standard_page is not None else {}
    candidate_page_props = direct_properties(candidate_page)
    page_id = candidate_page_props.get("Id") or standard_page_props.get("Id", "")
    contexts = []
    for item in direct_items(candidate_page):
        standard_item = standard_by_id.get(element_oid(item))
        props = effective_control_properties(item, standard_item)
        parent_id = props.get("ParentId", "")
        parent_type = id_types.get(parent_id)
        if not parent_type and parent_id and parent_id == page_id:
            parent_type = "FormMetadata"
        if not parent_type:
            parent_type = "none" if not parent_id else verified_parents.get(parent_id, "unresolved")
        contexts.append(
            {
                "item": item,
                "standard_item": standard_item,
                "properties": props,
                "changed_property_names": sorted(local_tag(child.tag) for child in list(item)),
                "parent_type": parent_type,
                "action": element_action(item) or "full",
                "oid_resolved": standard_item is not None,
            }
        )
    return contexts


def control_compatibility(
    catalog: dict[str, Any],
    control_type: str,
    host_model_type: str,
    page_model_type: str,
    parent_type: str,
) -> tuple[str, list[dict[str, Any]], set[str]]:
    info = catalog["control_types"].get(control_type)
    if not info:
        return "unknown-type", [], set()
    profiles = filter_control_profiles(
        info,
        host_model_type or None,
        page_model_type or None,
        None if parent_type == "unresolved" else parent_type,
    )
    full_profiles = [profile for profile in profiles if profile.get("full_definition_nodes", 0) > 0]
    allowed_properties = {
        name
        for profile in (profiles or info.get("profiles", []))
        for name in profile.get("observed_properties", [])
    }
    allowed_properties.update(
        name
        for profile in (profiles or info.get("profiles", []))
        for name in profile.get("nested_sections", {})
    )
    if parent_type == "unresolved":
        return ("parent-evidence-required" if full_profiles else "unsupported-model"), profiles, allowed_properties
    return ("observed" if full_profiles else "unsupported-combination"), profiles, allowed_properties


def validate_controls(args: argparse.Namespace) -> int:
    root_dir = Path(args.snapshot).expanduser().resolve()
    catalog = load_control_catalog(root_dir)
    verified_parents = parse_verified_parents(args.verified_parent)
    documents = candidate_documents(Path(args.candidate).expanduser().resolve())
    units = [unit for document in documents for unit in metadata_units(document) if unit.get("kind") == "form"]
    if not units:
        raise ContractError("候选中没有表单元数据")
    results = []
    errors = []
    incomplete = []
    standard_references = []
    for unit in units:
        xml_root = unit.get("xml_root")
        if xml_root is None:
            errors.append(f"{unit['source']}: 缺少 FormMetadata")
            continue
        host_model_type = metadata_value(unit["header"], "ModelType") or metadata_value(xml_root, "ModelType")
        form_number = metadata_value(unit["header"], "Number") or metadata_value(xml_root, "Key")
        standard_root, standard_record = resolve_standard_form_root(root_dir, unit)
        if standard_record:
            standard_references.append(
                {
                    "form_number": form_number,
                    "template_number": standard_record.get("fnumber"),
                    "template_fid": standard_record.get("fid"),
                    "template_fdata_sha256": (standard_record.get("fdata_summary") or {}).get("sha256"),
                }
            )
        for page, standard_page in paired_form_pages(xml_root, standard_root):
            page_props = direct_properties(page)
            standard_page_props = direct_properties(standard_page) if standard_page is not None else {}
            page_model_type = page_props.get("ModelType") or standard_page_props.get("ModelType") or host_model_type
            page_key = page_props.get("Key") or standard_page_props.get("Key", "")
            for context in page_item_contexts(page, standard_page, verified_parents):
                item = context["item"]
                props = context["properties"]
                control_type = local_tag(item.tag)
                parent_type = context["parent_type"]
                status, profiles, allowed_properties = control_compatibility(
                    catalog, control_type, host_model_type, page_model_type, parent_type
                )
                standard_properties = (
                    {local_tag(child.tag) for child in list(context["standard_item"])}
                    if context["standard_item"] is not None
                    else set()
                )
                changed_names = set(context["changed_property_names"])
                properties_to_check = changed_names if context["action"] != "full" else set(props)
                unknown_properties = sorted(properties_to_check - allowed_properties - standard_properties) if allowed_properties else sorted(properties_to_check - standard_properties)
                item_issues = []
                if context["action"] != "full" and not context["oid_resolved"]:
                    item_issues.append("继承差量节点的 oid 未能在精确标准父模板中解析")
                if status in {"unknown-type", "unsupported-model", "unsupported-combination"}:
                    item_issues.append("生产标准模板没有该控件类型/模型/父容器的完整实例")
                elif status == "parent-evidence-required":
                    item_issues.append("父容器未在候选中定义，需由业务页面元数据取证")
                if unknown_properties:
                    item_issues.append("候选属性未在匹配的生产标准实例中出现: " + ", ".join(unknown_properties))
                if (context["action"] != "full" and not context["oid_resolved"]) or status in {"unknown-type", "unsupported-model", "unsupported-combination"} or unknown_properties:
                    errors.append(f"{form_number}/{page_key}/{props.get('Key') or '<无Key>'}: " + "; ".join(item_issues))
                elif item_issues:
                    incomplete.append(f"{form_number}/{page_key}/{props.get('Key') or '<无Key>'}: " + "; ".join(item_issues))
                results.append(
                    {
                        "source": unit["source"],
                        "form_number": form_number,
                        "host_model_type": host_model_type,
                        "page_key": page_key,
                        "page_model_type": page_model_type,
                        "control_key": props.get("Key", ""),
                        "control_name": props.get("Name", ""),
                        "control_type": control_type,
                        "parent_type": parent_type,
                        "action": context["action"],
                        "oid_resolved": context["oid_resolved"],
                        "status": status,
                        "matching_profiles": len(profiles),
                        "unknown_properties": unknown_properties,
                    }
                )
    status = "invalid" if errors else ("incomplete" if incomplete else "structurally-ready")
    print(
        json.dumps(
            {
                "status": status,
                "catalog_source": catalog["source"],
                "standard_references": standard_references,
                "controls_checked": len(results),
                "controls": results,
                "errors": errors,
                "missing_evidence": incomplete,
                "meaning": "structurally-ready 仅证明控件类型、模型、父容器和属性名都有生产标准实例，不证明业务绑定、平台身份、导入或运行正确",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status == "structurally-ready" else 1


def select_form_unit(path: Path, form_number: str | None) -> dict[str, Any]:
    units = [
        unit
        for document in candidate_documents(path)
        for unit in metadata_units(document)
        if unit.get("kind") == "form" and unit.get("xml_root") is not None
    ]
    if form_number:
        units = [
            unit
            for unit in units
            if (metadata_value(unit["header"], "Number") or metadata_value(unit["xml_root"], "Key")) == form_number
        ]
    if len(units) != 1:
        raise ContractError(f"表单候选必须唯一，实际匹配 {len(units)} 个；请用 --form-number 消歧")
    return units[0]


def select_page_pair(
    root: ET.Element,
    standard_root: ET.Element | None,
    page_key: str,
    page_model_type: str | None,
) -> tuple[ET.Element, ET.Element | None]:
    pages = []
    for page, standard_page in paired_form_pages(root, standard_root):
        props = direct_properties(page)
        standard_props = direct_properties(standard_page) if standard_page is not None else {}
        effective_key = props.get("Key") or standard_props.get("Key")
        effective_model = props.get("ModelType") or standard_props.get("ModelType")
        if effective_key == page_key and (not page_model_type or effective_model == page_model_type):
            pages.append((page, standard_page))
    if len(pages) != 1:
        raise ContractError(f"页面必须唯一，实际匹配 {len(pages)} 个: {page_key}")
    return pages[0]


def select_controls(
    page: ET.Element,
    standard_page: ET.Element | None,
    control_key: str | None,
    control_oid: str | None,
) -> list[ET.Element]:
    standard_by_oid = standard_oid_index(direct_items(standard_page)) if standard_page is not None else {}
    result = []
    for item in direct_items(page):
        if control_oid and element_oid(item) == control_oid:
            result.append(item)
            continue
        standard_item = standard_by_oid.get(element_oid(item))
        effective = effective_control_properties(item, standard_item)
        if control_key and effective.get("Key") == control_key:
            result.append(item)
    return result


def child_signatures(element: ET.Element) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for child in list(element):
        grouped[local_tag(child.tag)].append(ET.tostring(child, encoding="unicode"))
    return grouped


def effective_child_signatures(
    element: ET.Element,
    standard_element: ET.Element | None,
) -> dict[str, list[str]]:
    """Return the effective direct-child XML for full or inherited-delta nodes."""
    result = (
        copy.deepcopy(child_signatures(standard_element))
        if standard_element is not None and element_action(element) != "full"
        else {}
    )
    for name, signatures in child_signatures(element).items():
        result[name] = signatures
    return result


def context_for_control(
    page: ET.Element,
    standard_page: ET.Element | None,
    control: ET.Element,
    verified_parents: dict[str, str],
) -> dict[str, Any]:
    for context in page_item_contexts(page, standard_page, verified_parents):
        if context["item"] is control:
            return context
    raise ContractError("无法解析目标控件的标准继承上下文")


def remove_control(
    root: ET.Element,
    standard_root: ET.Element | None,
    page_key: str,
    page_model_type: str | None,
    control_key: str | None,
    control_oid: str | None,
) -> ET.Element | None:
    page, standard_page = select_page_pair(root, standard_root, page_key, page_model_type)
    controls = select_controls(page, standard_page, control_key, control_oid)
    if len(controls) > 1:
        raise ContractError("目标控件不唯一")
    if not controls:
        return None
    items = next(child for child in list(page) if local_tag(child.tag) == "Items")
    items.remove(controls[0])
    return controls[0]


def control_diff(args: argparse.Namespace) -> int:
    root_dir = Path(args.snapshot).expanduser().resolve()
    catalog = load_control_catalog(root_dir)
    baseline_unit = select_form_unit(Path(args.baseline).expanduser().resolve(), args.form_number)
    candidate_unit = select_form_unit(Path(args.candidate).expanduser().resolve(), args.form_number)
    baseline_root = baseline_unit["xml_root"]
    candidate_root = candidate_unit["xml_root"]
    baseline_standard_root, baseline_standard_record = resolve_standard_form_root(root_dir, baseline_unit)
    candidate_standard_root, candidate_standard_record = resolve_standard_form_root(root_dir, candidate_unit)
    baseline_page, baseline_standard_page = select_page_pair(
        baseline_root, baseline_standard_root, args.page_key, args.page_model_type
    )
    candidate_page, candidate_standard_page = select_page_pair(
        candidate_root, candidate_standard_root, args.page_key, args.page_model_type
    )
    baseline_controls = select_controls(
        baseline_page, baseline_standard_page, args.control_key, args.control_oid
    )
    candidate_controls = select_controls(
        candidate_page, candidate_standard_page, args.control_key, args.control_oid
    )
    verified_parents = parse_verified_parents(args.verified_parent)
    issues = []
    expected_counts = {
        "add": (0, 1),
        "modify": (1, 1),
        "move": (1, 1),
        "delete": (1, 0),
    }
    expected = expected_counts[args.mode]
    if (len(baseline_controls), len(candidate_controls)) != expected:
        issues.append(
            f"{args.mode} 要求基线/候选控件数为 {expected[0]}/{expected[1]}，实际为 {len(baseline_controls)}/{len(candidate_controls)}"
        )

    baseline_copy = copy.deepcopy(baseline_root)
    candidate_copy = copy.deepcopy(candidate_root)
    remove_control(
        baseline_copy,
        baseline_standard_root,
        args.page_key,
        args.page_model_type,
        args.control_key,
        args.control_oid,
    )
    remove_control(
        candidate_copy,
        candidate_standard_root,
        args.page_key,
        args.page_model_type,
        args.control_key,
        args.control_oid,
    )
    if ET.tostring(baseline_copy, encoding="utf-8") != ET.tostring(candidate_copy, encoding="utf-8"):
        issues.append("目标控件以外仍有元数据差异")

    changed_properties = []
    compatibility = None
    target = candidate_controls[0] if len(candidate_controls) == 1 else None
    if args.mode in {"modify", "move"} and len(baseline_controls) == 1 and target is not None:
        baseline_control = baseline_controls[0]
        baseline_context = context_for_control(
            baseline_page, baseline_standard_page, baseline_control, verified_parents
        )
        candidate_context = context_for_control(
            candidate_page, candidate_standard_page, target, verified_parents
        )
        if local_tag(baseline_control.tag) != local_tag(target.tag):
            issues.append("修改前后控件类型发生变化")
        before = effective_child_signatures(baseline_control, baseline_context["standard_item"])
        after = effective_child_signatures(target, candidate_context["standard_item"])
        changed_properties = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
        allowed = set(args.allow_property or [])
        unexpected = sorted(set(changed_properties) - allowed - ({"ParentId"} if args.mode == "move" else set()))
        if unexpected:
            issues.append("存在未批准的控件属性变化: " + ", ".join(unexpected))
        if not changed_properties:
            issues.append("目标控件没有发生变化")
        before_props = baseline_context["properties"]
        after_props = candidate_context["properties"]
        for identity in ("Id", "Key"):
            if before_props.get(identity) != after_props.get(identity):
                issues.append(f"控件身份属性 {identity} 发生变化")
        if element_oid(baseline_control) and element_oid(baseline_control) != element_oid(target):
            issues.append("继承差量控件的 oid 发生变化")
        if args.mode == "modify" and before_props.get("ParentId") != after_props.get("ParentId"):
            issues.append("普通修改不允许改变 ParentId；移动控件应使用 --mode move")
        if args.mode == "move" and before_props.get("ParentId") == after_props.get("ParentId"):
            issues.append("move 模式下 ParentId 未变化")

    if target is not None:
        target_type = local_tag(target.tag)
        if args.control_type and target_type != args.control_type:
            issues.append(f"候选控件类型不是要求的 {args.control_type}")
        candidate_context = context_for_control(
            candidate_page, candidate_standard_page, target, verified_parents
        )
        candidate_props = candidate_context["properties"]
        host_model_type = metadata_value(candidate_unit["header"], "ModelType") or metadata_value(candidate_root, "ModelType")
        page_props = direct_properties(candidate_page)
        standard_page_props = direct_properties(candidate_standard_page) if candidate_standard_page is not None else {}
        page_model_type = page_props.get("ModelType") or standard_page_props.get("ModelType") or host_model_type
        parent_type = candidate_context["parent_type"]
        state, profiles, allowed_properties = control_compatibility(
            catalog, target_type, host_model_type, page_model_type, parent_type
        )
        standard_properties = (
            {local_tag(child.tag) for child in list(candidate_context["standard_item"])}
            if candidate_context["standard_item"] is not None
            else set()
        )
        candidate_property_names = (
            {local_tag(child.tag) for child in list(target)}
            if candidate_context["action"] != "full"
            else set(candidate_props) | {local_tag(child.tag) for child in list(target)}
        )
        unknown_properties = (
            sorted(candidate_property_names - allowed_properties - standard_properties)
            if allowed_properties
            else sorted(candidate_property_names - standard_properties)
        )
        compatibility = {
            "status": state,
            "control_type": target_type,
            "host_model_type": host_model_type,
            "page_model_type": page_model_type,
            "parent_type": parent_type,
            "matching_profiles": len(profiles),
            "unknown_properties": unknown_properties,
        }
        if state != "observed":
            issues.append("候选控件类型/模型/父容器组合没有生产标准完整实例")
        if unknown_properties:
            issues.append("候选包含标准实例未出现的属性: " + ", ".join(unknown_properties))
        if args.mode == "add":
            for identity in ("Id", "Key", "ParentId"):
                if not direct_properties(target).get(identity):
                    issues.append(f"新增控件缺少 {identity}")

    status = "structurally-ready" if not issues else "invalid"
    print(
        json.dumps(
            {
                "status": status,
                "mode": args.mode,
                "form_number": args.form_number,
                "page_key": args.page_key,
                "control_key": args.control_key,
                "control_oid": args.control_oid,
                "standard_references": {
                    "baseline": baseline_standard_record.get("fnumber") if baseline_standard_record else None,
                    "candidate": candidate_standard_record.get("fnumber") if candidate_standard_record else None,
                },
                "changed_properties": changed_properties,
                "compatibility": compatibility,
                "issues": issues,
                "remaining_evidence": [
                    "新增控件的平台设计器身份与保存后导出证据" if args.mode == "add" else "目标业务页面当前控件身份",
                    "字段/操作绑定的业务元数据证据",
                    "DEV/TEST 导入、设计器重开保存、重新导出对账",
                    "真实入口页面运行验收",
                ],
                "meaning": "structurally-ready 只证明精确差异和生产标准兼容性，不等于平台回导或运行通过",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status == "structurally-ready" else 1


def validate_candidate(args: argparse.Namespace) -> int:
    root_dir = Path(args.snapshot).expanduser().resolve()
    index = load_reference_index(root_dir)
    catalog = load_catalog(root_dir)
    contract = index.get("change_types", {}).get(args.change_type)
    if not contract:
        raise ContractError(f"未知变更类型: {args.change_type}")
    documents = candidate_documents(Path(args.candidate).expanduser().resolve())
    verified_business_ids = set(args.verified_business_ancestor_id or [])
    manifest = load_manifest(root_dir)
    reference_only_quality = manifest.get("quality", {}).get("reference_only_ancestor_ids", {})
    reference_only_ids = set(reference_only_quality.get("entity") or []) | set(reference_only_quality.get("form") or [])
    expected_kinds = {layer for layer in contract["layers"] if layer in ("entity", "form")}
    if any(layer in contract["layers"] for layer in ("entity_l", "entity_term", "mainentity")):
        expected_kinds.add("entity")
    if any(layer in contract["layers"] for layer in ("form_l", "form_term")):
        expected_kinds.add("form")

    units = [unit for document in documents for unit in metadata_units(document)]
    results = []
    present_kinds = set()
    for unit in units:
        if unit.get("status"):
            results.append(unit)
            continue
        kind = unit["kind"]
        present_kinds.add(kind)
        if kind not in ("entity", "form"):
            header = unit["header"]
            results.append(
                {
                    "source": unit["source"],
                    "status": "side-table-evidence-required",
                    "kind": kind,
                    "number": metadata_value(header, "Number"),
                    "locale_id": metadata_value(unit["xml_root"], "LocaleId") if unit.get("xml_root") is not None else "",
                }
            )
            continue
        xml_root = unit.get("xml_root")
        header = unit["header"]
        root_name = local_tag(xml_root.tag) if xml_root is not None else None
        number = metadata_value(header, "Number") or metadata_value(header, "Key")
        model_type = metadata_value(header, "ModelType")
        parent_id = metadata_value(header, "ParentId")
        inherit_path = metadata_value(header, "InheritPath")
        resolved = resolve_reference_chain(catalog, kind, inherit_path, parent_id)
        hash_matches = [
            item for item in catalog
            if item.get("kind") == kind and item.get("scope") == "template" and item.get("fdata_sha256") == unit.get("raw_sha256")
        ]
        if hash_matches and not number:
            number = str(hash_matches[0].get("fnumber") or "")
        if hash_matches and not model_type:
            model_type = str(hash_matches[0].get("fmodeltype") or "")
        if number:
            self_reference = [
                item for item in catalog
                if item.get("kind") == kind and item.get("scope") == "template" and item.get("fnumber") == number
            ]
            for item in self_reference:
                if not any(match["fid"] == item.get("fid") for match in resolved["matched"]):
                    resolved["matched"].append(
                        {
                            "fid": item.get("fid"),
                            "fnumber": item.get("fnumber"),
                            "fmodeltype": item.get("fmodeltype"),
                            "scope": item.get("scope"),
                            "fdata_sha256": item.get("fdata_sha256"),
                            "source_file": record_file(kind),
                            "relation": "self-template",
                        }
                    )
        for item in hash_matches:
            if not any(match["fid"] == item.get("fid") for match in resolved["matched"]):
                resolved["matched"].append(
                    {
                        "fid": item.get("fid"),
                        "fnumber": item.get("fnumber"),
                        "fmodeltype": item.get("fmodeltype"),
                        "scope": item.get("scope"),
                        "fdata_sha256": item.get("fdata_sha256"),
                        "source_file": record_file(kind),
                        "relation": "exact-fdata-hash",
                    }
                )
        issues = []
        model_contract = index.get("model_types", {}).get(model_type)
        if xml_root is None:
            issues.append("部署元数据缺少 DataXml 中的设计 XML")
        if not model_type:
            issues.append("缺少顶层 ModelType")
        elif not model_contract:
            issues.append("ModelType 不在基对象模板引用索引中")
        elif kind == "entity" and model_contract.get("entity_templates", 0) == 0:
            issues.append("该 ModelType 没有实体模板引用")
        elif kind == "form" and model_contract.get("form_templates", 0) == 0:
            issues.append("该 ModelType 没有表单模板引用")
        if kind in expected_kinds and not resolved["matched"]:
            issues.append("未绑定到任何精确模板或模板祖先")
        wrong_models = [item for item in resolved["matched"] if item.get("fmodeltype") != model_type]
        if wrong_models:
            issues.append("匹配引用的 ModelType 与候选不一致")
        blocked_reference_only = sorted(set(resolved["unmatched"]) & reference_only_ids)
        verified = sorted((set(resolved["unmatched"]) & verified_business_ids) - reference_only_ids)
        unresolved = sorted(set(resolved["unmatched"]) - set(verified) - reference_only_ids)
        if blocked_reference_only:
            issues.append("继承链包含只有登记、没有定义内容的标准祖先")
        if unresolved:
            issues.append("继承链包含尚未由业务元数据取证的祖先")
        status = "not-required" if kind not in expected_kinds else ("ready" if not issues else "incomplete")
        results.append(
            {
                "source": unit["source"],
                "status": status,
                "kind": kind,
                "number": number,
                "model_type": model_type,
                "xml_root": root_name,
                "references": resolved["matched"],
                "verified_business_ancestor_ids": verified,
                "reference_only_ids": blocked_reference_only,
                "unresolved_chain_ids": unresolved,
                "issues": issues,
            }
        )

    missing_kinds = sorted(expected_kinds - present_kinds)
    side_layers = [layer for layer in contract["layers"] if layer not in ("entity", "form")]
    matched_ids = {
        kind: {
            str(reference.get("fid"))
            for item in results if item.get("kind") == kind
            for reference in item.get("references", [])
        }
        for kind in ("entity", "form")
    }
    standard_side_references: dict[str, dict[str, Any]] = {}
    if "mainentity" in side_layers:
        main_rows = [
            compact_side_row(row, "mainentityinfo.jsonl.gz")
            for row in read_jsonl_gz(root_dir / "mainentityinfo.jsonl.gz")
            if str(row.get("fdentityid")) in matched_ids["entity"]
        ]
        standard_side_references["mainentity"] = {
            "status": "present" if main_rows else "confirmed_absent",
            "source_file": "mainentityinfo.jsonl.gz",
            "records": main_rows,
        }
    for layer, kind, collection_name in (
        ("entity_l", "entity", "locales"),
        ("form_l", "form", "locales"),
        ("entity_term", "entity", "terms"),
        ("form_term", "form", "terms"),
    ):
        if layer not in side_layers:
            continue
        side_rows = []
        for record in load_kind_records(root_dir, kind):
            if str(record.get("fid")) in matched_ids[kind]:
                side_rows.extend(compact_side_row(row, record_file(kind)) for row in record.get(collection_name, []))
        standard_side_references[layer] = {
            "status": "present" if side_rows else "confirmed_absent",
            "source_file": record_file(kind),
            "records": side_rows,
        }
    overall_issues = []
    if missing_kinds:
        overall_issues.append("候选缺少元数据层: " + ", ".join(missing_kinds))
    if side_layers:
        overall_issues.append("仍需查询目标业务对象侧表: " + ", ".join(side_layers))
    blocking_docs = [item for item in results if item.get("kind") in expected_kinds and item.get("status") != "ready"]
    overall = "ready" if not overall_issues and not blocking_docs else "incomplete"
    output = {
        "status": overall,
        "change_type": args.change_type,
        "required_layers": contract["layers"],
        "required_rule_files": contract.get("rule_files", []),
        "conditional_rule_files": contract.get("conditional_rule_files", {}),
        "documents": results,
        "standard_side_references": standard_side_references,
        "issues": overall_issues,
        "meaning": "ready 仅表示候选已绑定正确类型的数据库标准引用，不表示元数据内容正确、已导入或已生效",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if overall == "ready" else 1


def materialize_knowledge(args: argparse.Namespace) -> int:
    snapshot_root = Path(args.snapshot).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if output.exists() and not args.overwrite:
        raise ContractError(f"知识库输出已存在；明确使用 --overwrite 才能更新: {output}")
    snapshot_manifest = load_manifest(snapshot_root)
    control_catalog = load_control_catalog(snapshot_root)
    bundle = build_knowledge_bundle(
        load_kind_records(snapshot_root, "entity"),
        load_kind_records(snapshot_root, "form"),
        list(read_jsonl_gz(snapshot_root / "mainentityinfo.jsonl.gz")),
        control_catalog,
        {
            "environment": snapshot_manifest.get("environment"),
            "snapshot_manifest_sha256": sha256_file(snapshot_root / "manifest.json"),
            "snapshot_captured_at_utc": snapshot_manifest.get("captured_at_utc"),
            "template_filter": "fistemplate='1'",
        },
    )
    standard_files = {
        "standard-entity.jsonl.gz": snapshot_root / "entitydesign.jsonl.gz",
        "standard-form.jsonl.gz": snapshot_root / "formdesign.jsonl.gz",
        "standard-mainentity.jsonl.gz": snapshot_root / "mainentityinfo.jsonl.gz",
        "standard-reference-registry.jsonl.gz": snapshot_root / "reference-registry.jsonl.gz",
    }
    bundle["manifest"]["standard_record_files"] = {
        name: {"sha256": sha256_file(source), "bytes": source.stat().st_size}
        for name, source in standard_files.items()
    }
    names = write_knowledge_bundle(output, bundle)
    for name, source in standard_files.items():
        shutil.copyfile(source, output / name)
        names.append(name)
    print(
        json.dumps(
            {
                "status": "observed",
                "output": str(output),
                "files": names,
                "counts": bundle["manifest"]["counts"],
                "authoring_verified_contracts": 0,
                "meaning": "已固化实际结构；新增身份合同仍需同版本 DEV 回导验证",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def verify_knowledge(args: argparse.Namespace) -> int:
    root = Path(args.knowledge).expanduser().resolve()
    manifest, payloads = load_knowledge_bundle(root)
    errors = validate_knowledge_bundle(manifest, payloads)
    for name, expected in (manifest.get("standard_record_files") or {}).items():
        path = root / name
        if not path.is_file():
            errors.append(f"缺少标准记录文件: {name}")
        elif sha256_file(path) != expected.get("sha256"):
            errors.append(f"标准记录文件哈希不匹配: {name}")
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "valid", "counts": manifest.get("counts", {}), "source": manifest.get("source", {})}, ensure_ascii=False, indent=2))
    return 0


def schema_show(args: argparse.Namespace) -> int:
    root = Path(args.knowledge).expanduser().resolve()
    manifest, payloads = load_knowledge_bundle(root)
    errors = validate_knowledge_bundle(manifest, payloads)
    if errors:
        raise ContractError("知识库无效: " + "; ".join(errors))
    if args.kind == "control":
        info = payloads["control-types.json"]["control_types"].get(args.node_type)
        if not info:
            print(json.dumps({"status": "unsupported", "kind": args.kind, "node_type": args.node_type}, ensure_ascii=False, indent=2))
            return 1
        profiles = [
            profile
            for profile in info["profiles"]
            if (not args.model_type or profile["host_model_type"] == args.model_type)
            and (not args.page_model_type or profile["page_model_type"] == args.page_model_type)
            and (not args.parent_type or profile["parent_type"] == args.parent_type)
        ]
        status = "observed" if any(profile["full_definition_nodes"] for profile in profiles) else "unsupported"
        print(
            json.dumps(
                {
                    "status": status,
                    "kind": "control",
                    "node_type": args.node_type,
                    "family": info.get("family"),
                    "properties": info.get("properties"),
                    "binding_properties": info.get("binding_properties"),
                    "profiles": profiles,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if status == "observed" else 1
    filename = {"entity": "entity-types.json", "form": "form-types.json"}[args.kind]
    catalog = payloads[filename]
    info = catalog["node_types"].get(args.node_type)
    if not info:
        print(json.dumps({"status": "unsupported", "kind": args.kind, "node_type": args.node_type}, ensure_ascii=False, indent=2))
        return 1
    profiles = [
        profile
        for profile in info["profiles"]
        if (not args.model_type or profile["model_type"] == args.model_type)
        and (not args.parent_type or profile["parent_type"] == args.parent_type)
    ]
    status = "observed" if any(profile["full_definition_nodes"] for profile in profiles) else "unsupported"
    print(
        json.dumps(
            {
                "status": status,
                "kind": args.kind,
                "node_type": args.node_type,
                "identity_properties": info["identity_properties"],
                "binding_properties": info["binding_properties"],
                "properties": info["properties"],
                "profiles": profiles,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status == "observed" else 1


def binding_show(args: argparse.Namespace) -> int:
    root = Path(args.knowledge).expanduser().resolve()
    manifest, payloads = load_knowledge_bundle(root)
    errors = validate_knowledge_bundle(manifest, payloads)
    if errors:
        raise ContractError("知识库无效: " + "; ".join(errors))
    rows = [
        row
        for row in payloads["binding-matrix.json"]["bindings"]
        if (not args.model_type or row["model_type"] == args.model_type)
        and (not args.field_type or row["field_type"] == args.field_type)
        and (not args.control_type or row["control_type"] == args.control_type)
        and (not args.binding_property or row["binding_property"] == args.binding_property)
    ]
    print(json.dumps({"status": "observed" if rows else "unsupported", "count": len(rows), "bindings": rows}, ensure_ascii=False, indent=2))
    return 0 if rows else 1


def operation_show(args: argparse.Namespace) -> int:
    root = Path(args.knowledge).expanduser().resolve()
    manifest, payloads = load_knowledge_bundle(root)
    errors = validate_knowledge_bundle(manifest, payloads)
    if errors:
        raise ContractError("知识库无效: " + "; ".join(errors))
    matrix = payloads["binding-matrix.json"]
    entity_bindings = [
        row
        for row in matrix.get("operation_bindings", [])
        if (not args.model_type or row["model_type"] == args.model_type)
        and (not args.operation_type or row["operation_type"] == args.operation_type)
        and (not args.control_type or row["control_type"] == args.control_type)
    ]
    form_actions = [
        row
        for row in matrix.get("form_action_bindings", [])
        if (not args.model_type or row["model_type"] == args.model_type)
        and (not args.control_type or row["control_type"] == args.control_type)
        and (not args.operation_key or row["operation_key"] == args.operation_key)
    ]
    status = "observed" if entity_bindings or form_actions else "unsupported"
    print(
        json.dumps(
            {
                "status": status,
                "entity_operation_bindings": entity_bindings,
                "standard_form_actions": form_actions,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status == "observed" else 1


def model_show(args: argparse.Namespace) -> int:
    root = Path(args.knowledge).expanduser().resolve()
    manifest, payloads = load_knowledge_bundle(root)
    errors = validate_knowledge_bundle(manifest, payloads)
    if errors:
        raise ContractError("知识库无效: " + "; ".join(errors))
    model = payloads["model-matrix.json"]["models"].get(args.model_type)
    print(json.dumps({"status": "observed" if model else "unsupported", "model_type": args.model_type, "contract": model}, ensure_ascii=False, indent=2))
    return 0 if model else 1


def side_show(args: argparse.Namespace) -> int:
    root = Path(args.knowledge).expanduser().resolve()
    manifest, payloads = load_knowledge_bundle(root)
    errors = validate_knowledge_bundle(manifest, payloads)
    if errors:
        raise ContractError("知识库无效: " + "; ".join(errors))
    contract = payloads["localization-term-contracts.json"]["contracts"].get(args.kind)
    print(json.dumps({"status": "observed" if contract else "unsupported", "kind": args.kind, "contract": contract}, ensure_ascii=False, indent=2))
    return 0 if contract else 1


def mainentity_show(args: argparse.Namespace) -> int:
    root = Path(args.knowledge).expanduser().resolve()
    manifest, payloads = load_knowledge_bundle(root)
    errors = validate_knowledge_bundle(manifest, payloads)
    if errors:
        raise ContractError("知识库无效: " + "; ".join(errors))
    contract = payloads["mainentity-contract.json"]
    model = contract.get("models", {}).get(args.model_type) if args.model_type else None
    status = "observed" if (model or not args.model_type) else "unsupported"
    print(json.dumps({"status": status, "model_type": args.model_type, "columns": contract.get("columns"), "model": model}, ensure_ascii=False, indent=2))
    return 0 if status == "observed" else 1


def check_config(args: argparse.Namespace) -> int:
    path = Path(args.config).expanduser().resolve()
    config = load_config(path)
    _, source = resolve_password(config, path)
    database = config["metadataAnalyzer"]["database"]
    print(json.dumps({"status": "ok", "schema": database.get("schema", "public"), "credential_source": source}, ensure_ascii=False))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="金蝶云苍穹元数据写入知识采集与查询工具")
    sub = root.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check-config")
    check.add_argument("--config", required=True)
    check.set_defaults(func=check_config)

    snap = sub.add_parser("snapshot")
    snap.add_argument("--config", required=True)
    snap.add_argument("--environment", required=True, choices=("dev", "test", "prod"))
    snap.add_argument("--output")
    snap.add_argument("--timeout-seconds", type=int, default=60)
    snap.add_argument("--allow-git-output", action="store_true")
    snap.set_defaults(func=snapshot)

    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("snapshot")
    verify_parser.set_defaults(func=verify)

    materialize_parser = sub.add_parser("materialize-knowledge")
    materialize_parser.add_argument("snapshot")
    materialize_parser.add_argument("--output", required=True)
    materialize_parser.add_argument("--overwrite", action="store_true")
    materialize_parser.set_defaults(func=materialize_knowledge)

    verify_knowledge_parser = sub.add_parser("verify-knowledge")
    verify_knowledge_parser.add_argument("knowledge")
    verify_knowledge_parser.set_defaults(func=verify_knowledge)

    schema_show_parser = sub.add_parser("schema-show")
    schema_show_parser.add_argument("knowledge")
    schema_show_parser.add_argument("--kind", choices=("entity", "form", "control"), required=True)
    schema_show_parser.add_argument("--node-type", required=True)
    schema_show_parser.add_argument("--model-type")
    schema_show_parser.add_argument("--page-model-type")
    schema_show_parser.add_argument("--parent-type")
    schema_show_parser.set_defaults(func=schema_show)

    binding_show_parser = sub.add_parser("binding-show")
    binding_show_parser.add_argument("knowledge")
    binding_show_parser.add_argument("--model-type")
    binding_show_parser.add_argument("--field-type")
    binding_show_parser.add_argument("--control-type")
    binding_show_parser.add_argument("--binding-property")
    binding_show_parser.set_defaults(func=binding_show)

    operation_show_parser = sub.add_parser("operation-show")
    operation_show_parser.add_argument("knowledge")
    operation_show_parser.add_argument("--model-type")
    operation_show_parser.add_argument("--operation-type")
    operation_show_parser.add_argument("--control-type")
    operation_show_parser.add_argument("--operation-key")
    operation_show_parser.set_defaults(func=operation_show)

    model_show_parser = sub.add_parser("model-show")
    model_show_parser.add_argument("knowledge")
    model_show_parser.add_argument("model_type")
    model_show_parser.set_defaults(func=model_show)

    side_show_parser = sub.add_parser("side-show")
    side_show_parser.add_argument("knowledge")
    side_show_parser.add_argument("kind", choices=("entity_l", "form_l", "entity_term", "form_term"))
    side_show_parser.set_defaults(func=side_show)

    mainentity_show_parser = sub.add_parser("mainentity-show")
    mainentity_show_parser.add_argument("knowledge")
    mainentity_show_parser.add_argument("--model-type")
    mainentity_show_parser.set_defaults(func=mainentity_show)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("snapshot")
    list_parser.add_argument("--kind", choices=("entity", "form"))
    list_parser.add_argument("--scope", choices=("template", "ancestor_context"), default="template")
    list_parser.add_argument("--model-type")
    list_parser.add_argument("--query")
    list_parser.add_argument("--limit", type=int)
    list_parser.set_defaults(func=list_records)

    controls_parser = sub.add_parser("controls")
    controls_parser.add_argument("snapshot")
    controls_parser.add_argument("--host-model-type")
    controls_parser.add_argument("--page-model-type")
    controls_parser.add_argument("--parent-type")
    controls_parser.add_argument("--family")
    controls_parser.add_argument("--query")
    controls_parser.add_argument("--usable-for-new", action="store_true")
    controls_parser.add_argument("--limit", type=int)
    controls_parser.set_defaults(func=control_types)

    control_show_parser = sub.add_parser("control-show")
    control_show_parser.add_argument("snapshot")
    control_show_parser.add_argument("control_type")
    control_show_parser.add_argument("--host-model-type")
    control_show_parser.add_argument("--page-model-type")
    control_show_parser.add_argument("--parent-type")
    control_show_parser.set_defaults(func=control_show)

    model_diff_parser = sub.add_parser("control-model-diff")
    model_diff_parser.add_argument("snapshot")
    model_diff_parser.add_argument("--left-model-type", required=True)
    model_diff_parser.add_argument("--right-model-type", required=True)
    model_diff_parser.set_defaults(func=control_model_diff)

    show_parser = sub.add_parser("show")
    show_parser.add_argument("snapshot")
    show_parser.add_argument("number")
    show_parser.add_argument("--kind", choices=("entity", "form"))
    show_parser.set_defaults(func=show)

    lineage_parser = sub.add_parser("lineage")
    lineage_parser.add_argument("snapshot")
    lineage_parser.add_argument("number")
    lineage_parser.add_argument("--kind", choices=("entity", "form"), required=True)
    lineage_parser.set_defaults(func=lineage)

    extract_parser = sub.add_parser("extract")
    extract_parser.add_argument("snapshot")
    extract_parser.add_argument("number")
    extract_parser.add_argument("--kind", choices=("entity", "form"), required=True)
    extract_parser.add_argument("--output", required=True)
    extract_parser.add_argument("--overwrite", action="store_true")
    extract_parser.set_defaults(func=extract)

    diff_parser = sub.add_parser("diff")
    diff_parser.add_argument("left")
    diff_parser.add_argument("right")
    diff_parser.set_defaults(func=diff)

    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.func(args)
    except ContractError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("[ERROR] 已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
