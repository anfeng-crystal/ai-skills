"""Read-only PostgreSQL resolution from Cosmic entity metadata to business tables."""

import importlib.util
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path

from db_connection import connect_with_retry


class RoutingError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def clean(value):
    return "" if value is None else str(value).strip()


def route_items(value):
    """Management routes may be a scalar, comma list, or JSON array."""
    if isinstance(value, list):
        return {clean(v) for v in value if clean(v)}
    raw = clean(value)
    if not raw:
        return set()
    if raw.startswith(("[", '"')):
        try:
            parsed = json.loads(raw)
        except ValueError:
            raise RoutingError("invalid_route_list") from None
        if not isinstance(parsed, (str, list)):
            raise RoutingError("invalid_route_list")
        if isinstance(parsed, str):
            return {parsed.strip()} if parsed.strip() else set()
        return route_items(parsed)
    return {v.strip() for v in raw.split(",") if v.strip()}


def configured_center(project_root, environment, explicit=None, login_config=None):
    """Find the existing environment-specific login config, including submodules."""
    paths = []
    if login_config:
        paths = [Path(login_config)]
        if not paths[0].is_file():
            raise RoutingError("login_config_not_found")
    else:
        ignored = {".git", ".gradle", ".venv", "node_modules", "build", "filestorage"}
        filename = "login-" + environment + ".properties"
        for base, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in ignored]
            if filename in files:
                paths.append(Path(base) / filename)
    ids = set()
    for path in paths:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r"^\s*accountId\s*[:=]\s*(.*?)\s*$", line)
            if match and clean(match[1]):
                ids.add(clean(match[1]))
    if clean(explicit):
        return clean(explicit), "argument", (clean(explicit) in ids if ids else None)
    if len(ids) > 1:
        raise RoutingError("data_center_config_ambiguous")
    return (next(iter(ids)), "login_config", True) if ids else (None, "metadata_mapping", None)


def select_center(candidates, requested):
    candidates = {clean(v) for v in candidates}
    if requested:
        if requested not in candidates:
            raise RoutingError("data_center_metadata_mismatch")
        return requested
    if len(candidates) != 1:
        raise RoutingError("data_center_required" if candidates else "data_center_not_found")
    return next(iter(candidates))


def select_schema(schemas, configured, current):
    """Whitespace-only fdbschema is an unset value, not a schema conflict."""
    schemas = set(schemas)
    registered = clean(configured)
    if registered in schemas:
        chosen = registered
    elif len(schemas) == 1:
        chosen = next(iter(schemas))
    else:
        raise RoutingError("table_schema_ambiguous" if schemas else "table_not_found")
    return chosen, bool(registered and registered != chosen), chosen == current


def entity_mapping(number, fetch, parse):
    """Resolve only the root entity's table/route, inheriting missing values."""
    route = table = ""
    seen = set()
    key, by_id = number, False
    for _ in range(32):
        rows = fetch(key, by_id)
        if len(rows) != 1:
            raise RoutingError("entity_not_unique" if rows else "entity_not_found")
        entity_id, data = rows[0]
        if str(entity_id) in seen:
            raise RoutingError("entity_inheritance_cycle")
        seen.add(str(entity_id))
        fmt, root = parse(data)
        if fmt != "xml" or root is None:
            raise RoutingError("unsupported_entity_format")
        items = root.find("Items")
        nodes = [n for n in items if n.tag in ("BaseEntity", "BillEntity", "DynamicEntity")] if items is not None else []
        if len(nodes) > 1:
            raise RoutingError("entity_root_ambiguous")
        if nodes:
            node = nodes[0]
            if node.get("action") in ("delete", "remove"):
                raise RoutingError("entity_mapping_removed")
            route = route or clean(node.findtext("dbRoute"))
            table = table or clean(node.findtext("TableName"))
        if route and table:
            return {"entity": number, "route": route, "table": table}
        key, by_id = clean(root.findtext("ParentId")), True
        if not key:
            raise RoutingError("entity_mapping_incomplete")
    raise RoutingError("entity_inheritance_limit")


class Reader:
    def __init__(self, database, password, timeout):
        self.database = database
        self.password = password
        self.timeout = timeout
        self.connections = 0
        self.statements = 0

    @contextmanager
    def connect(self, name):
        import psycopg2
        db = self.database
        conn = connect_with_retry(psycopg2.connect, {
            "host": db["host"], "port": db.get("port", 5432), "dbname": name,
            "user": db["user"], "password": self.password,
            "connect_timeout": min(int(db.get("connectTimeoutSeconds", 10)), self.timeout),
            "options": "-c default_transaction_read_only=on -c statement_timeout=" + str(self.timeout * 1000),
        })
        self.connections += 1
        try:
            conn.set_session(readonly=True)
            with conn.cursor() as cursor:
                yield cursor
        finally:
            try:
                conn.rollback()
            finally:
                conn.close()

    def query(self, cursor, sql, parameters=()):
        self.statements += 1
        cursor.execute(sql, parameters)
        return cursor.fetchall()


