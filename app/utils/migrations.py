import logging
import os
import sys

from sqlalchemy import text

logger = logging.getLogger(__name__)

ADVISORY_LOCK_KEY = 9142026


def _get_head_revision() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    ini_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "alembic.ini")
    cfg = Config(ini_path)
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    return head or "unknown"


def _get_current_revision(engine) -> str:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = result.fetchone()
            return row[0] if row else "none"
    except Exception:
        return "unknown"


def get_migration_state(engine) -> dict:
    current = _get_current_revision(engine)
    head = _get_head_revision()
    return {
        "current_revision": current,
        "head_revision": head,
        "migration_pending": current != head,
    }


def run_migrations_if_enabled(engine) -> None:
    from ..config import get_settings

    settings = get_settings()
    enabled = settings.run_migrations_on_startup.lower() == "true"

    if not enabled:
        logger.info("RUN_MIGRATIONS_ON_STARTUP is not enabled; skipping auto-migration")
        return

    logger.info("RUN_MIGRATIONS_ON_STARTUP is enabled; acquiring advisory lock %d", ADVISORY_LOCK_KEY)
    print(f"[startup] Acquiring advisory lock {ADVISORY_LOCK_KEY} for migrations...")

    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        cursor.execute("SELECT pg_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
        logger.info("Advisory lock acquired; running alembic upgrade head")
        print("[startup] Advisory lock acquired; running alembic upgrade head...")

        from alembic.config import Config
        from alembic import command

        ini_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "alembic.ini")
        cfg = Config(ini_path)
        cfg.set_main_option("sqlalchemy.url", str(engine.url))

        command.upgrade(cfg, "head")

        logger.info("Migrations complete")
        print("[startup] Migrations complete")

        cursor.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))
        logger.info("Advisory lock released")
    except Exception as exc:
        logger.error("Migration failed: %s", exc)
        print(f"[startup] MIGRATION FAILED: {exc}")
        try:
            cursor = raw_conn.cursor()
            cursor.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))
        except Exception:
            pass
        raw_conn.close()
        sys.exit(1)
    finally:
        raw_conn.close()
