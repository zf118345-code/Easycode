# core/schemas.py

# API 请求模型。

from typing import Any

from pydantic import BaseModel, Field


# ===== 请求 Payload 模型 =====


class RunRequestSchema(BaseModel):
    model_config = {'extra': 'allow'}

    project_path: str
    task_id: str
    start_node_id: str | None = None
    blueprint_data: dict[str, Any] | None = None


class SaveBlueprintRequestSchema(BaseModel):
    """
    保存蓝图请求
    关键修复：blueprint_data 改为 Dict[str, Any] 而非 BlueprintSchema
    避免 Pydantic 校验丢弃字段或因类型不匹配返回 422/500
    """

    model_config = {'extra': 'allow'}

    project_path: str
    blueprint_data: dict[str, Any] = Field(..., description='蓝图原始数据，直接落盘不经 Pydantic 校验')


class WorkflowSaveRequestSchema(BaseModel):
    """保存流程画布（workflow.json）请求"""

    model_config = {'extra': 'allow'}

    project_path: str
    workflow_data: dict[str, Any] = Field(..., description='流程数据 {main_graph, functions, function_folders}')


class TopologySaveRequestSchema(BaseModel):
    """保存拓扑地图（topology.json）请求"""

    model_config = {'extra': 'allow'}

    project_path: str
    topology_data: dict[str, Any] = Field(..., description='页面地图数据 {nodes, edges}')


class FunctionCreateRequestSchema(BaseModel):
    model_config = {'extra': 'forbid'}

    project_path: str
    name: str = Field(default='新建函数', min_length=1, max_length=64)
    folder_id: str | None = None


class FunctionSaveRequestSchema(BaseModel):
    model_config = {'extra': 'forbid'}

    project_path: str
    function_data: dict[str, Any]


class CropScreenshotRequestSchema(BaseModel):
    model_config = {'extra': 'allow'}

    project_path: str
    template_name: str
    crop_rect: list[int] = Field(..., min_length=4, max_length=4)


class ContextSaveRequestSchema(BaseModel):
    model_config = {'extra': 'allow'}

    project_path: str
    context: dict[str, Any]


class OcrTestRequestSchema(BaseModel):
    model_config = {'extra': 'allow'}

    project_path: str | None = None
    region_value: list[int] = Field(default=[0, 0, 0, 0])
    gray_scale: bool = True
    gray_threshold: int = Field(default=127, ge=0, le=255)
    image_source: str | None = Field(default='')
    region_reference_size: list[int] = Field(default=[0, 0])


class ImageTestRequestSchema(BaseModel):
    model_config = {'extra': 'allow'}

    project_path: str
    template_name: str
    gray_scale: bool = True
    gray_threshold: int = Field(default=127, ge=0, le=255)
    preview_only: bool = False
    # ⚡ 区域匹配参数（节点"测试识别"携带；与执行引擎坐标系一致：region_value 为工作区相对坐标）
    region_type: str = 'fullwindow'
    region_value: list[int] = Field(default=[0, 0, 0, 0])
    region_reference_size: list[int] = Field(default=[0, 0])


# ===== 补充：原 dict body 端点的 Pydantic Schema =====


class ExporterSchemaRequestSchema(BaseModel):
    """导出器表单 Schema 请求"""

    model_config = {'extra': 'allow'}

    project_path: str = Field(..., description='项目路径')
    schema_data: dict[str, Any] | None = Field(default=None, description='表单 Schema 数据')


class ExporterBuildRequestSchema(BaseModel):
    """导出打包请求"""

    model_config = {'extra': 'allow'}

    project_path: str = Field(..., description='项目路径')
    form_schema: dict[str, Any] | None = Field(default=None, description='客户配置表单 Schema')


class CompileExeRequestSchema(BaseModel):
    """编译 Player EXE 请求"""

    model_config = {'extra': 'allow'}

    project_path: str = Field(..., description='项目路径')


class PlayerConfigRequestSchema(BaseModel):
    """Player 用户配置保存请求"""

    model_config = {'extra': 'allow'}

    user_config: dict[str, Any] = Field(default_factory=dict, description='用户配置数据')


class TemplateMkdirRequestSchema(BaseModel):
    """创建模板文件夹请求"""

    model_config = {'extra': 'allow'}

    project_path: str = Field(..., description='项目路径')
    parent_path: str = Field(default='', description='父目录相对路径')
    folder_name: str = Field(default='', description='文件夹名称')


class TemplateDeleteRequestSchema(BaseModel):
    """删除项目视觉资源或资源文件夹。"""

    model_config = {'extra': 'forbid'}

    project_path: str = Field(..., description='项目路径')
    relative_path: str = Field(..., description='templates 下的相对路径')


class TemplateMoveRequestSchema(BaseModel):
    """移动或重命名项目视觉资源。"""

    model_config = {'extra': 'forbid'}

    project_path: str = Field(..., description='项目路径')
    relative_path: str = Field(..., description='原始相对路径')
    target_parent_path: str = Field(..., description='目标父目录相对路径')
    new_name: str = Field(default='', description='新名称；留空时保留原名')


class SaveRegionRequestSchema(BaseModel):
    """保存区域请求"""

    model_config = {'extra': 'allow'}

    project_path: str = Field(..., description='项目路径')
    template_name: str | None = Field(default=None, description='模板名称')
    relative_path: str | None = Field(default=None, description='相对路径')
    crop_rect: list[int] | None = Field(default=None, description='裁剪区域 [x, y, w, h]')
    region: dict[str, Any] | None = Field(default=None, description='区域数据')


class StepRequestSchema(BaseModel):
    """单步执行请求"""

    model_config = {'extra': 'allow'}

    step: str = Field(default='over', description='单步类型: over/into/out/next')


class BreakpointsRequestSchema(BaseModel):
    """批量设置断点请求"""

    model_config = {'extra': 'allow'}

    breakpoints: list[str] = Field(default_factory=list, description='断点节点 ID 列表')


class BreakpointNodeRequestSchema(BaseModel):
    """单个断点操作请求"""

    model_config = {'extra': 'allow'}

    node_id: str = Field(..., description='节点 ID')
