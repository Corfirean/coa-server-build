"""Repack integration for unchanged SQUID Playerbots; never log credentials."""
from pathlib import Path
import hashlib
import json
import os
import re


def options(path):
    result = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r'^\s*([^#=\s]+)\s*=\s*(.*?)\s*(?:#.*)?$', line)
            if match:
                result[match[1]] = match[2].strip('"')
    return result


def package_root(root):
    return root.parent.parent if root.name == "secondary" and root.parent.name == ".realms" else root


def module_options(root, name):
    folder = root / "Core/configs/modules"
    active = folder / name
    path = active if active.exists() else folder / (name + ".dist")
    if not path.exists() and name == "playerbots.conf":
        path = package_root(root) / "Core/configs/modules/playerbots.conf.dist"
    return path, options(path)


def enabled(values, key):
    # Invalid booleans fall back to the modules' compiled default (enabled).
    return values.get(key, "1").lower() not in ("0", "false", "no", "off")


def validate_bots(root):
    a, av = module_options(root, "mod_coa_playerbots.conf")
    b, bv = module_options(root, "playerbots.conf")
    if a.exists() and b.exists() and enabled(av, "CoaBots.Enable") and enabled(bv, "AiPlayerbot.Enabled"):
        raise RuntimeError("CoA Companions and SQUID Playerbots cannot both be enabled. Disable one bot module in Modules or its config.")


def startup_timeout(root):
    path, values = module_options(Path(root), "playerbots.conf")
    return 1500 if path.exists() and enabled(values, "AiPlayerbot.Enabled") else 180


