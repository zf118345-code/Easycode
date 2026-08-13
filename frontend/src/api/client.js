// frontend/src/api/client.js
// Axios 封装：统一 baseURL、超时、错误处理、Vite 代理对齐
// 修复：该文件此前缺失，导致 blueprintApi.js 导入失败，前端全部 API 不可用

import axios from 'axios'

const client = axios.create({
    // 开发模式下 Vite 代理会将以 /api 开头的请求转发到后端 http://127.0.0.1:8000
    // 生产模式下由 FastAPI 静态托管，同源访问
    baseURL: '/',
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json'
    }
})

// 请求拦截器：可在此添加 token 等
client.interceptors.request.use(
    (config) => {
        return config
    },
    (error) => {
        return Promise.reject(error)
    }
)

// 响应拦截器：统一错误处理
client.interceptors.response.use(
    (response) => {
        return response.data
    },
    (error) => {
        // 统一错误格式
        let message = '请求失败'
        if (error.response) {
            // HTTP 错误（4xx / 5xx）
            const status = error.response.status
            const detail = error.response.data?.detail || error.response.data?.message
            message = detail || `服务器错误 (${status})`
        } else if (error.request) {
            // 网络错误（无响应）
            message = '网络错误：无法连接到服务器'
        } else {
            message = error.message || '未知错误'
        }

        // 保留原始 Error 对象，但附加友好消息
        const wrappedError = new Error(message)
        wrappedError.original = error
        wrappedError.status = error.response?.status
        wrappedError.detail = error.response?.data?.detail

        return Promise.reject(wrappedError)
    }
)

export default client