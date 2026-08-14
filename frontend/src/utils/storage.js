// frontend/src/utils/storage.js
// 统一的 localStorage 封装，支持 JSON 序列化、命名空间、TTL 过期

const DEFAULT_NAMESPACE = 'easycode'

function buildKey(key, namespace) {
    return namespace ? `${namespace}:${key}` : key
}

export const storage = {
    /**
     * 存储值（自动 JSON 序列化）
     * @param {string} key - 键名
     * @param {*} value - 值
     * @param {object} options - { namespace, ttl (毫秒) }
     */
    set(key, value, options = {}) {
        try {
            const ns = options.namespace ?? DEFAULT_NAMESPACE
            const fullKey = buildKey(key, ns)
            const data = {
                value: value,
                timestamp: Date.now()
            }
            if (options.ttl) {
                data.expiresAt = Date.now() + options.ttl
            }
            localStorage.setItem(fullKey, JSON.stringify(data))
            return true
        } catch (err) {
            console.error('[storage] set 失败:', key, err)
            return false
        }
    },

    /**
     * 读取值（自动 JSON 反序列化）
     * @param {string} key - 键名
     * @param {*} defaultValue - 默认值
     * @param {object} options - { namespace }
     * @returns {*}
     */
    get(key, defaultValue = null, options = {}) {
        try {
            const ns = options.namespace ?? DEFAULT_NAMESPACE
            const fullKey = buildKey(key, ns)
            const raw = localStorage.getItem(fullKey)
            if (raw === null) return defaultValue

            const data = JSON.parse(raw)

            // TTL 过期检查
            if (data.expiresAt && Date.now() > data.expiresAt) {
                localStorage.removeItem(fullKey)
                return defaultValue
            }

            return data.value !== undefined ? data.value : data
        } catch (err) {
            console.error('[storage] get 失败:', key, err)
            return defaultValue
        }
    },

    /**
     * 移除值
     */
    remove(key, options = {}) {
        try {
            const ns = options.namespace ?? DEFAULT_NAMESPACE
            localStorage.removeItem(buildKey(key, ns))
        } catch (err) {
            console.error('[storage] remove 失败:', key, err)
        }
    },

    /**
     * 清除命名空间下的所有键
     */
    clearNamespace(namespace = DEFAULT_NAMESPACE) {
        try {
            const prefix = `${namespace}:`
            const keysToRemove = []
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i)
                if (key && key.startsWith(prefix)) {
                    keysToRemove.push(key)
                }
            }
            keysToRemove.forEach(k => localStorage.removeItem(k))
        } catch (err) {
            console.error('[storage] clearNamespace 失败:', namespace, err)
        }
    },

    /**
     * 获取命名空间下所有键
     */
    keys(namespace = DEFAULT_NAMESPACE) {
        try {
            const prefix = `${namespace}:`
            const result = []
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i)
                if (key && key.startsWith(prefix)) {
                    result.push(key.substring(prefix.length))
                }
            }
            return result
        } catch (err) {
            console.error('[storage] keys 失败:', namespace, err)
            return []
        }
    },

    /**
     * 直接存储原始字符串（不经 JSON 序列化，向后兼容）
     */
    setRaw(key, value) {
        try {
            localStorage.setItem(key, value)
        } catch (err) {
            console.error('[storage] setRaw 失败:', key, err)
        }
    },

    /**
     * 直接读取原始字符串
     */
    getRaw(key) {
        try {
            return localStorage.getItem(key)
        } catch (err) {
            console.error('[storage] getRaw 失败:', key, err)
            return null
        }
    }
}

export default storage
