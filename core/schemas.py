# core/schemas.py

# 修复：所有新字段 Optional + extra="allow" 容错，字段名对齐前后端

from typing import Any

from pydantic import BaseModel, Field


class JumpSchema(BaseModel):
    """连线跳转配置，字段名与前端对齐"""

    model_config = {'extra': 'allow'}

    target: str | None = Field(default=None, description='目标任务组 ID')
    target_task: str | None = Field(default=None, description='目标任务组 ID（前端兼容字段）')
    target_node: str | None = Field(default=None, description='目标节点 ID')
    return_on_complete: bool = Field(default=False, description='完成后是否返回')
    # 兼容前端可能发送的旧字段
    type: str | None = Field(default=None, description='跳转类型（已废弃，兼容保留）')
    jump_type: str | None = Field(default=None, description='跳转类型（已废弃，兼容保留）')


class EdgeSchema(BaseModel):
    """连线一等公民的 API Schema，所有字段容错"""

    model_config = {'extra': 'allow'}

    edge_id: str = Field(default='', description='连线唯一标识')
    source_node: str = Field(default='', description='源节点 ID')
    target_node: str = Field(default='', description='目标节点 ID')
    # 兼容前端使用的 source/target 简写
    source: str | None = Field(default=None, description='源节点 ID（前端兼容字段）')
    target: str | None = Field(default=None, description='目标节点/页面 ID（前端兼容字段）')
    target_task: str | None = Field(default=None, description='目标任务组 ID')
    source_port: str = Field(default='success', description='源端口')
    source_exit: str | None = Field(default=None, description='源出口（拓扑画布兼容字段）')
    condition: dict[str, Any] | None = Field(default=None, description='连线条件')
    return_on_complete: bool = Field(default=False, description='完成后是否返回')
    label: str = Field(default='', description='连线显示标签')
    canvas: str = Field(default='workflow', description='所属画布')


class NodeSchema(BaseModel):
    """节点 Schema，position 容错为 float 兼容前端坐标"""

    model_config = {'extra': 'allow'}

    node_id: str = Field(..., description='节点唯一标识')
    node_name: str = Field(..., description='节点显示名称')
    node_type: str = Field(..., description='节点类型')
    params: dict[str, Any] = Field(default_factory=dict, description='节点配置参数')
    delay_before: int = Field(default=0, ge=0, description='执行前延迟 (ms)')
    loop_count: int = Field(default=1, description='循环次数')
    enabled: bool = Field(default=True, description='是否启用')
    position: dict[str, Any] | None = Field(default=None, description='画布坐标')
    size: dict[str, Any] | None = Field(default=None, description='节点尺寸')


class TaskSchema(BaseModel):
    """任务组 Schema
    修复：task_id 改为 Optional，因为创建任务时前端不传 task_id（由后端生成）
    """

    model_config = {'extra': 'allow'}

    task_id: str | None = Field(default=None, description='任务组 ID（创建时可不传，后端自动生成）')
    task_name: str = Field(..., description='任务组名称')
    loop_count: int = Field(default=1, description='循环次数')
    loop_interval: int = Field(default=0, description='循环间隔')
    nodes: list[NodeSchema] = Field(default_factory=list, description='包含节点列表')


class TopologyMapSchema(BaseModel):
    """拓扑地图蓝图：任务组化结构（tasks 内含拓扑节点，edges 为拓扑连线）"""

    model_config = {'extra': 'allow'}

    tasks: list[dict[str, Any]] = Field(default_factory=list, description='拓扑任务组列表（节点存于 tasks[].nodes）')
    edges: list[dict[str, Any]] = Field(default_factory=list, description='拓扑连线列表')


class BlueprintSchema(BaseModel):
    """
    蓝图 Schema
    关键修复：extra="allow" 保留前端发送的所有字段（不丢弃 topology/edges）
    所有新字段 Optional，兼容旧蓝图
    """

    model_config = {'extra': 'allow'}

    project_name: str = Field(default='default', description='项目名称')
    tasks: list[TaskSchema] = Field(default_factory=list, description='任务组列表')
    variables: dict[str, Any] = Field(default_factory=dict, description='全局变量')
    ui_state: dict[str, Any] | None = Field(default_factory=dict, description='UI布局')
    edges: list[dict[str, Any]] = Field(default_factory=list, description='全局连线列表')
    topology: dict[str, Any] | None = Field(default=None, description='拓扑地图蓝图')


# ===== 请求 Payload 模型 =====


class RunRequestSchema(BaseModel):
    model_config = {'extra': 'allow'}

    project_path: str
    task_id: str
    start_node_id: str | None = None
    blueprint_data: dict[str, Any] | None = None


class SaveTaskRequestSchema(BaseModel):
    model_config = {'extra': 'allow'}

    project_path: str
    task_data: TaskSchema


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
    workflow_data: dict[str, Any] = Field(..., description='流程画布数据 {tasks, edges}，直接落盘不经 Pydantic 校验')


class TopologySaveRequestSchema(BaseModel):
    """保存拓扑地图（topology.json）请求"""

    model_config = {'extra': 'allow'}

    project_path: str
    topology_data: dict[str, Any] = Field(..., description='拓扑地图数据 {tasks, edges}，直接落盘不经 Pydantic 校验')


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


class ImageTestRequestSchema(BaseModel):
    model_config = {'extra': 'allow'}

    project_path: str
    template_name: str
    gray_scale: bool = True
    gray_threshold: int = Field(default=127, ge=0, le=255)


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
