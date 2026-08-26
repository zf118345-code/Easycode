# core/db.py
# SQLite 数据库初始化与连接管理
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

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
    category TEXT DEFAULT 'execution',
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


def get_db_path(project_path: str | None = None) -> str:
    """Return the active project's private runtime database path."""
    if not project_path:
        from core.services.project_workspace_service import project_workspace_manager

        active = project_workspace_manager.active()
        project_path = active.get('project_path') if active else None
    if not project_path:
        raise RuntimeError('没有活动项目，不能访问执行数据库')
    return str(Path(project_path).resolve() / '.easycode' / 'runtime.db')


def get_connection(project_path: str | None = None) -> sqlite3.Connection:
    """获取 SQLite 连接（启用 WAL 模式和外键）"""
    db_path = get_db_path(project_path)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db(project_path: str | None = None):
    """初始化数据库表"""
    conn = get_connection(project_path)
    try:
        conn.executescript(_schema)
        log_columns = {row['name'] for row in conn.execute('PRAGMA table_info(execution_logs)').fetchall()}
        if 'category' not in log_columns:
            # Existing rows stay NULL so the reader can infer their category from message text.
            conn.execute('ALTER TABLE execution_logs ADD COLUMN category TEXT')
        conn.commit()
        logger.info(f'数据库已初始化: {get_db_path(project_path)}')
    except Exception as e:
        logger.error(f'数据库初始化失败: {e}')
        raise
    finally:
        conn.close()
