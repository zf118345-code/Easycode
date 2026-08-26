import pytest
import sqlite3

from core.logging_model import infer_log_category


@pytest.mark.parametrize(
    ('message', 'expected'),
    [
        ('[页面状态] 已定位当前页面', 'vision'),
        ('[OCR] 识别文字="开始"', 'vision'),
        ('[智能跳转] 寻路成功', 'navigation'),
        ('[弹窗处理] 执行关闭动作', 'navigation'),
        ('[目标绑定] 已绑定窗口', 'operation'),
        ('[ADB] 设备已连接', 'operation'),
        ('[变量操作] count = 2', 'data'),
        ('[调用能力] collector 完成', 'data'),
        ('[Node 执行] 等待节点', 'node'),
        ('[Executor] 启动流程', 'execution'),
    ],
)
def test_log_category_inference(message, expected):
    assert infer_log_category(message) == expected


def test_explicit_valid_category_wins_and_invalid_category_falls_back():
    assert infer_log_category('[OCR] 文本', 'data') == 'data'
    assert infer_log_category('[OCR] 文本', 'unknown') == 'vision'


def test_init_db_adds_nullable_category_to_existing_runtime_database(tmp_path, monkeypatch):
    import core.db as db_mod

    db_path = tmp_path / 'runtime.db'
    conn = sqlite3.connect(db_path)
    conn.execute(
        'CREATE TABLE execution_logs ('
        'id INTEGER PRIMARY KEY, execution_id TEXT, seq INTEGER, timestamp TEXT, '
        'level TEXT, message TEXT)'
    )
    conn.execute(
        'INSERT INTO execution_logs (execution_id, seq, timestamp, level, message) '
        "VALUES ('old', 1, '10:00:00', 'info', '[OCR] 旧日志')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db_mod, 'get_db_path', lambda project_path=None: str(db_path))
    db_mod.init_db(str(tmp_path))

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute('PRAGMA table_info(execution_logs)').fetchall()}
    category = conn.execute("SELECT category FROM execution_logs WHERE execution_id='old'").fetchone()[0]
    conn.close()
    assert 'category' in columns
    assert category is None
