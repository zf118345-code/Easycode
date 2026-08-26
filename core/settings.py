# core/settings.py
# ⚡ 项目级引擎设置：全局生效，前端「项目设置」页面可配置（编辑菜单 → 项目设置）
# 所有设置以项目为单位存储（project.json 的 settings 段），未配置时使用默认值。
# 新增设置项：在此加默认值 + SETTINGS_GROUPS 加字段元数据（前端自动渲染）

DEFAULT_PROJECT_SETTINGS = {
    # ===== 加载与等待 =====
    'frame_stable_frames': 2,          # 帧稳定判定：连续几帧画面基本不变视为加载完成
    'frame_stable_threshold': 12,      # 帧差阈值：相邻帧抽样像素差均值低于此值视为静止
    'page_load_poll_ms': 250,          # 画面静止后页面识别间隔
    'page_load_anim_wait_ms': 200,     # 画面变化中（加载动画）的等待间隔
    # ===== 弹窗处理 =====
    'popup_cooldown_ms': 800,          # 同一弹窗关闭动作后的冷却窗口（防响应延迟重复点击）
    'popup_max_handles': 5,            # 单次检查点弹窗处理次数上限
    'popup_max_consecutive': 3,        # 连续检查点都在处理弹窗即判定"关不完"报错
    'popup_quiet_frames': 2,           # 关闭后连续多少个稳定无弹窗帧才允许恢复主流程
    'popup_quiet_window_ms': 500,      # 关闭后最短无弹窗静默时间
    'popup_poll_ms': 150,              # 弹窗清场复检间隔
    'popup_total_timeout_ms': 5000,    # 单次弹窗清场总超时
    # ===== 识别匹配 =====
    'match_poll_ms': 100,              # 图像/条件匹配轮询间隔（超时窗口内的重试频率）
    'ocr_poll_ms': 300,                # OCR 识别轮询间隔
    'multi_scale_scales': '1.0,0.75,0.5',  # 多尺度模板匹配缩放级别（逗号分隔；级别越多越慢、DPI 覆盖越好）
    # ===== 执行引擎 =====
    'max_node_visits': 50,             # 单节点最大访问次数（环路保护）
    'smart_jump_attempts': 3,          # 智能跳转整体重试次数上限
    'smart_jump_retry_ms': 500,        # 智能跳转重试间隔
    'control_timeout_cap_ms': 1500,    # 控件查找（祖先链/兜底路径）超时上限
    'allow_physical_fallback': False,  # PC后台输入明确失败时是否允许回退物理输入（默认关闭，模拟器永不回退）
    'android_stream_reconnect_attempts': 2,  # scrcpy断线有界重连，超限熔断当前实例
    # ===== 日志与调试 =====
    'max_logs': 500,                   # 单次执行内存日志条数上限
    'debug_screenshot_max': 20,        # debug_screenshots 目录保留截图张数上限
}

