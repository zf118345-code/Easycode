# core/schemas.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class JumpSchema(BaseModel):
    type: str = Field(default="next", description="跳转类型: next | node | task | end")
    target: Optional[str] = Field(default=None, description="目标任务 ID")
    target_node: Optional[str] = Field(default=None, description="目标节点 ID")
    return_on_complete: bool = Field(default=False, description="完成后是否返回")

class NodeSchema(BaseModel):
    node_id: str = Field(..., description="节点唯一标识")
    node_name: str = Field(..., description="节点显示名称")
    node_type: str = Field(..., description="节点类型")
    params: Dict[str, Any] = Field(default_factory=dict, description="节点配置参数")
    delay_before: int = Field(default=0, ge=0, description="执行前延迟 (ms)")
    loop_count: int = Field(default=1, description="循环次数 (-1 为无限)")
    enabled: bool = Field(default=True, description="是否启用")
    on_success: Optional[JumpSchema] = Field(default=None, description="成功跳转配置")
    on_failure: Optional[JumpSchema] = Field(default=None, description="失败跳转配置")
    position: Optional[Dict[str, int]] = Field(default=None, description="画布坐标")

class TaskSchema(BaseModel):
    task_id: str = Field(..., description="任务组 ID")
    task_name: str = Field(..., description="任务组名称")
    loop_count: int = Field(default=1, description="循环次数")
    loop_interval: int = Field(default=0, description="循环间隔")
    nodes: List[NodeSchema] = Field(default_factory=list, description="包含节点列表")

class BlueprintSchema(BaseModel):
    project_name: str = Field(default="default", description="项目名称")
    tasks: List[TaskSchema] = Field(default_factory=list, description="任务组列表")
    variables: Dict[str, Any] = Field(default_factory=dict, description="全局变量")

# ===== 请求 Payload 模型 =====

class RunRequestSchema(BaseModel):
    project_path: str
    task_id: str
    start_node_id: Optional[str] = None
    blueprint_data: Optional[BlueprintSchema] = None

class SaveTaskRequestSchema(BaseModel):
    project_path: str
    task_data: TaskSchema

class TaskOrderRequestSchema(BaseModel):
    project_path: str
    order: List[str]

class SaveBlueprintRequestSchema(BaseModel):
    project_path: str
    blueprint_data: BlueprintSchema

class CropScreenshotRequestSchema(BaseModel):
    project_path: str
    template_name: str
    crop_rect: List[int] = Field(..., min_items=4, max_items=4)

class ContextSaveRequestSchema(BaseModel):
    project_path: str
    context: Dict[str, Any]

class OcrTestRequestSchema(BaseModel):
    project_path: Optional[str] = None
    region_value: List[int] = Field(default=[0, 0, 0, 0], min_items=4, max_items=4)
    gray_scale: bool = True
    gray_threshold: int = Field(default=127, ge=0, le=255)

class ImageTestRequestSchema(BaseModel):
    project_path: str
    template_name: str
    gray_scale: bool = True
    gray_threshold: int = Field(default=127, ge=0, le=255)