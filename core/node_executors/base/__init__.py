# core/node_executors/base/__init__.py
# 节点执行器注册入口：导入各执行器类以触发 @NodeExecutorRegistry.register 装饰器

from .click import ClickNodeExecutor
from .wait import WaitNodeExecutor
from .log import LogNodeExecutor
from .set_window import SetWindowNodeExecutor
from .image_recognition import ImageRecognitionNodeExecutor
from .branch import BranchNodeExecutor
from .logic_check import LogicCheckNodeExecutor
from .ocr_recognition import OcrRecognitionNodeExecutor
from .variable_op import VariableOpNodeExecutor

# P2 新增：拓扑与智能跳转节点执行器
from .page_state import PageStateNodeExecutor
from .smart_jump import SmartJumpNodeExecutor

from core.node_executors.base_class import BaseNodeExecutor

__all__ = [
    "ClickNodeExecutor",
    "WaitNodeExecutor",
    "LogNodeExecutor",
    "SetWindowNodeExecutor",
    "ImageRecognitionNodeExecutor",
    "BranchNodeExecutor",
    "LogicCheckNodeExecutor",
    "OcrRecognitionNodeExecutor",
    "VariableOpNodeExecutor",
    "PageStateNodeExecutor",
    "SmartJumpNodeExecutor",
    "BaseNodeExecutor",
]
