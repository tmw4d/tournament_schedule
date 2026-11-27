"""Timestamped S3 backups of the tournament SQLite database."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile

import database


class S3BackupError(Exception):
    """Raised when backup configuration or upload fails."""


def get_config(secrets):
    required = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION", "S3_BUCKET")
    missing = [key for key in required if not secrets.get(key)]
    if missing:
        raise S3BackupError(f"Missing Streamlit secrets: {', '.join(missing)}")
    return {
        "aws_access_key_id": secrets["AWS_ACCESS_KEY_ID"],
        "aws_secret_access_key": secrets["AWS_SECRET_ACCESS_KEY"],
        "region_name": secrets["AWS_DEFAULT_REGION"],
        "bucket": secrets["S3_BUCKET"],
        "prefix": secrets.get("TOURNAMENT_S3_BACKUP_PREFIX", "tournament_schedule/backups/"),
    }


def _s3_client(config):
    try:
        import boto3
    except ImportError as exc:
        raise S3BackupError("boto3 is required for S3 backups. Install dependencies from requirements.txt.") from exc
    return boto3.client(
        "s3",
        aws_access_key_id=config["aws_access_key_id"],
        aws_secret_access_key=config["aws_secret_access_key"],
        region_name=config["region_name"],
    )


def _timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def list_backups(config, limit=20):
    """Return recent backup metadata without downloading backup contents."""
    s3 = _s3_client(config)
    prefix = config["prefix"].strip("/") + "/"
    try:
        objects = []
        for page in s3.get_paginator("list_objects_v2").paginate(
            Bucket=config["bucket"], Prefix=prefix
        ):
            objects.extend(page.get("Contents", []))
    except Exception as exc:
        raise S3BackupError(f"Could not list S3 backups: {exc}") from exc
    return sorted(objects, key=lambda item: item.get("LastModified", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)[:limit]


def _create_snapshot():
    database_path = Path(database.DB_PATH)
    if not database_path.exists():
        raise S3BackupError("Local tournament database does not exist.")

    handle = tempfile.NamedTemporaryFile(prefix="tournament-backup-", suffix=".db", delete=False)
    snapshot_path = Path(handle.name)
    handle.close()
    try:
        with closing(sqlite3.connect(database_path)) as source, closing(sqlite3.connect(snapshot_path)) as snapshot:
            source.backup(snapshot)
            result = snapshot.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise S3BackupError("Tournament database snapshot failed its SQLite integrity check.")
        return snapshot_path
    except Exception:
        snapshot_path.unlink(missing_ok=True)
        raise


def backup_to_s3(config):
    """Create a consistent local snapshot and upload it under a unique S3 key."""
    snapshot_path = _create_snapshot()
    prefix = config["prefix"].strip("/")
    key = f"{prefix + '/' if prefix else ''}tournament-{_timestamp()}.db"
    try:
        _s3_client(config).upload_file(str(snapshot_path), config["bucket"], key)
    except Exception as exc:
        raise S3BackupError(f"Could not upload tournament backup to S3: {exc}") from exc
    finally:
        snapshot_path.unlink(missing_ok=True)
    return key
