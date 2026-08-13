
# core/schemas.py

# 修复：所有新字段 Optional + extra="allow" 容错，字段名对齐前后端

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class JumpSchema(BaseModel):
    """连线跳转配置，字段名与前端对齐"""
    model_config = {"extra": "allow"}

    target: Optional[str] = Field(default=None, description="目标任务组 ID")
    target_task: Optional[str] = Field(default=None, description="目标任务组 ID（前端兼容字段）")
    target_node: Optional[str] = Field(default=None, description="目标节点 ID")
    return_on_complete: bool = Field(default=False, description="完成后是否返回")
    # 兼容前端可能发送的旧字段
    type: Optional[str] = Field(default=None, description="跳转类型（已废弃，兼容保留）")
    jump_type: Optional[str] = Field(default=None, description="跳转类型（已废弃，兼容保留）")

class EdgeSchema(BaseModel):
    """连线一等公民的 API Schema，所有字段容错"""
    model_config = {"extra": "allow"}

    edge_id: str = Field(default="", description="连线唯一标识")
    source_node: str = Field(default="", description="源节点 ID")
    target_node: str = Field(default="", description="目标节点 ID")
    # 兼容前端使用的 source/target 简写
    source: Optional[str] = Field(default=None, description="源节点 ID（前端兼容字段）")
    target: Optional[str] = Field(default=None, description="目标节点/页面 ID（前端兼容字段）")
    target_task: Optional[str] = Field(default=None, description="目标任务组 ID")
    source_port: str = Field(default="success", description="源端口")
    source_exit: Optional[str] = Field(default=None, description="源出口（拓扑画布兼容字段）")
    condition: Optional[Dict[str, Any]] = Field(default=None, description="连线条件")
    return_on_complete: bool = Field(default=False, description="完成后是否返回")
    label: str = Field(default="", description="连线显示标签")
    canvas: str = Field(default="workflow", description="所属画布")

class NodeSchema(BaseModel):
    """节点 Schema，positions 容错为 float 兼容前端坐标"""
    model_config = {"extra": "allow"}

    node_id: str = Field(..., description="节点唯一标识")
    node_name: str = Field(..., description="节点显示名称")
    node_type: str = Field(..., description="节点类型")
    params: Dict[str, Any] = Field(default_factory=dict, description="节点配置参数")
    delay_before: int = Field(default=0, ge=0, description="执行前延迟 (ms)")
    loop_count: int = Field(default=1, description="循环次数")
    enabled: bool = Field(default=True, description="是否启用")
    on_success: Optional[Dict[str, Any]] = Field(default=None, description="成功跳转（兼容旧版，存于 params）")
    on_failure: Optional[Dict[str, Any]] = Field(default=None, description="失败跳转（兼容旧版，存于 params）")
    position: Optional[Dict[str, Any]] = Field(default=None, description="画布坐标")
    positions: Dict[str, Any] = Field(default_factory=dict, description="多画布坐标")
    size: Optional[Dict[str, Any]] = Field(default=None, description="节点尺寸")
    canvas_ids: List[str] = Field(default_factory=lambda: ["workflow"], description="所属画布列表")

class TaskSchema(BaseModel):
    """任务组 Schema
    修复：task_id 改为 Optional，因为创建任务时前端不传 task_id（由后端生成）
    """
    model_config = {"extra": "allow"}

    task_id: Optional[str] = Field(default=None, description="任务组 ID（创建时可不传，后端自动生成）")
    task_name: str = Field(..., description="任务组名称")
    loop_count: int = Field(default=1, description="循环次数")
    loop_interval: int = Field(default=0, description="循环间隔")
    nodes: List[NodeSchema] = Field(default_factory=list, description="包含节点列表")

class TopologyNodeSchema(BaseModel):
    """拓扑页面状态节点，字段名与前端对齐"""
    model_config = {"extra": "allow"}

    node_id: str = Field(default="", description="节点唯一标识")
    node_name: str = Field(default="", description="节点显示名称")
    name: Optional[str] = Field(default=None, description="节点名称（前端兼容字段）")
    label: Optional[str] = Field(default=None, description="节点标签（前端兼容字段）")
    type: Optional[str] = Field(default="page_state", description="节点类型")
    page_id: str = Field(default="", description="页面唯一标识")
    features: List[Dict[str, Any]] = Field(default_factory=list, description="复合特征列表")
    feature_mode: str = Field(default="and", description="特征组合模式")
    position: Optional[Dict[str, Any]] = Field(default=None, description="画布坐标")
    exits: List[Dict[str, Any]] = Field(default_factory=list, description="出口列表")
    params: Dict[str, Any] = Field(default_factory=dict, description="节点参数")
    condition: Optional[Dict[str, Any]] = Field(default=None, description="节点条件")

