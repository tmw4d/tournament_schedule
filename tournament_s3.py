"""Timestamped S3 backups of the tournament SQLite database."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import os

import database

LOCAL_BACKUP_DIR = database.BASE_DIR / "data" / "backups"


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
        "db_key": secrets.get("TOURNAMENT_S3_DB_KEY", "tournament_schedule/tournament.db"),
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


def _integrity_ok(path):
    with closing(sqlite3.connect(path)) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()
    return bool(result and result[0] == "ok")


def _seed_local_database():
    """Copy the tracked database once when no S3 primary database exists yet."""
    if database.DB_PATH.exists() or not database.SEED_DB_PATH.exists():
        return False
    database.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database.SEED_DB_PATH)) as source, closing(sqlite3.connect(database.DB_PATH)) as target:
        source.backup(target)
    return True


def _remote_primary_exists(config):
    try:
        _s3_client(config).head_object(Bucket=config["bucket"], Key=config["db_key"])
        return True
    except Exception as exc:
        response = getattr(exc, "response", {})
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        code = str(error.get("Code", ""))
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode") if isinstance(response, dict) else None
        if code in ("404", "NoSuchKey", "NotFound") or status == 404:
            return False
        raise S3BackupError(f"Could not check the primary S3 database: {exc}") from exc


def initialize_primary_database(secrets):
    """Load the S3 primary database once at process startup, or seed local data."""
    database.DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        config = get_config(secrets)
    except Exception as error:
        exc = error if isinstance(error, S3BackupError) else S3BackupError("Streamlit secrets are unavailable.")
        seeded = _seed_local_database()
        return {"source": "local", "remote_exists": None, "message": f"S3 database sync is not configured ({exc})." + (" Loaded the repository database as a local seed." if seeded else "")}

    try:
        if not _remote_primary_exists(config):
            seeded = _seed_local_database()
            local_note = (
                " Loaded the repository database as a seed; upload it to S3 to make it persistent."
                if seeded else " Using the existing local database."
                if database.DB_PATH.exists() else " No local database is available."
            )
            return {"source": "local", "remote_exists": False, "message": "No primary tournament database was found in S3." + local_note}

        handle = tempfile.NamedTemporaryFile(
            prefix="tournament-primary-", suffix=".db", dir=database.DATA_DIR, delete=False
        )
        downloaded_path = Path(handle.name)
        handle.close()
        try:
            try:
                _s3_client(config).download_file(config["bucket"], config["db_key"], str(downloaded_path))
            except Exception as exc:
                raise S3BackupError(f"Could not download the primary S3 database: {exc}") from exc
            if not _integrity_ok(downloaded_path):
                raise S3BackupError("The primary S3 database failed its SQLite integrity check.")
            os.replace(downloaded_path, database.DB_PATH)
        finally:
            downloaded_path.unlink(missing_ok=True)
        return {"source": "s3", "remote_exists": True, "message": f"Loaded the primary database from s3://{config['bucket']}/{config['db_key']}."}
    except Exception as error:
        exc = error if isinstance(error, S3BackupError) else S3BackupError(f"Could not load primary S3 database: {error}")
        seeded = _seed_local_database()
        return {"source": "local", "remote_exists": None, "message": f"S3 database could not be loaded ({exc})." + (" Using the local database." if database.DB_PATH.exists() else (" Loaded the repository database as a seed." if seeded else " No local database is available."))}


def primary_database_exists(config):
    """Check whether the durable primary database object is present in S3."""
    return _remote_primary_exists(config)


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


def upload_primary_database(config):
    """Save the current local database as the durable S3 primary copy."""
    snapshot_path = _create_snapshot()
    previous_backup_key = None
    try:
        s3 = _s3_client(config)
        if _remote_primary_exists(config):
            handle = tempfile.NamedTemporaryFile(prefix="tournament-previous-primary-", suffix=".db", delete=False)
            previous_path = Path(handle.name)
            handle.close()
            try:
                s3.download_file(config["bucket"], config["db_key"], str(previous_path))
                if not _integrity_ok(previous_path):
                    raise S3BackupError("The current S3 database failed integrity validation; upload cancelled.")
                prefix = config["prefix"].strip("/")
                previous_backup_key = f"{prefix + '/' if prefix else ''}tournament-before-sync-{_timestamp()}.db"
                s3.upload_file(str(previous_path), config["bucket"], previous_backup_key)
            finally:
                previous_path.unlink(missing_ok=True)
        s3.upload_file(str(snapshot_path), config["bucket"], config["db_key"])
    except S3BackupError:
        raise
    except Exception as exc:
        raise S3BackupError(f"Could not save the primary database to S3: {exc}") from exc
    finally:
        snapshot_path.unlink(missing_ok=True)
    return previous_backup_key


def restore_from_s3(config, key, destination_connection):
    """Restore a listed backup, retaining a local snapshot for recovery."""
    prefix = config["prefix"].strip("/")
    allowed_prefix = f"{prefix}/" if prefix else ""
    if (key != config["db_key"] and not key.startswith(allowed_prefix)) or not key.lower().endswith(".db"):
        raise S3BackupError("Select a tournament database backup from the configured backup prefix.")

    LOCAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    local_backup_path = LOCAL_BACKUP_DIR / f"tournament-before-restore-{_timestamp()}.db"
    with closing(sqlite3.connect(local_backup_path)) as local_backup:
        destination_connection.backup(local_backup)
        result = local_backup.execute("PRAGMA integrity_check").fetchone()
    if not result or result[0] != "ok":
        local_backup_path.unlink(missing_ok=True)
        raise S3BackupError("Could not create a valid local backup before restore.")

    handle = tempfile.NamedTemporaryFile(prefix="tournament-restore-", suffix=".db", delete=False)
    downloaded_path = Path(handle.name)
    handle.close()
    try:
        try:
            _s3_client(config).download_file(config["bucket"], key, str(downloaded_path))
        except Exception as exc:
            raise S3BackupError(f"Could not download the selected S3 backup: {exc}") from exc

        with closing(sqlite3.connect(downloaded_path)) as downloaded:
            result = downloaded.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise S3BackupError("The selected S3 backup failed its SQLite integrity check. Current data was not changed.")

        try:
            with closing(sqlite3.connect(downloaded_path)) as downloaded:
                downloaded.backup(destination_connection)
            integrity = destination_connection.execute("PRAGMA integrity_check").fetchone()
            foreign_key_issues = destination_connection.execute("PRAGMA foreign_key_check").fetchall()
            if not integrity or integrity[0] != "ok" or foreign_key_issues:
                raise S3BackupError("Restored database validation failed.")
        except Exception as exc:
            with closing(sqlite3.connect(local_backup_path)) as local_backup:
                local_backup.backup(destination_connection)
            if isinstance(exc, S3BackupError):
                raise S3BackupError(f"Restore was rolled back to the local backup: {exc}") from exc
            raise S3BackupError(f"Restore failed and was rolled back to the local backup: {exc}") from exc
        return local_backup_path
    finally:
        downloaded_path.unlink(missing_ok=True)
