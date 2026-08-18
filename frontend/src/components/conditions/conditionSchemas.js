// frontend/src/components/conditions/conditionSchemas.js

export const CONDITION_SCHEMAS = {
    // 1. 屏幕/区域存在指定图片 (图像判定)
    image_exists: {
        label: "屏幕/区域存在指定图片",
        params: {
            exist_mode: {
                type: "select",
                label: "判定要求",
                default: "exists",
                options: [
                    { label: "屏幕/区域存在该图片", value: "exists" },
                    { label: "屏幕/区域不存在该图片", value: "not_exists" }
                ]
            },
            image_source: {
                type: "file",
                default: "",
                label: "模板图片"
            },
            gray_scale: {
                type: "bool",
                default: true,
                label: "去除背景干扰 (灰度处理)"
            },
            gray_threshold: {
                type: "int",
                default: 127,
                label: "二值化灰度阈值 (0-255，调节至轮廓最清晰)",
                min: 0,
                max: 255,
                step: 1,
                visible_if: {
                    field: "gray_scale",
                    operator: "eq",
                    value: true
                }
            },
            threshold: {
                type: "int",
                default: 85,
                label: "匹配相似度",
                suffix: "%",
                min: 1,
                max: 100
            },
            region_type: {
                type: "select",
                options: [
                    { value: "fullwindow", label: "整个工作面板" },
                    { value: "recorded", label: "录制时的坐标区域" },
                    { value: "custom", label: "自定义区域" }
                ],
                default: "recorded",
                label: "匹配区域"
            },
            region_value: {
                type: "list_int4_picker",
                default: [0, 0, 0, 0],
                label: "匹配区域坐标",
                visible_if: {
                    field: "region_type",
                    operator: "in",
                    value: ["recorded", "custom"]
                }
            }
        }
    },

    // 2. 屏幕/区域包含指定文本 (OCR 判定)
    text_contains: {
        label: "屏幕/区域包含指定文本 (OCR)",
        params: {
            exist_mode: {
                type: "select",
                label: "判定要求",
                default: "contains",
                options: [
                    { label: "区域文本包含目标内容", value: "contains" },
                    { label: "区域文本不包含目标内容", value: "not_contains" },
                    { label: "区域文本完全等于目标内容", value: "equals" }
                ]
            },
            target_text: {
                type: "str",  // ⚡ 修正：改为常规字符串输入框，方便打字
                default: "",
                label: "期望对比的文本内容",
                placeholder: "请输入固定文本或变量如 $var{name}"
            },
            image_source: {
                type: "file",
                default: "",
                label: "OCR 文本视角模板"
            },
            gray_scale: {
                type: "bool",
                default: true,
                label: "去除背景干扰 (灰度处理)"
            },
            gray_threshold: {
                type: "int",
                default: 127,
                label: "二值化灰度阈值 (0-255，调节至文字最清晰)",
                min: 0,
                max: 255,
                step: 1,
                visible_if: {
                    field: "gray_scale",
                    operator: "eq",
                    value: true
                }
            },
            region_type: {
                type: "select",
                options: [
                    { value: "fullwindow", label: "整个工作面板" },
                    { value: "recorded", label: "录制时的坐标区域" },
                    { value: "custom", label: "自定义区域" }
                ],
                default: "recorded",
                label: "识别区域"
            },
            region_value: {
                type: "list_int4_picker",
                default: [0, 0, 0, 0],
                label: "识别区域坐标",
                visible_if: {
                    field: "region_type",
                    operator: "in",
                    value: ["recorded", "custom"]
                }
            }
        }
    },

    // 3. 变量数值/逻辑比较
    variable_check: {
        label: "变量数值/逻辑比较",
        params: {
            variable_name: {
                type: "str",  // 统一普通输入框（$var{} 语法）
                default: "",
                label: "比较变量",
                placeholder: "填写变量名，如 $var{coin_num}"
            },
            operator: {
                type: "select",
                default: "eq",
                label: "比较运算符",
                options: [
                    { label: "等于 (==)", value: "eq" },
                    { label: "不等于 (!=)", value: "ne" },
                    { label: "大于 (>)", value: "gt" },
                    { label: "大于等于 (>=)", value: "gte" },
                    { label: "小于 (<)", value: "lt" },
                    { label: "小于等于 (<=)", value: "lte" },
                    { label: "包含 (Contains)", value: "contains" }
                ]
            },
            compare_value: {
                type: "str",  // ⚡ 修正：改为常规输入框，既可填数字字符串也可引用变量
                default: "",
                label: "目标对比值",
                placeholder: "请输入数值、常数或 $var{变量名}"
            }
        }
    },

    // 4. 指定窗口状态 (存在/激活/关闭)
    window_state: {
        label: "指定窗口状态",
        params: {
            window_title: {
                type: "window_select",
                default: "",
                label: "目标窗口名称"
            },
            state_check: {
                type: "select",
                default: "exists",
                label: "期望窗口状态",
                options: [
                    { label: "窗口存在", value: "exists" },
                    { label: "窗口不存在", value: "not_exists" },
                    { label: "窗口处于前台激活", value: "active" }
                ]
            }
        }
    },

    // 5. 本地文件/文件夹是否存在
    file_exists: {
        label: "本地文件/文件夹状态",
        params: {
            file_path: {
                type: "str",
                default: "",
                label: "文件/目录绝对路径",
                placeholder: "如 D:/data/config.json"
            },
            check_type: {
                type: "select",
                default: "exists",
                label: "检查模式",
                options: [
                    { label: "文件或目录存在", value: "exists" },
                    { label: "文件或目录不存在", value: "not_exists" }
                ]
            }
        }
    },

    // 6. 控件存在性（存在控件/不存在控件，捕获控件自动填充名称）
    control_exists: {
        label: "存在/不存在控件",
        params: {
            exist_mode: {
                type: "select",
                default: "exists",
                label: "判定要求",
                options: [
                    { label: "存在控件", value: "exists" },
                    { label: "不存在控件", value: "not_exists" }
                ]
            },
            target: {
                type: "capture_str",
                default: "",
                label: "控件名称",
                placeholder: "点击「捕获控件」自动填入"
            },
            window_title: {
                type: "str",
                default: "",
                label: "目标窗口标题",
                placeholder: "留空则在所有窗口中查找"
            },
            index: {
                type: "int",
                default: 0,
                min: 0,
                label: "匹配序号"
            },
            timeout: {
                type: "int",
                default: 3000,
                min: 100,
                step: 100,
                suffix: "ms",
                label: "匹配超时时长"
            }
        }
    }
}

