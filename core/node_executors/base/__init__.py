# core/node_executors/base/__init__.py

from .click import ClickNodeExecutor
from .wait import WaitNodeExecutor
from .log import LogNodeExecutor
from .set_window import SetWindowNodeExecutor
from .image_recognition import ImageRecognitionNodeExecutor
from .branch import BranchNodeExecutor
# 追加在 core/node_executors/base/__init__.py 底部
from .logic_check import LogicCheckNodeExecutor# 追加在 core/node_executors/base/__init__.py 底部
from .ocr_recognition import OcrRecognitionNodeExecutor
from .variable_op import VariableOpNodeExecutor
from core.node_executors.base_class import BaseNodeExecutor