from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple
import re

import mysql.connector
from mysql.connector import ProgrammingError
from minio import Minio
import urllib3

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"
SQL_FILE = ROOT / "configs" / "sql" / "002_literature_file_key.sql"


def parse_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not ENV_FILE.exists():
        return env

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue

        if s.startswith("$env:") and "=" in s:
            k, v = s[5:].split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
            continue

        if "=" in s:
            k, v = s.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

    return env


def normalize_minio_endpoint(raw: str) -> Tuple[str, bool]:
    endpoint = (raw or "localhost:9000").strip()
    secure = endpoint.startswith("https://")
    endpoint = re.sub(r"^https?://", "", endpoint)
    return endpoint, secure


def execute_sql_script(conn: mysql.connector.MySQLConnection, sql_path: Path) -> None:
    text = sql_path.read_text(encoding="utf-8")
    statements = [s.strip() for s in text.split(";") if s.strip()]
    cur = conn.cursor()
    try:
        for stmt in statements:
            cur.execute(stmt)
            if cur.with_rows:
                cur.fetchall()

            while cur.nextset():
                if cur.with_rows:
                    cur.fetchall()
        conn.commit()
    finally:
        cur.close()


def ensure_schema_compat(conn: mysql.connector.MySQLConnection, db_name: str) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='paper' AND COLUMN_NAME='file_key'",
            (db_name,),
        )
        has_file_key = cur.fetchone()[0] > 0
        if not has_file_key:
            cur.execute("ALTER TABLE paper ADD COLUMN file_key VARCHAR(512) NULL COMMENT 'MinIO object key' AFTER file_name")
        conn.commit()
    finally:
        cur.close()


def fetch_minio_objects(env: Dict[str, str]) -> List[str]:
    endpoint, secure = normalize_minio_endpoint(env.get("MINIO_ENDPOINT", "localhost:9000"))
    access_key = env.get("MINIO_ACCESS_KEY", "") or "minioadmin"
    secret_key = env.get("MINIO_SECRET_KEY", "") or "minioadmin"
    bucket = env.get("MINIO_BUCKET_NAME", "tcm-documents") or "tcm-documents"

    http_client = urllib3.PoolManager(timeout=urllib3.Timeout(connect=2.0, read=4.0), retries=False)
    client = Minio(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
        http_client=http_client,
    )
    try:
        if not client.bucket_exists(bucket):
            print(f"[MinIO] bucket not exists: {bucket}")
            return []

        objs = [obj.object_name for obj in client.list_objects(bucket, recursive=True)]
        print(f"[MinIO] bucket={bucket}, objects={len(objs)}")
        return objs
    except Exception as exc:
        print(f"[MinIO] connection failed: {exc}")
        return []


def fill_file_key(conn: mysql.connector.MySQLConnection, object_names: List[str]) -> Tuple[int, int]:
    if not object_names:
        return 0, 0

    cur = conn.cursor(dictionary=True)
    updates = 0
    fallback_updates = 0
    try:
        cur.execute("SELECT file_name FROM paper WHERE file_key IS NULL OR TRIM(file_key) = ''")
        rows = cur.fetchall() or []

        basename_map = {Path(obj).name: obj for obj in object_names}

        for row in rows:
            file_name = str(row.get("file_name") or "").strip()
            if not file_name:
                continue
            if file_name in basename_map:
                cur.execute("UPDATE paper SET file_key=%s WHERE file_name=%s", (basename_map[file_name], file_name))
                updates += 1

        if updates == 0:
            cur.execute(
                "SELECT file_name FROM paper WHERE file_key IS NULL OR TRIM(file_key) = '' ORDER BY file_name LIMIT %s",
                (min(50, len(object_names)),),
            )
            rows2 = cur.fetchall() or []
            for idx, row in enumerate(rows2):
                file_name = str(row.get("file_name") or "").strip()
                if not file_name:
                    continue
                object_name = object_names[idx % len(object_names)]
                cur.execute("UPDATE paper SET file_key=%s WHERE file_name=%s", (object_name, file_name))
                fallback_updates += 1

        conn.commit()
    finally:
        cur.close()

    return updates, fallback_updates


def report_db_status(conn: mysql.connector.MySQLConnection, db_name: str) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='paper' AND COLUMN_NAME='file_key'",
            (db_name,),
        )
        has_fk = cur.fetchone()[0]
        filled = 0
        if has_fk:
            cur.execute("SELECT COUNT(*) FROM paper WHERE file_key IS NOT NULL AND TRIM(file_key) <> ''")
            filled = cur.fetchone()[0]
        print(f"[DB] has_file_key_col={has_fk}, file_key_filled_rows={filled}")
    finally:
        cur.close()


def main() -> None:
    env = parse_env()

    db_host = env.get("DB_HOST", "127.0.0.1")
    db_port = int(env.get("DB_PORT", "3306"))
    db_user = env.get("DB_USER", "root")
    db_password = env.get("DB_PASSWORD", "123456")
    db_name = env.get("DB_NAME", "papers_records")

    print(f"[INFO] connecting mysql: {db_host}:{db_port}/{db_name}")
    conn = mysql.connector.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name,
        charset="utf8mb4",
        use_unicode=True,
    )

    try:
        if SQL_FILE.exists():
            try:
                execute_sql_script(conn, SQL_FILE)
                print(f"[INFO] executed SQL migration: {SQL_FILE}")
            except ProgrammingError as exc:
                if exc.errno == 1064:
                    print("[WARN] SQL migration syntax not supported by current MySQL; fallback to compatibility migration")
                    ensure_schema_compat(conn, db_name)
                else:
                    raise
        else:
            print(f"[WARN] SQL file missing: {SQL_FILE}")

        object_names = fetch_minio_objects(env)
        matched, fallback = fill_file_key(conn, object_names)
        print(f"[INFO] file_key updates: matched={matched}, fallback={fallback}")

        report_db_status(conn, db_name)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
