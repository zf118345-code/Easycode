// frontend/src/api/client.js
import axios from 'axios'

const client = axios.create({
    baseURL: '', // Vite proxy 代理处理 /api
    timeout: 15000
})

// 响应拦截器：统一提取数据与错误处理
client.interceptors.response.use(
    response => response.data,
    error => {
        const detail = error.response?.data?.detail || error.message || '网络请求服务异常'
        return Promise.reject(new Error(detail))
    }
)

export default client