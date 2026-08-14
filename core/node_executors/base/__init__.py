# core/node_executors/base/__init__.py
# 节点执行器注册入口：导入各执行器类以触发 @NodeExecutorRegistry.register 装饰器

from core.node_executors.base_class import BaseNodeExecutor

from .branch import BranchNodeExecutor
from .click import ClickNodeExecutor
from .image_recognition import ImageRecognitionNodeExecutor
from .log import LogNodeExecutor
from .logic_check import LogicCheckNodeExecutor
from .ocr_recognition import OcrRecognitionNodeExecutor

# P2 新增：拓扑与智能跳转节点执行器
from .page_state import PageStateNodeExecutor
from .set_window import SetWindowNodeExecutor
from .smart_jump import SmartJumpNodeExecutor
from .variable_op import VariableOpNodeExecutor
from .wait import WaitNodeExecutor

__all__ = [
    'ClickNodeExecutor',
    'WaitNodeExecutor',
    'LogNodeExecutor',
    'SetWindowNodeExecutor',
    'ImageRecognitionNodeExecutor',
    'BranchNodeExecutor',
    'LogicCheckNodeExecutor',
    'OcrRecognitionNodeExecutor',
    'VariableOpNodeExecutor',
    'PageStateNodeExecutor',
    'SmartJumpNodeExecutor',
    'BaseNodeExecutor',
]
