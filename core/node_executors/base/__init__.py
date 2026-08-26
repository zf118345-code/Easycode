# core/node_executors/base/__init__.py
# 节点执行器注册入口：导入各执行器类以触发 @NodeExecutorRegistry.register 装饰器

from core.node_executors.base_class import BaseNodeExecutor

from .branch import BranchNodeExecutor
from .call_function import CallFunctionNodeExecutor
from .function_contract import FunctionEntryNodeExecutor, FunctionReturnNodeExecutor
from .click import ClickNodeExecutor
from .drag import DragNodeExecutor
from .image_recognition import ImageRecognitionNodeExecutor
from .log import LogNodeExecutor
from .logic_check import LogicCheckNodeExecutor
from .ocr_recognition import OcrRecognitionNodeExecutor

# P2 新增：拓扑与智能跳转节点执行器
from .page_state import PageStateNodeExecutor
from .set_window import SetWindowNodeExecutor
from .smart_jump import SmartJumpNodeExecutor
from .script_call import ScriptCallNodeExecutor
from .scroll import ScrollNodeExecutor
from .text_input import TextInputNodeExecutor
from .variable_op import VariableOpNodeExecutor
from .wait import WaitNodeExecutor

# P3 新增：控件操作节点执行器（Win32 控件树）
from .control import ControlNodeExecutor

__all__ = [
    'ClickNodeExecutor',
    'ScrollNodeExecutor',
    'DragNodeExecutor',
    'TextInputNodeExecutor',
    'WaitNodeExecutor',
    'LogNodeExecutor',
    'SetWindowNodeExecutor',
    'ImageRecognitionNodeExecutor',
    'BranchNodeExecutor',
    'CallFunctionNodeExecutor',
    'FunctionEntryNodeExecutor',
    'FunctionReturnNodeExecutor',
    'LogicCheckNodeExecutor',
    'OcrRecognitionNodeExecutor',
    'VariableOpNodeExecutor',
    'PageStateNodeExecutor',
    'SmartJumpNodeExecutor',
    'ScriptCallNodeExecutor',
    'ControlNodeExecutor',
    'BaseNodeExecutor',
]
