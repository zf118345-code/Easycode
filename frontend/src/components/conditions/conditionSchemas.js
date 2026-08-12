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
                placeholder: "请输入固定文本或变量如 {var_name}"
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
                type: "variable",  // ⚡ 保留强变量选择：比较变量必须选择已有变量名
                default: "",
                label: "比较变量",
                placeholder: "请选择变量名"
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
                placeholder: "请输入数值、常数或 {var_name}"
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
    }
}