def set_options(path, values):
    text = path.read_text(encoding="utf-8-sig")
    for key, value in values.items():
        pattern = r'(?m)^\s*' + re.escape(key) + r'\s*=.*$'
        line = key + " = " + value
        if re.search(pattern, text):
            text = re.sub(pattern, lambda _: line, text)
        else:
            text += "\n" + line + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def prepare_playerbots(root, config, mysql):
    """Provision enabled SQUID without replaying imported base tables.

    Each target database has its own migration ledger. Completed base imports never
    run again, so existing bot accounts, characters and caches survive restarts.
    """
    root = Path(root)
    path, values = module_options(root, "playerbots.conf")
    if not path.exists() or not enabled(values, "AiPlayerbot.Enabled"):
        return
    validate_bots(root)
    sql_root = package_root(root) / "Extras/SquidPlayerbots/sql"
    if not (sql_root / "playerbots/base").is_dir():
        raise RuntimeError("SQUID Playerbots database files are missing. Repair the server installation.")
    world = options(root / "Core/configs/worldserver.conf")
    schemas = {"playerbots": "acore_playerbots"}
    for kind, key in (("world", "WorldDatabaseInfo"), ("characters", "CharacterDatabaseInfo")):
        schema = world[key].split(";")[-1]
        if not re.fullmatch(r"acore_(?:world|characters)(?:_wildcard)?", schema):
            raise RuntimeError("Unsupported world/characters database for SQUID Playerbots.")
        schemas[kind] = schema
    existing_playerbots = set(mysql("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='acore_playerbots';").splitlines())
    data_tables = existing_playerbots - {"updates", "updates_include", "version_db_playerbots", "coa_squid_migrations", "coa_bots_installed", "coa_squid_pending"}
    installer_history = set()
    if "coa_bots_installed" in existing_playerbots:
        for name in mysql("SELECT file FROM `acore_playerbots`.coa_bots_installed;").splitlines():
            normalized = re.sub(r"/+", "/", name.replace("\\", "/")).strip("/")
            if normalized.lower().endswith(".sql"):
                installer_history.add(normalized)
    histories, ledgers, tables = {}, {}, {}
    for kind, schema in schemas.items():
        tables[kind] = existing_playerbots if kind == "playerbots" else set(mysql(f"SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='{schema}';").splitlines())
        if "coa_squid_pending" in tables[kind]:
            pending = mysql(f"SELECT path FROM `{schema}`.coa_squid_pending;").strip()
            if pending:
                raise RuntimeError("A SQUID base import was interrupted. Restore the database backup or repair the incomplete import before continuing; no SQL was applied: " + pending)
        history = {}
        if "updates" in tables[kind]:
            for row in mysql(f"SELECT name,hash FROM `{schema}`.updates;").splitlines():
                name, digest = row.split("\t", 1)
                history[name] = digest.lower()
        histories[kind] = history
        ledgers[kind] = {}
        if "coa_squid_migrations" in tables[kind]:
            for row in mysql(f"SELECT path,sha256 FROM `{schema}`.coa_squid_migrations;").splitlines():
                name, digest = row.split("\t", 1)
                ledgers[kind][name] = digest
    if data_tables and not (installer_history or histories["playerbots"] or ledgers["playerbots"]):
        for table in data_tables:
            quoted = table.replace("`", "``")
            if mysql(f"SELECT EXISTS(SELECT 1 FROM `acore_playerbots`.`{quoted}` LIMIT 1);").strip() == "1":
                raise RuntimeError("Existing SQUID data has no recorded installation history. Repair the imported database history before continuing; no SQL was applied.")
    mysql("CREATE DATABASE IF NOT EXISTS acore_playerbots CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    # Use the repack's existing application account; do not create another password.
    for host in ("localhost", "127.0.0.1"):
        mysql(f"GRANT ALL PRIVILEGES ON acore_playerbots.* TO 'acore'@'{host}';")
    credentials = json.loads((root / "Settings/database.json").read_text(encoding="utf-8-sig"))
    password = credentials["appPassword"]
    if not re.fullmatch(r"[a-f0-9]{48}", password):
        raise RuntimeError("Invalid packaged database configuration.")
    if path.name.endswith(".dist"):
        active = root / "Core/configs/modules/playerbots.conf"
        active.parent.mkdir(parents=True, exist_ok=True)
        active.write_bytes(path.read_bytes())
        path = active
    set_options(path, {"PlayerbotsDatabaseInfo": f'"127.0.0.1;{config["mysqlPort"]};acore;{password};acore_playerbots"',
                       "Playerbots.Updates.EnableDatabases": "0"})
    for kind, schema in schemas.items():
        mysql(f"CREATE TABLE IF NOT EXISTS `{schema}`.coa_squid_migrations (path VARCHAR(240) PRIMARY KEY, sha256 CHAR(64) NOT NULL);")
        mysql(f"CREATE TABLE IF NOT EXISTS `{schema}`.coa_squid_pending (path VARCHAR(240) PRIMARY KEY, sha256 CHAR(64) NOT NULL);")
        history = histories[kind]
        recorded = ledgers[kind]
        for stage in ("base", "updates", "custom"):
            for source in sorted((sql_root / kind / stage).glob("*.sql")):
                relative = source.relative_to(sql_root).as_posix()
                if not re.fullmatch(r"[A-Za-z0-9_./-]+", relative):
                    raise RuntimeError("Invalid SQUID SQL filename.")
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                if relative in recorded:
                    if recorded[relative] != digest:
                        raise RuntimeError("A previously applied SQUID database migration changed: " + relative)
                    if stage != "base":
                        continue
                ledger_sql = "" if relative in recorded else f"INSERT INTO `{schema}`.coa_squid_migrations VALUES ('{relative}','{digest}');"
                if stage == "base":
                    definitions = set(re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([A-Za-z0-9_]+)`?", source.read_text(encoding="utf-8-sig"), re.I))
                    present = definitions & tables[kind]
                    if present and present != definitions:
                        raise RuntimeError("SQUID base file has only some of its tables. Repair the incomplete database before continuing: " + relative)
                    if not definitions:
                        raise RuntimeError("SQUID base file has no recognizable table definitions; repair is required: " + relative)
                    if present == definitions:
                        if ledger_sql:
                            mysql(ledger_sql)
                        continue
                    mysql(f"INSERT INTO `{schema}`.coa_squid_pending VALUES ('{relative}','{digest}'); COMMIT;")
                    complete_sql = f"DELETE FROM `{schema}`.coa_squid_pending WHERE path='{relative}' AND sha256='{digest}'; COMMIT;"
                    mysql(f"USE `{schema}`;\n" + source.read_text(encoding="utf-8-sig") + "\n" + ledger_sql + "\n" + complete_sql)
                    tables[kind].update(definitions)
                    continue
                if any(name == relative or name.endswith("/" + relative) for name in installer_history):
                    mysql(ledger_sql)
                    continue
                if source.name in history:
                    upstream_hash = history[source.name]
                    contents = source.read_bytes()
                    upstream_hashes = {hashlib.sha1(contents).hexdigest(), hashlib.sha1(contents.replace(b"\r\n", b"\n")).hexdigest()}
                    if upstream_hash and upstream_hash not in upstream_hashes:
                        raise RuntimeError("SQUID update history does not match the shipped SQL: " + relative)
                    mysql(ledger_sql)
                    continue
                mysql(f"USE `{schema}`;\n" + source.read_text(encoding="utf-8-sig") + "\n" + ledger_sql)
