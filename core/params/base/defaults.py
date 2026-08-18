# core/params/base/defaults.py
# 节点参数通用默认值（单一事实源）
# 各节点 schema 引用本文件常量，避免魔数散落；前端建节点时从 schema default 填充。
#
# 约定：
#   - 一般节点默认 延迟 200ms 执行、循环 1 次
#   - 图像匹配类：相似度 85%、匹配超时 3000ms、匹配区域默认「录制时的坐标区域」、
#     识别成功后默认「点击目标中心」、灰度预处理默认开启（二值化阈值 127）

NODE_DEFAULTS: dict[str, object] = {
    'delay_before': 200,          # 节点执行前延迟 (ms)
    'loop_count': 1,              # 循环次数
    'threshold': 85,              # 图像匹配相似度 (%)
    'timeout': 3000,              # 匹配超时时长 (ms)
    'region_type': 'recorded',    # 匹配区域：默认录制时的坐标区域
    'on_success_action': 'click_center',  # 识别成功后默认点击目标中心
    'gray_scale': False,          # 灰度预处理默认关闭，按需开启
    'gray_threshold': 127,        # 二值化灰度阈值 (0-255)
}
