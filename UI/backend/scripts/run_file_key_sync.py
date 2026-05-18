from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple
import re

import psycopg2
from minio import Minio
import urllib3

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"


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


def fill_storage_path(
    conn,
    object_names: List[str],
    allow_fallback: bool,
    dry_run: bool,
) -> Tuple[int, int, List[Tuple[str, str]]]:
    if not object_names:
        return 0, 0, []

    cur = conn.cursor()
    updates = 0
    fallback_updates = 0
    unmatched: List[Tuple[str, str]] = []
    try:
        cur.execute(
            "SELECT file_uuid, original_name FROM core_file "
            "WHERE storage_path IS NULL OR btrim(storage_path) = ''"
        )
        rows = cur.fetchall() or []

        basename_map = {Path(obj).name: obj for obj in object_names}

        for row in rows:
            file_uuid, original_name = row
            file_name = str(original_name or "").strip()
            if not file_name:
                unmatched.append((str(file_uuid), str(original_name or "")))
                continue
            if file_name in basename_map:
                if not dry_run:
                    cur.execute(
                        "UPDATE core_file SET storage_path=%s WHERE file_uuid=%s",
                        (basename_map[file_name], file_uuid),
                    )
                updates += 1
            else:
                unmatched.append((str(file_uuid), str(original_name or "")))

        if allow_fallback and not dry_run and updates == 0 and rows:
            sample_rows = rows[: min(50, len(object_names))]
            for idx, (file_uuid, _) in enumerate(sample_rows):
                object_name = object_names[idx % len(object_names)]
                cur.execute(
                    "UPDATE core_file SET storage_path=%s WHERE file_uuid=%s",
                    (object_name, file_uuid),
                )
                fallback_updates += 1

        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    finally:
        cur.close()

    return updates, fallback_updates, unmatched


def write_unmatched_list(unmatched: List[Tuple[str, str]], output_path: Path) -> None:
    if not unmatched:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file_uuid", "original_name"])
        writer.writerows(unmatched)


def sync_lit_metadata_storage(conn) -> int:
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE lit_metadata lm "
            "SET storage_path = cf.storage_path "
            "FROM core_file cf "
            "WHERE lm.file_uuid = cf.file_uuid "
            "AND (lm.storage_path IS NULL OR btrim(lm.storage_path) = '') "
            "AND cf.storage_path IS NOT NULL AND btrim(cf.storage_path) <> ''"
        )
        updated = cur.rowcount
        conn.commit()
        return updated
    finally:
        cur.close()


def report_db_status(conn) -> None:
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM core_file WHERE storage_path IS NULL OR btrim(storage_path) = ''")
        missing_core = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM lit_metadata WHERE storage_path IS NULL OR btrim(storage_path) = ''")
        missing_lit = cur.fetchone()[0]
        print(f"[DB] core_file_missing_storage_path={missing_core}, lit_metadata_missing_storage_path={missing_lit}")
    finally:
        cur.close()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync core_file storage_path from MinIO object list")
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Enable legacy fallback mapping when no filename matches (unsafe, default off)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute matches but do not write any database updates",
    )
    parser.add_argument(
        "--unmatched-out",
        default=str(ROOT / "storage_path_unmatched.csv"),
        help="Path to write unmatched file_uuid/original_name list",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    env = parse_env()

    db_host = env.get("DB_HOST") or env.get("POSTGRES_HOST", "127.0.0.1")
    db_port = int(env.get("DB_PORT") or env.get("POSTGRES_PORT", "5432"))
    db_user = env.get("DB_USER") or env.get("POSTGRES_USER", "postgres")
    db_password = env.get("DB_PASSWORD") or env.get("POSTGRES_PASSWORD", "")
    db_name = env.get("DB_NAME") or env.get("POSTGRES_DB", "postgres")

    print(f"[INFO] connecting postgres: {db_host}:{db_port}/{db_name}")
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        dbname=db_name,
    )

    try:
        object_names = fetch_minio_objects(env)
        matched, fallback, unmatched = fill_storage_path(
            conn,
            object_names,
            allow_fallback=args.allow_fallback,
            dry_run=args.dry_run,
        )
        print(
            f"[INFO] storage_path updates: matched={matched}, fallback={fallback}, "
            f"dry_run={args.dry_run}"
        )
        if unmatched:
            unmatched_path = Path(args.unmatched_out)
            write_unmatched_list(unmatched, unmatched_path)
            print(f"[WARN] unmatched storage_path rows: {len(unmatched)} -> {unmatched_path}")
        else:
            print("[INFO] unmatched storage_path rows: 0")

        if args.dry_run:
            print("[INFO] dry-run enabled: skip lit_metadata storage_path sync")
        else:
            synced = sync_lit_metadata_storage(conn)
            print(f"[INFO] lit_metadata storage_path synced: {synced}")

        report_db_status(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
