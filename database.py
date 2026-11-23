import sqlite3
from contextlib import closing
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tournament.db"
SCHEMA_PATH = BASE_DIR / "database_setup.sql"
GAME_MIGRATION_PATH = BASE_DIR / "migrations" / "002_game_side_sources.sql"
DERIVED_MODEL_MIGRATION_PATH = BASE_DIR / "migrations" / "003_derived_game_and_pool_views.sql"
POOL_SLOTS_MIGRATION_PATH = BASE_DIR / "migrations" / "004_pool_slots_and_tournaments.sql"
VENUE_FIELDS_MIGRATION_PATH = BASE_DIR / "migrations" / "005_venue_fields.sql"
TEAM_PAYMENT_MIGRATION_PATH = BASE_DIR / "migrations" / "006_team_location_and_payment.sql"
DIVISION_SCHEDULE_MIGRATION_PATH = BASE_DIR / "migrations" / "007_division_schedule_metadata.sql"


def init_db():
    """Create the current schema and migrate legacy pool and match fields."""
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        conn.execute("PRAGMA foreign_keys = ON")
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "matches" in tables and "games" not in tables:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.executescript(DERIVED_MODEL_MIGRATION_PATH.read_text(encoding="utf-8"))
            conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        division_columns = {row[1] for row in conn.execute("PRAGMA table_info(divisions)")}
        pool_columns = {row[1] for row in conn.execute("PRAGMA table_info(pools)")}
        member_columns = {row[1] for row in conn.execute("PRAGMA table_info(pool_members)")}
        if "tournament" not in division_columns or "num_members" not in pool_columns or "pool_member_id" not in member_columns:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.executescript(POOL_SLOTS_MIGRATION_PATH.read_text(encoding="utf-8"))
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        game_columns = {row[1] for row in conn.execute("PRAGMA table_info(games)")}
        if "field_id" not in game_columns:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.executescript(VENUE_FIELDS_MIGRATION_PATH.read_text(encoding="utf-8"))
            conn.execute("PRAGMA foreign_keys = ON")

        team_columns = {row[1] for row in conn.execute("PRAGMA table_info(teams)")}
        if "payment_received_date" not in team_columns:
            conn.executescript(TEAM_PAYMENT_MIGRATION_PATH.read_text(encoding="utf-8"))

        division_columns = {row[1] for row in conn.execute("PRAGMA table_info(divisions)")}
        division_schedule_columns = {
            "description", "pool_game_length_minutes", "playoff_game_length_minutes"
        }
        if not division_schedule_columns.issubset(division_columns):
            migration_sql = DIVISION_SCHEDULE_MIGRATION_PATH.read_text(encoding="utf-8")
            for statement in migration_sql.split(";"):
                statement = statement.strip()
                if statement:
                    column = statement.split("ADD COLUMN", 1)[1].split()[0]
                    if column not in division_columns:
                        conn.execute(statement)
                        division_columns.add(column)

        team_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(teams)").fetchall()
        }
        if "pool_identifier" in team_columns:
            legacy_assignments = conn.execute(
                """
                SELECT team_id, division_id, TRIM(pool_identifier)
                FROM teams
                WHERE pool_identifier IS NOT NULL AND TRIM(pool_identifier) != ''
                """
            ).fetchall()

            for team_id, division_id, pool_name in legacy_assignments:
                if division_id is None:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO pools (division_id, name) VALUES (?, ?)",
                    (division_id, pool_name),
                )
                pool = conn.execute(
                    "SELECT pool_id FROM pools WHERE division_id = ? AND name = ?",
                    (division_id, pool_name),
                ).fetchone()
                position = conn.execute(
                    "SELECT COALESCE(MAX(position), 0) + 1 FROM pool_members WHERE pool_id = ?",
                    (pool[0],),
                ).fetchone()[0]
                conn.execute(
                    """INSERT OR IGNORE INTO pool_members
                       (pool_id, team_id, division_id, position) VALUES (?, ?, ?, ?)""",
                    (pool[0], team_id, division_id, position),
                )

            conn.execute("ALTER TABLE teams DROP COLUMN pool_identifier")

        foreign_key_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_issues:
            raise sqlite3.IntegrityError(
                f"Database migration left foreign key issues: {foreign_key_issues}"
            )
