// frontend/src/utils/nodeDefaults.js
// 节点默认值（前端侧单一事实源，与后端 core/params/base/defaults.py 对齐）：
//   一般节点默认 延迟 200ms 执行、循环 1 次；
//   其余参数默认值来自后端 /api/params 的 schema default（图像识别 85%/3000ms/录入区域/识别后点击…）。

export const NODE_DEFAULTS = {
    delayBefore: 200,   // 节点执行前延迟 (ms)
    loopCount: 1        // 循环次数
}

/**
 * 按后端 schema 的 default 构建节点初始参数（隐藏字段跳过，由创建处特判生成）
 * @param {string} nodeType 节点类型
 * @param {Object} paramsDefinitions 后端 /api/params 定义（projectStore.paramsDefinitions）
 * @returns {Object} 初始 params
 */
export function buildNodeDefaultParams(nodeType, paramsDefinitions) {
    const defs = (paramsDefinitions && paramsDefinitions[nodeType] && paramsDefinitions[nodeType].params) || {}
    const params = {}
    for (const [key, config] of Object.entries(defs)) {
        if (config.hidden) continue
        if (config.type === 'list_int2' || config.type === 'list_int4') {
            params[key] = [0, 0, 0, 0].slice(0, config.type === 'list_int2' ? 2 : 4)
        } else if (config.type === 'list_dict') {
            params[key] = []
        } else if (config.type === 'dict') {
            const subDefaults = {}
            for (const [subKey, subConfig] of Object.entries(config.sub || {})) {
                if (subConfig.default !== undefined) {
                    subDefaults[subKey] = Array.isArray(subConfig.default) ? [...subConfig.default] : subConfig.default
                }
            }
            if (Object.keys(subDefaults).length) {
                params[key] = subDefaults
            }
        } else if (config.default !== undefined) {
            params[key] = Array.isArray(config.default) ? [...config.default] : config.default
        }
    }
    return params
}