// ===== 页面特征 schema（page_state 复合特征，条件列表编辑器使用） =====
// 复用通用条件 schema，并追加页面特征专属字段：组合方式 / 结果取反

const PAGE_FEATURE_COMMON = {
    combine_mode: {
        type: "select",
        label: "与上一特征组合方式",
        // 默认空 = 跟随全局「特征组合模式」；显式选择 and/or 才覆盖全局
        default: "",
        options: [
            { label: "跟随全局 (默认)", value: "" },
            { label: "且 (AND)", value: "and" },
            { label: "或 (OR)", value: "or" }
        ]
    },
    negate: {
        type: "bool",
        label: "结果取反（描述不存在该特征）",
        default: false
    }
}

export const PAGE_FEATURE_SCHEMAS = {
    image_exists: {
        label: "页面包含指定图片（图像特征）",
        params: {
            ...CONDITION_SCHEMAS.image_exists.params,
            ...PAGE_FEATURE_COMMON
        }
    },
    text_contains: {
        label: "页面包含指定文本（文本特征）",
        params: {
            ...CONDITION_SCHEMAS.text_contains.params,
            ...PAGE_FEATURE_COMMON
        }
    },
    control_exists: {
        label: "页面包含/不包含指定控件（控件特征）",
        params: {
            exist_mode: {
                type: "select",
                default: "exists",
                label: "判定要求",
                options: [
                    { label: "存在控件", value: "exists" },
                    { label: "不存在控件", value: "not_exists" }
                ]
            },
            target: {
                type: "capture_str",
                default: "",
                label: "控件名称",
                placeholder: "点击「捕获控件」自动填入"
            },
            ...PAGE_FEATURE_COMMON
        }
    }
}