class TopologyEdgeSchema(BaseModel):
    """拓扑连线，字段名与前端对齐"""
    model_config = {"extra": "allow"}

    edge_id: str = Field(default="", description="连线唯一标识")
    source_page: str = Field(default="", description="源页面 ID")
    target_page: str = Field(default="", description="目标页面 ID")
    # 兼容前端使用的 source/target
    source: Optional[str] = Field(default=None, description="源节点/页面 ID（前端兼容字段）")
    target: Optional[str] = Field(default=None, description="目标节点/页面 ID（前端兼容字段）")
    source_exit: Optional[str] = Field(default=None, description="源出口标识")
    action: str = Field(default="", description="过图动作")
    conditions: List[Dict[str, Any]] = Field(default_factory=list, description="过图条件")
    condition: Optional[Dict[str, Any]] = Field(default=None, description="连线条件（前端兼容字段）")
    label: str = Field(default="", description="连线标签")

class TopologyMapSchema(BaseModel):
    """拓扑地图蓝图"""
    model_config = {"extra": "allow"}

    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="拓扑节点列表")
    edges: List[Dict[str, Any]] = Field(default_factory=list, description="拓扑连线列表")

class BlueprintSchema(BaseModel):
    """
    蓝图 Schema
    关键修复：extra="allow" 保留前端发送的所有字段（不丢弃 topology/edges）
    所有新字段 Optional，兼容旧蓝图
    """
    model_config = {"extra": "allow"}

    project_name: str = Field(default="default", description="项目名称")
    tasks: List[TaskSchema] = Field(default_factory=list, description="任务组列表")
    variables: Dict[str, Any] = Field(default_factory=dict, description="全局变量")
    ui_state: Optional[Dict[str, Any]] = Field(default_factory=dict, description="UI布局")
    edges: List[Dict[str, Any]] = Field(default_factory=list, description="全局连线列表")
    topology: Optional[Dict[str, Any]] = Field(default=None, description="拓扑地图蓝图")
    task_order: Optional[List[str]] = Field(default=None, description="任务排序")

# ===== 请求 Payload 模型 =====

class RunRequestSchema(BaseModel):
    model_config = {"extra": "allow"}

    project_path: str
    task_id: str
    start_node_id: Optional[str] = None
    blueprint_data: Optional[Dict[str, Any]] = None

class SaveTaskRequestSchema(BaseModel):
    model_config = {"extra": "allow"}

    project_path: str
    task_data: TaskSchema

class TaskOrderRequestSchema(BaseModel):
    model_config = {"extra": "allow"}

    project_path: str
    order: List[str]

class SaveBlueprintRequestSchema(BaseModel):
    """
    保存蓝图请求
    关键修复：blueprint_data 改为 Dict[str, Any] 而非 BlueprintSchema
    避免 Pydantic 校验丢弃字段或因类型不匹配返回 422/500
    """
    model_config = {"extra": "allow"}

    project_path: str
    blueprint_data: Dict[str, Any] = Field(..., description="蓝图原始数据，直接落盘不经 Pydantic 校验")

class CropScreenshotRequestSchema(BaseModel):
    model_config = {"extra": "allow"}

    project_path: str
    template_name: str
    crop_rect: List[int] = Field(..., min_length=4, max_length=4)

class ContextSaveRequestSchema(BaseModel):
    model_config = {"extra": "allow"}

    project_path: str
    context: Dict[str, Any]

class OcrTestRequestSchema(BaseModel):
    model_config = {"extra": "allow"}

    project_path: Optional[str] = None
    region_value: List[int] = Field(default=[0, 0, 0, 0])
    gray_scale: bool = True
    gray_threshold: int = Field(default=127, ge=0, le=255)
    image_source: Optional[str] = Field(default="")

class ImageTestRequestSchema(BaseModel):
    model_config = {"extra": "allow"}

    project_path: str
    template_name: str
    gray_scale: bool = True
    gray_threshold: int = Field(default=127, ge=0, le=255)