def management_rows(reader, candidates, metadata_db, requested):
    from psycopg2 import sql
    matches = []
    for database in candidates:
        with reader.connect(database) as cursor:
            schemas = reader.query(cursor, """SELECT table_schema FROM information_schema.tables
                WHERE table_name='t_mc_dbsource' AND table_schema NOT IN ('pg_catalog','information_schema')""")
            for (schema,) in schemas:
                columns = {r[0] for r in reader.query(cursor, """SELECT column_name FROM information_schema.columns
                    WHERE table_schema=%s AND table_name='t_mc_dbsource'""", (schema,))}
                if not {"fdatacenterid", "fdbid", "fdbinstance", "fdbschema"}.issubset(columns):
                    continue
                source = sql.Identifier(schema, "t_mc_dbsource")
                centers = reader.query(cursor, sql.SQL("SELECT DISTINCT fdatacenterid::text FROM {} WHERE fdbinstance=%s").format(source), (metadata_db,))
                if not centers or (requested and requested not in {clean(r[0]) for r in centers}):
                    continue
                selected = select_center([r[0] for r in centers], requested)
                rows = reader.query(cursor, sql.SQL("SELECT fdbid, fdbinstance, fdbschema FROM {} WHERE fdatacenterid::text=%s").format(source), (selected,))
                matches.append((selected, rows))
    if len(matches) != 1:
        raise RoutingError("management_mapping_ambiguous" if matches else "management_mapping_not_found")
    return matches[0]


def verify_tables(reader, mappings, routes):
    from psycopg2 import sql
    groups = {}
    for mapping in mappings:
        locations = {(clean(row[1]), clean(row[2])) for row in routes if mapping["route"] in route_items(row[0])}
        if len(locations) != 1:
            raise RoutingError("route_ambiguous" if locations else "route_not_found")
        database, schema = next(iter(locations))
        if not database:
            raise RoutingError("route_database_empty")
        groups.setdefault(database, []).append((mapping, schema))
    results = []
    for database, entries in groups.items():
        with reader.connect(database) as cursor:
            actual_db, current, readonly = reader.query(cursor, "SELECT current_database(), current_schema(), current_setting('transaction_read_only')")[0]
            if actual_db != database or readonly != "on":
                raise RoutingError("connection_verification_failed")
            tables = list({m["table"] for m, _ in entries})
            columns = reader.query(cursor, """SELECT table_schema, table_name, count(*)
                FROM information_schema.columns WHERE table_name=ANY(%s)
                AND table_schema NOT IN ('pg_catalog','information_schema') GROUP BY table_schema,table_name""", (tables,))
            for mapping, configured in entries:
                counts = {s: n for s, t, n in columns if t == mapping["table"]}
                schema, mismatch, is_current = select_schema(counts, configured, current)
                found = reader.query(cursor, sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier(schema, mapping["table"])))
                results.append(dict(mapping, database=database, schema=schema,
                    schema_setting="explicit" if configured else "unset",
                    schema_mismatch=mismatch, current_schema=is_current,
                    columns=counts[schema], query_ok=True, row_exists=bool(found)))
    return results


def resolve(config_path, environment, entities, datacenter=None, login_config=None,
            management_db=None, timeout=10):
    path = Path(config_path).expanduser().resolve()
    spec = importlib.util.spec_from_file_location("cosmic_analyzer", Path(__file__).with_name("cosmic-metadata-analyzer.py"))
    analyzer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyzer)
    config = analyzer.load_json(path)
    metadata = analyzer.analyzer_config(config)
    database = metadata.get("database", {})
    if not metadata.get("enabled", False):
        raise RoutingError("metadata_disabled")
    if not all(clean(database.get(k)) for k in ("host", "dbname", "user")):
        raise RoutingError("database_config_incomplete")
    config_environment = analyzer.config_environment_label(path)
    if config_environment in ("dev", "test", "prod") and config_environment != environment:
        raise RoutingError("config_environment_mismatch")
    password, credential_source = analyzer.resolve_database_password(config, path)
    if not password:
        raise RoutingError("credential_unavailable")
    center, source, config_match = configured_center(analyzer.project_root(config, path), environment, datacenter, login_config)
    reader = Reader(database, password, timeout)
    from psycopg2 import sql
    with reader.connect(database["dbname"]) as cursor:
        entity_table = sql.Identifier(clean(database.get("schema")) or "public", "t_meta_entitydesign")
        cache = {}
        def fetch(key, by_id):
            cache_key = (key, by_id)
            if cache_key not in cache:
                column = sql.SQL("fid::text") if by_id else sql.Identifier("fnumber")
                cache[cache_key] = reader.query(cursor, sql.SQL("SELECT fid, fdata FROM {} WHERE {}=%s LIMIT 2").format(entity_table, column), (key,))
            return cache[cache_key]
        mappings = [entity_mapping(entity, fetch, analyzer.parse_fdata) for entity in dict.fromkeys(entities)]
        catalog = reader.query(cursor, "SELECT datname FROM pg_database WHERE datallowconn AND NOT datistemplate AND has_database_privilege(oid,'CONNECT')")
    candidates = [management_db] if management_db else [r[0] for r in catalog if "mc" in r[0].lower() or "manage" in r[0].lower()]
    if not candidates:
        raise RoutingError("management_database_required")
    center, rows = management_rows(reader, candidates, database["dbname"], center)
    results = verify_tables(reader, mappings, rows)
    return {"status": "verified", "environment": environment,
        "datacenter": center, "datacenter_source": source,
        "login_config_matches": config_match, "credential_source": credential_source,
        "results": results, "connections": reader.connections, "statements": reader.statements}
