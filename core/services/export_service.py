# core/services/export_service.py
import os
import json
from fastapi import HTTPException
from core.builder.exporter import ProjectExporter


class ExportService:
    """
    工业级导出与 Schema 业务服务
    实现控制层与打包导出逻辑的解耦
    """

    @classmethod
    def get_form_schema(cls, project_path: str) -> dict:
        """读取项目绑定的客户动态表单 Schema"""
        if not project_path or not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="项目路径不存在")

        schema_path = os.path.join(project_path, "form_schema.json")
        if os.path.exists(schema_path):
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"读取 Schema 失败: {e}")

        return {"form_title": "客户运行配置面板", "groups": []}

    @classmethod
    def save_form_schema(cls, project_path: str, schema_data: dict) -> dict:
        """保存项目绑定的客户动态表单 Schema"""
        if not project_path or not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="项目路径不存在")

        schema_path = os.path.join(project_path, "form_schema.json")
        try:
            with open(schema_path, "w", encoding="utf-8") as f:
                json.dump(schema_data, f, ensure_ascii=False, indent=2)
            return {"status": "success"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"保存 Schema 失败: {e}")

    @classmethod
    def build_export_bundle(cls, project_path: str, form_schema: dict) -> dict:
        """执行项目打包与 DRM 加密构建"""
        if not project_path or not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="项目路径不存在")

        try:
            return ProjectExporter.build_export_bundle(project_path, form_schema)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"打包编译失败: {e}")