# 前端设置页分组元数据（field: key/label/desc/type/min/max）
SETTINGS_GROUPS = [
    {
        'key': 'loading',
        'title': '加载与等待',
        'desc': '页面跳转/加载期间的等待策略：动画中纯等待、画面静止后开始识别，识别不到持续重试直到超时',
        'fields': [
            {'key': 'frame_stable_frames', 'label': '帧稳定判定帧数', 'type': 'number', 'min': 1, 'max': 10,
             'desc': '连续几帧画面基本不变视为加载完成（帧数越多判定越保守）'},
            {'key': 'frame_stable_threshold', 'label': '帧差阈值', 'type': 'number', 'min': 0, 'max': 100,
             'desc': '相邻帧抽样像素差均值，低于此值视为画面静止；动画越大默认阈值越需调高'},
            {'key': 'page_load_poll_ms', 'label': '静止后识别间隔 (ms)', 'type': 'number', 'min': 50, 'max': 2000,
             'desc': '画面静止后多久识别一次页面（越小响应越快、CPU 消耗越高）'},
            {'key': 'page_load_anim_wait_ms', 'label': '动画中等待间隔 (ms)', 'type': 'number', 'min': 50, 'max': 2000,
             'desc': '加载动画期间纯等待的间隔（只截帧不识别，节省 CPU）'},
        ],
    },
    {
        'key': 'popup',
        'title': '弹窗处理',
        'desc': '随机弹窗旁路处理的防重复与死锁保护（仅使用明确的弹窗角色或标签）',
        'fields': [
            {'key': 'popup_cooldown_ms', 'label': '弹窗冷却时间 (ms)', 'type': 'number', 'min': 0, 'max': 10000,
             'desc': '同一弹窗关闭动作后的冷却窗口；项目响应慢可调大（如 1500），响应快可调小'},
            {'key': 'popup_max_handles', 'label': '单次处理次数上限', 'type': 'number', 'min': 1, 'max': 20,
             'desc': '单次检查点最多处理几个弹窗（防连环弹窗死循环）'},
            {'key': 'popup_max_consecutive', 'label': '连续处理判定阈值', 'type': 'number', 'min': 1, 'max': 20,
             'desc': '连续多少次检查点都在处理弹窗即判定"关不完"并报错'},
            {'key': 'popup_quiet_frames', 'label': '关闭后无弹窗帧数', 'type': 'number', 'min': 1, 'max': 10,
             'desc': '关闭弹窗后连续多少个稳定帧未发现弹窗才恢复主流程'},
            {'key': 'popup_quiet_window_ms', 'label': '关闭后静默时间 (ms)', 'type': 'number', 'min': 0, 'max': 10000,
             'desc': '用于覆盖多层弹窗之间短暂空白，默认至少静默 500ms'},
            {'key': 'popup_poll_ms', 'label': '弹窗复检间隔 (ms)', 'type': 'number', 'min': 30, 'max': 2000,
             'desc': '弹窗关闭、冷却和过渡期间的复检频率'},
            {'key': 'popup_total_timeout_ms', 'label': '单次清场总超时 (ms)', 'type': 'number', 'min': 500, 'max': 60000,
             'desc': '超过时间仍有弹窗或无法确认清场时让当前界面节点失败'},
        ],
    },
    {
        'key': 'matching',
        'title': '识别匹配',
        'desc': '图像/OCR/条件匹配的重试频率与匹配策略',
        'fields': [
            {'key': 'match_poll_ms', 'label': '匹配轮询间隔 (ms)', 'type': 'number', 'min': 30, 'max': 2000,
             'desc': '图像识别/条件判定的重试间隔；慢机器可调大降 CPU'},
            {'key': 'ocr_poll_ms', 'label': 'OCR 轮询间隔 (ms)', 'type': 'number', 'min': 50, 'max': 3000,
             'desc': '文字识别节点的重试间隔（OCR 较慢，默认高于图像匹配）'},
            {'key': 'multi_scale_scales', 'label': '多尺度匹配级别', 'type': 'string',
             'desc': '逗号分隔的缩放比例，如 1.0,0.75,0.5；高 DPI 环境可加 0.6 提高识别率（速度略降）'},
        ],
    },
    {
        'key': 'engine',
        'title': '执行引擎',
        'desc': '环路保护、智能跳转重试、控件查找超时与输入安全策略',
        'fields': [
            {'key': 'max_node_visits', 'label': '节点访问次数上限', 'type': 'number', 'min': 5, 'max': 10000,
             'desc': '单节点最大访问次数，超限触发环路保护终止流程；长时间循环任务可调大'},
            {'key': 'smart_jump_attempts', 'label': '智能跳转重试次数', 'type': 'number', 'min': 1, 'max': 20,
             'desc': '寻路失败/路径未达时的整体重试上限'},
            {'key': 'smart_jump_retry_ms', 'label': '智能跳转重试间隔 (ms)', 'type': 'number', 'min': 100, 'max': 5000,
             'desc': '两次重试之间的等待时间'},
            {'key': 'control_timeout_cap_ms', 'label': '控件查找超时上限 (ms)', 'type': 'number', 'min': 300, 'max': 30000,
             'desc': '控件节点实际查找超时的硬上限（UI 上设置的超时不会超过此值）'},
            {'key': 'allow_physical_fallback', 'label': '允许后台输入失败时回退物理输入', 'type': 'bool',
             'desc': '默认关闭。仅影响PC窗口模式；开启后后台投递明确失败或所选后置验证失败时才回退物理输入。全屏模式固定使用物理输入，模拟器ADB失效时仍会阻止运行。'},
            {'key': 'android_stream_reconnect_attempts', 'label': 'Android高速通道重连次数', 'type': 'number', 'min': 0, 'max': 10,
             'desc': 'scrcpy画面通道断开时按退避重连；超过次数后只终止所属运行实例。'},
        ],
    },
    {
        'key': 'logging',
        'title': '日志与调试',
        'desc': '运行日志保留与调试截图数量',
        'fields': [
            {'key': 'max_logs', 'label': '日志条数上限', 'type': 'number', 'min': 50, 'max': 5000,
             'desc': '单次执行内存保留的日志条数（含截图日志；调大可看更久历史，内存略增）'},
            {'key': 'debug_screenshot_max', 'label': '调试截图保留张数', 'type': 'number', 'min': 1, 'max': 500,
             'desc': 'debug_screenshots 目录最多保留的截图张数（超出自动清理最旧的）'},
        ],
    },
]


def merge_settings(raw: dict | None) -> dict:
    """项目设置与默认值合并：只保留已知键（未知键忽略），缺失用默认值"""
    merged = dict(DEFAULT_PROJECT_SETTINGS)
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k in merged and v is not None:
                merged[k] = v
    return merged
