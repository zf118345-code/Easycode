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
    (error) => {
        let message = '请求失败'
        if (error.response) {
            const status = error.response.status
            const detail = error.response.data?.detail || error.response.data?.message
            message = detail || `服务器错误 (${status})`
        } else if (error.code === 'ECONNABORTED' || /timeout/i.test(error.message || '')) {
            message = '请求超时，后端可能正忙或无响应，请稍后重试'
        } else if (error.request) {
            message = '网络异常，无法连接到服务器'
        } else {
            message = error.message || '未知错误'
        }

        // 保留原始错误，向调用方暴露统一的人类可读消息。
        const wrappedError = new Error(message)
        wrappedError.original = error
        wrappedError.status = error.response?.status
        wrappedError.detail = error.response?.data?.detail

        return Promise.reject(wrappedError)
    }
)

export default client
