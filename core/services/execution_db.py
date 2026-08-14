# core/services/execution_db.py
# SQLite 持久化执行记录，替代内存 OrderedDict
import contextlib
import json
import logging
from datetime import datetime
from typing import Any

from core.db import get_connection, init_db

logger = logging.getLogger(__name__)

MAX_LOG_ENTRIES = 1000  # 每次执行最多保留的日志条数


class ExecutionDB:
    """执行记录 SQLite 持久化"""

    @staticmethod
    def _ensure_db():
        """确保数据库已初始化"""
        with contextlib.suppress(Exception):
            init_db()

    @staticmethod
    def create_execution(execution_id: str, project_path: str, task_id: str, start_node_id: str = None) -> bool:
        """创建执行记录"""
        ExecutionDB._ensure_db()
        conn = get_connection()
        try:
            now = datetime.now().isoformat()
            conn.execute(
                'INSERT OR REPLACE INTO executions (execution_id, project_path, task_id, start_node_id, status, message, created_at, updated_at) '
                "VALUES (?, ?, ?, ?, 'running', '执行中...', ?, ?)",
                (execution_id, project_path, task_id, start_node_id, now, now),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'创建执行记录失败: {e}')
            return False
        finally:
            conn.close()

    @staticmethod
    def update_status(execution_id: str, status: str, message: str = '') -> bool:
        """更新执行状态"""
        ExecutionDB._ensure_db()
        conn = get_connection()
        try:
            now = datetime.now().isoformat()
            conn.execute(
                'UPDATE executions SET status = ?, message = ?, updated_at = ? WHERE execution_id = ?',
                (status, message, now, execution_id),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'更新执行状态失败: {e}')
            return False
        finally:
            conn.close()

    @staticmethod
    def get_status(execution_id: str) -> dict[str, Any] | None:
        """获取执行状态"""
        ExecutionDB._ensure_db()
        conn = get_connection()
        try:
            row = conn.execute('SELECT * FROM executions WHERE execution_id = ?', (execution_id,)).fetchone()
            if not row:
                return None
            return {
                'status': {'status': row['status'], 'message': row['message']},
                'logs': ExecutionDB.get_logs(execution_id),
            }
        except Exception as e:
            logger.error(f'获取执行状态失败: {e}')
            return None
        finally:
            conn.close()

    @staticmethod
    def add_log(execution_id: str, message: str, level: str = 'INFO', timestamp: str = None) -> bool:
        """添加单条日志"""
        ExecutionDB._ensure_db()
        conn = get_connection()
        try:
            ts = timestamp or datetime.now().isoformat()
            # 获取当前 seq
            row = conn.execute(
                'SELECT MAX(seq) as max_seq FROM execution_logs WHERE execution_id = ?', (execution_id,)
            ).fetchone()
            seq = (row['max_seq'] or 0) + 1 if row else 1

            conn.execute(
                'INSERT INTO execution_logs (execution_id, seq, timestamp, level, message) VALUES (?, ?, ?, ?, ?)',
                (execution_id, seq, ts, level, message),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'添加日志失败: {e}')
            return False
        finally:
            conn.close()

    @staticmethod
    def add_logs(execution_id: str, logs: list[dict[str, Any]]) -> bool:
        """批量添加日志"""
        ExecutionDB._ensure_db()
        conn = get_connection()
        try:
            # 获取当前 seq
            row = conn.execute(
                'SELECT MAX(seq) as max_seq FROM execution_logs WHERE execution_id = ?', (execution_id,)
            ).fetchone()
            seq = (row['max_seq'] or 0) + 1 if row else 1

            for log_item in logs:
                ts = log_item.get('time') or datetime.now().isoformat()
                msg = log_item.get('message', str(log_item)) if isinstance(log_item, dict) else str(log_item)
                level = log_item.get('level', 'INFO') if isinstance(log_item, dict) else 'INFO'
                conn.execute(
                    'INSERT INTO execution_logs (execution_id, seq, timestamp, level, message) VALUES (?, ?, ?, ?, ?)',
                    (execution_id, seq, ts, level, msg),
                )
                seq += 1

            conn.commit()
            return True
        except Exception as e:
            logger.error(f'批量添加日志失败: {e}')
            return False
        finally:
            conn.close()

    @staticmethod
    def get_logs(execution_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
        """获取日志（可从指定 seq 之后）"""
        ExecutionDB._ensure_db()
        conn = get_connection()
        try:
            rows = conn.execute(
                'SELECT * FROM execution_logs WHERE execution_id = ? AND seq > ? ORDER BY seq ASC',
                (execution_id, after_seq),
            ).fetchall()
            return [{'time': r['timestamp'], 'level': r['level'], 'message': r['message']} for r in rows]
        except Exception as e:
            logger.error(f'获取日志失败: {e}')
            return []
        finally:
            conn.close()

    @staticmethod
    def get_log_count(execution_id: str) -> int:
        """获取日志总数"""
        ExecutionDB._ensure_db()
        conn = get_connection()
        try:
            row = conn.execute(
                'SELECT COUNT(*) as cnt FROM execution_logs WHERE execution_id = ?', (execution_id,)
            ).fetchone()
            return row['cnt'] if row else 0
        except Exception:
            return 0
        finally:
            conn.close()

    @staticmethod
    def list_executions(project_path: str = None, limit: int = 50) -> list[dict[str, Any]]:
        """列出执行记录"""
        ExecutionDB._ensure_db()
        conn = get_connection()
        try:
            if project_path:
                rows = conn.execute(
                    'SELECT * FROM executions WHERE project_path = ? ORDER BY created_at DESC LIMIT ?',
                    (project_path, limit),
                ).fetchall()
            else:
                rows = conn.execute('SELECT * FROM executions ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f'列出执行记录失败: {e}')
            return []
        finally:
            conn.close()

    @staticmethod
    def delete_execution(execution_id: str) -> bool:
        """删除执行记录（级联删除日志）"""
        ExecutionDB._ensure_db()
        conn = get_connection()
        try:
            conn.execute('DELETE FROM execution_logs WHERE execution_id = ?', (execution_id,))
            conn.execute('DELETE FROM executions WHERE execution_id = ?', (execution_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'删除执行记录失败: {e}')
            return False
        finally:
            conn.close()

    @staticmethod
    def save_variable(execution_id: str, name: str, value: Any, var_type: str = None) -> bool:
        """保存/更新执行时变量快照"""
        ExecutionDB._ensure_db()
        conn = get_connection()
        try:
            now = datetime.now().isoformat()
            conn.execute(
                'INSERT OR REPLACE INTO execution_variables (execution_id, variable_name, variable_value, variable_type, updated_at) '
                'VALUES (?, ?, ?, ?, ?)',
                (
                    execution_id,
                    name,
                    json.dumps(value, ensure_ascii=False, default=str),
                    var_type or type(value).__name__,
                    now,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'保存变量失败: {e}')
            return False
        finally:
            conn.close()

    @staticmethod
    def get_variables(execution_id: str) -> dict[str, Any]:
        """获取执行时所有变量"""
        ExecutionDB._ensure_db()
        conn = get_connection()
        try:
            rows = conn.execute('SELECT * FROM execution_variables WHERE execution_id = ?', (execution_id,)).fetchall()
            result = {}
            for row in rows:
                try:
                    result[row['variable_name']] = json.loads(row['variable_value'])
                except Exception:
                    result[row['variable_name']] = row['variable_value']
            return result
        except Exception as e:
            logger.error(f'获取变量失败: {e}')
            return {}
        finally:
            conn.close()

    @staticmethod
    def cleanup_old_executions(max_records: int = 100):
        """清理旧执行记录，保留最近 max_records 条"""
        ExecutionDB._ensure_db()
        conn = get_connection()
        try:
            rows = conn.execute(
                'SELECT execution_id FROM executions ORDER BY created_at DESC LIMIT -1 OFFSET ?', (max_records,)
            ).fetchall()
            for row in rows:
                eid = row['execution_id']
                conn.execute('DELETE FROM execution_logs WHERE execution_id = ?', (eid,))
                conn.execute('DELETE FROM executions WHERE execution_id = ?', (eid,))
            conn.commit()
            if rows:
                logger.info(f'已清理 {len(rows)} 条旧执行记录')
        except Exception as e:
            logger.error(f'清理旧执行记录失败: {e}')
        finally:
            conn.close()
