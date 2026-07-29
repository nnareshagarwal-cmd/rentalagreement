"""
database.py — Production-Ready PostgreSQL Layer with Connection Pooling
=======================================================================
Uses psycopg2 ThreadedConnectionPool so a fixed number of connections
are reused across concurrent requests instead of opening a new socket
for every query.

Pool settings (configurable via .env):
    DB_POOL_MIN   — minimum connections kept alive (default 2)
    DB_POOL_MAX   — maximum simultaneous connections (default 20)

At 1000 concurrent users hitting Flask/Gunicorn with 4 gevent workers:
  - Each worker gets up to DB_POOL_MAX connections
  - Total Postgres load = workers × DB_POOL_MAX (e.g. 4 × 20 = 80)
  - Tune DB_POOL_MAX to stay within your Postgres max_connections limit
"""

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
import logging
import threading
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgreementAI_DB")

# ─────────────────────────────────────────────────────────────────────────────
# Pool singleton — created once on first use, thread-safe
# ─────────────────────────────────────────────────────────────────────────────
_pool: ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> ThreadedConnectionPool | None:
    """Return the shared connection pool, creating it on first call."""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:      # double-checked locking
            return _pool
        try:
            _pool = ThreadedConnectionPool(
                minconn=Config.DB_POOL_MIN,
                maxconn=Config.DB_POOL_MAX,
                dsn=Config.DATABASE_URL,
            )
            logger.info(
                f"DB pool created — min={Config.DB_POOL_MIN}, "
                f"max={Config.DB_POOL_MAX}"
            )
        except Exception as e:
            logger.error(f"Failed to create DB connection pool: {e}")
            _pool = None
    return _pool


def get_db_connection():
    """
    Borrow a connection from the pool.
    Caller MUST release it via release_connection() in a finally block.
    Returns None if the pool is unavailable.
    """
    pool = _get_pool()
    if pool is None:
        return None
    try:
        conn = pool.getconn()
        return conn
    except Exception as e:
        logger.error(f"Pool getconn error: {e}")
        return None


def release_connection(conn) -> None:
    """Return a borrowed connection back to the pool."""
    if conn is None:
        return
    pool = _get_pool()
    if pool is None:
        try:
            conn.close()
        except Exception:
            pass
        return
    try:
        pool.putconn(conn)
    except Exception as e:
        logger.warning(f"Pool putconn error: {e}")


def close_pool() -> None:
    """Shut down the pool cleanly (call on app teardown)."""
    global _pool
    if _pool:
        try:
            _pool.closeall()
            logger.info("DB pool closed.")
        except Exception as e:
            logger.warning(f"Pool closeall error: {e}")
        _pool = None


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers — use these instead of raw psycopg2 calls
# ─────────────────────────────────────────────────────────────────────────────

def init_db() -> bool:
    """
    Execute schema.sql to create all agr_* tables if they don't exist.
    Safe to call on every startup (uses CREATE TABLE IF NOT EXISTS).
    """
    conn = get_db_connection()
    if not conn:
        logger.info("No DB connection — running in mock/offline mode.")
        return False
    try:
        with conn.cursor() as cur:
            with open("schema.sql", "r", encoding="utf-8") as f:
                sql_script = f.read()
            cur.execute(sql_script)
        conn.commit()
        logger.info("DB schema initialised successfully.")
        return True
    except Exception as e:
        logger.error(f"schema.sql execution failed: {e}")
        conn.rollback()
        return False
    finally:
        release_connection(conn)


def query_db(query: str, args: tuple = (), one: bool = False):
    """
    Run a SELECT query and return results as list-of-dicts (or single dict).
    Returns None on connection failure or query error.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, args)
            rv = cur.fetchall()
            conn.commit()
            return (dict(rv[0]) if rv else None) if one else [dict(r) for r in rv]
    except Exception as e:
        logger.error(f"query_db error — {e} | query: {query[:120]}")
        conn.rollback()
        return None
    finally:
        release_connection(conn)


def execute_db(query: str, args: tuple = (), returning: bool = False):
    """
    Run an INSERT / UPDATE / DELETE command.
    If returning=True, fetches and returns the first result row (for RETURNING clauses).
    Returns True/dict on success, False on failure.
    """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, args)
            result = None
            if returning:
                row = cur.fetchone()
                result = dict(row) if row else None
            conn.commit()
            return result if returning else True
    except Exception as e:
        logger.error(f"execute_db error — {e} | query: {query[:120]}")
        conn.rollback()
        return False
    finally:
        release_connection(conn)
