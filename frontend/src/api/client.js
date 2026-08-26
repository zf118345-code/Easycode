// frontend/src/api/client.js
// Axios 客户端：开发环境由 Vite 代理 /api，发布环境与 FastAPI 同源。

import axios from 'axios'
import { getWorkspaceIdentity, workspaceHeaders } from './workspaceIdentity'

const client = axios.create({
    // 开发模式：Vite 将 /api 转发到 FastAPI；发布模式：FastAPI 静态托管前端。
    baseURL: '/',
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
})

export function normalizeApiError(error) {
    const response = error?.response
    const status = response?.status
    const payload = response?.data
    const structuredDetail = payload?.detail
    const serverMessage = (
        (typeof structuredDetail === 'string' && structuredDetail)
        || structuredDetail?.message
        || payload?.message
        || payload?.data?.message
    )
    let message = '请求失败'

    if (response) {
        const fallbackByStatus = {
            408: '请求超时，请稍后重试',
            409: '当前状态已变化，请刷新后重试',
            422: '提交的数据不符合要求，请检查后重试',
            429: '操作过于频繁，请稍后重试',
            503: '所需服务暂时不可用，请检查环境后重试',
        }
        message = serverMessage || fallbackByStatus[status] || `服务器错误 (${status})`
    } else if (error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')) {
        message = '请求超时，后端可能正忙或无响应，请稍后重试'
    } else if (error?.request) {
        message = '网络异常，无法连接到服务器'
    } else {
        message = error?.message || '未知错误'
    }

    const normalized = new Error(typeof message === 'string' ? message : '请求失败')
    normalized.name = 'ApiError'
    normalized.kind = response
        ? 'http'
        : ((error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')) ? 'timeout' : 'network')
    normalized.original = error
    normalized.status = status
    normalized.code = payload?.code ?? error?.code
    normalized.detail = payload?.detail
    normalized.details = payload?.data ?? structuredDetail
    normalized.retryAfter = response?.headers?.['retry-after'] ?? null
    normalized.retryable = !response || status === 408 || status === 429 || status >= 500
    return normalized
}

client.interceptors.request.use(
    (config) => {
        // 保存队列可以显式携带旧工作区身份；没有显式值时使用当前身份。
        // 切换后旧 generation 会被后端拒绝，绝不会写入新项目。
        const identity = config.workspaceIdentity || getWorkspaceIdentity()
        config.headers = { ...config.headers, ...workspaceHeaders(identity) }
        delete config.workspaceIdentity
        return config
    },
    (error) => {
        return Promise.reject(error)
    }
)

// 统一将 Axios 错误转换为用户可读错误。
client.interceptors.response.use(
    (response) => {
        return response.data
    },
    (error) => Promise.reject(normalizeApiError(error))
)

export default client
