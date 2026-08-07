// frontend/src/utils/canvasLogger.js
const DEBUG_MODE = true

export const canvasLogger = {
    intent(action, target, meta = {}) {
        if (!DEBUG_MODE) return
        console.log(`%c[INTENT 🖱️] ${action} -> [${target}]`, 'color: #409EFF; font-weight: bold;', meta)
    },

    action(step, message, data = {}) {
        if (!DEBUG_MODE) return
        console.log(`%c[ACTION ⚡] [步骤: ${step}] ${message}`, 'color: #67C23A; font-weight: bold;', data)
    },

    api(url, payload, response) {
        if (!DEBUG_MODE) return
        console.log(`%c[API 🌐] 请求: ${url}`, 'color: #E6A23C; font-weight: bold;', { payload, response })
    },

    transition(stateName, details = {}) {
        if (!DEBUG_MODE) return
        console.log(`%c[TRANSITION 🚀] 状态跃迁: ${stateName}`, 'color: #909399; font-weight: bold;', details)
    },

    commit(action, result = {}) {
        if (!DEBUG_MODE) return
        console.log(`%c[COMMIT 💾] 动作提交: ${action}`, 'color: #4ed19c; font-weight: bold;', result)
    },

    error(action, err) {
        console.error(`%c[ERROR 💥] 异常捕获 [${action}]:`, 'color: #F56C6C; font-weight: bold;', err)
    }
}