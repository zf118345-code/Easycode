# core/db.py
# SQLite 数据库初始化与连接管理
import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DB_DIR = os.path.join(os.getcwd(), 'data')
DB_PATH = os.path.join(DB_DIR, 'easycode.db')

_schema = """
CREATE TABLE IF NOT EXISTS executions (
    execution_id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    task_id TEXT NOT NULL,
    start_node_id TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    message TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    timestamp TEXT,
    level TEXT DEFAULT 'INFO',
    message TEXT NOT NULL,
    FOREIGN KEY (execution_id) REFERENCES executions(execution_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_execution_logs_eid ON execution_logs(execution_id);

CREATE TABLE IF NOT EXISTS execution_variables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    variable_name TEXT NOT NULL,
    variable_value TEXT,
    variable_type TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (execution_id) REFERENCES executions(execution_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_exec_vars_eid ON execution_variables(execution_id);
"""


def get_db_path() -> str:
    """获取数据库路径（可被环境变量覆盖）"""
    return os.environ.get('EASYCODE_DB_PATH', DB_PATH)


def get_connection() -> sqlite3.Connection:
    """获取 SQLite 连接（启用 WAL 模式和外键）"""
    db_path = get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_connection()
    try:
        conn.executescript(_schema)
        conn.commit()
        logger.info(f'数据库已初始化: {get_db_path()}')
    except Exception as e:
        logger.error(f'数据库初始化失败: {e}')
        raise
    finally:
        conn.close()


# 模块加载时自动初始化
try:
    init_db()
except Exception as e:
    logger.warning(f'数据库自动初始化失败（将在首次使用时重试）: {e}')
