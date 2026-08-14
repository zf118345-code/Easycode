"""统一错误码定义"""


class ErrorCode:
    """标准错误码常量"""

    # 成功
    SUCCESS = 0

    # 通用错误 (1xx)
    INTERNAL_ERROR = 100
    BAD_REQUEST = 101
    NOT_FOUND = 102
    METHOD_NOT_ALLOWED = 103
    VALIDATION_ERROR = 104

    # 认证授权 (2xx)
    UNAUTHORIZED = 200
    FORBIDDEN = 201
    TOKEN_EXPIRED = 202

    # 资源相关 (3xx)
    RESOURCE_NOT_FOUND = 300
    RESOURCE_CONFLICT = 301
    RESOURCE_LOCKED = 302

    # 服务相关 (4xx)
    SERVICE_UNAVAILABLE = 400
    SERVICE_TIMEOUT = 401
    DEPENDENCY_MISSING = 402

    # 业务逻辑 (5xx)
    BLUEPRINT_LOAD_FAILED = 500
    BLUEPRINT_SAVE_FAILED = 501
    TASK_NOT_FOUND = 502
    EXECUTION_FAILED = 503
    EXECUTION_NOT_FOUND = 504
    PROJECT_INVALID = 505

    # 文件操作 (6xx)
    FILE_NOT_FOUND = 600
    FILE_PERMISSION_DENIED = 601
    FILE_TOO_LARGE = 602
    PATH_TRAVERSAL_DETECTED = 603


ERROR_MESSAGES = {
    ErrorCode.SUCCESS: 'success',
    ErrorCode.INTERNAL_ERROR: '内部服务器错误',
    ErrorCode.BAD_REQUEST: '请求参数错误',
    ErrorCode.NOT_FOUND: '资源不存在',
    ErrorCode.VALIDATION_ERROR: '数据校验失败',
    ErrorCode.UNAUTHORIZED: '未授权访问',
    ErrorCode.FORBIDDEN: '禁止访问',
    ErrorCode.SERVICE_UNAVAILABLE: '服务不可用',
    ErrorCode.BLUEPRINT_LOAD_FAILED: '蓝图加载失败',
    ErrorCode.BLUEPRINT_SAVE_FAILED: '蓝图保存失败',
    ErrorCode.TASK_NOT_FOUND: '任务不存在',
    ErrorCode.EXECUTION_FAILED: '执行失败',
    ErrorCode.EXECUTION_NOT_FOUND: '执行记录不存在',
    ErrorCode.PROJECT_INVALID: '项目路径无效',
    ErrorCode.FILE_NOT_FOUND: '文件不存在',
    ErrorCode.PATH_TRAVERSAL_DETECTED: '检测到路径遍历攻击',
}
