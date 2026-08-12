# core/conditions/handlers/file_exists.py
import os
from typing import Any
from core.conditions.base import BaseConditionEvaluator, ConditionRegistry
from core.utils import resolve_template_string


@ConditionRegistry.register("file_exists")
class FileExistsEvaluator(BaseConditionEvaluator):

    @classmethod
    def evaluate(cls, params: dict, context: Any) -> bool:
        raw_path = str(params.get("file_path", "")).strip()
        operator = str(params.get("operator", "exists"))

        if not raw_path:
            return False

        file_path = resolve_template_string(raw_path, context)

        # ⚡ 兼容 project_dir 与 project_path
        project_dir = getattr(context, 'project_dir', None) or getattr(context, 'project_path', None)

        if not os.path.isabs(file_path) and project_dir:
            file_path = os.path.join(project_dir, file_path)

        path_exists = os.path.exists(file_path)

        if operator == "exists":
            return path_exists
        elif operator in ("not_exists", "not_exist"):
            return not path_exists

        return False