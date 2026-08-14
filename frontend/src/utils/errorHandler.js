// frontend/src/utils/errorHandler.js
// 统一错误处理基础设施，配合 Element Plus ElMessage 和 logger

import { ElMessage, ElMessageBox } from 'element-plus'
import { logger } from './logger'

// 错误类型枚举
export const ERROR_TYPES = {
    NETWORK: 'network',       // 网络请求失败
    VALIDATION: 'validation', // 数据校验失败
    PERMISSION: 'permission', // 权限不足
    NOT_FOUND: 'not_found',   // 资源不存在
    SERVER: 'server',         // 服务器内部错误
    UNKNOWN: 'unknown'        // 未知错误
}

// 错误严重级别
export const ERROR_SEVERITY = {
    INFO: 'info',
    WARNING: 'warning',
    ERROR: 'error',
    FATAL: 'fatal'
}

/**
 * 从 HTTP 错误中提取错误类型
 */
function classifyError(error) {
    if (!error) return ERROR_TYPES.UNKNOWN

    const status = error.status || error.response?.status
    if (!status && !error.response) return ERROR_TYPES.NETWORK
    if (status === 400) return ERROR_TYPES.VALIDATION
    if (status === 401 || status === 403) return ERROR_TYPES.PERMISSION
    if (status === 404) return ERROR_TYPES.NOT_FOUND
    if (status >= 500) return ERROR_TYPES.SERVER
    return ERROR_TYPES.UNKNOWN
}

/**
 * 获取用户友好的错误消息
 */
function getUserMessage(error, fallback = '操作失败') {
    if (!error) return fallback
    if (typeof error === 'string') return error
    return error.message || error.detail || fallback
}

/**
 * 统一错误处理
 * @param {Error} error - 错误对象
 * @param {object} options - { tag, silent, severity, showRetry }
 */
export function handleError(error, options = {}) {
    const tag = options.tag || 'Error'
    const errorType = classifyError(error)
    const message = getUserMessage(error, options.fallback || '操作失败')

    // 记录日志
    if (options.severity === ERROR_SEVERITY.FATAL) {
        logger.error(tag, message, error)
    } else if (options.severity === ERROR_SEVERITY.WARNING) {
        logger.warn(tag, message, error)
    } else {
        logger.error(tag, message, error)
    }

    // 静默模式：仅记录日志不弹窗
    if (options.silent) return { type: errorType, message }

    // 显示 Toast
    const toastType = errorType === ERROR_TYPES.VALIDATION ? 'warning' : 'error'
    ElMessage({
        message: message,
        type: toastType,
        duration: options.duration || 3000,
        grouping: true
    })

    return { type: errorType, message }
}

/**
 * 异步操作包装器，自动捕获错误
 * @param {Function} asyncFn - 异步函数
 * @param {object} options - handleError options
 * @returns {Promise<{success: boolean, data?: *, error?: *}>}
 */
export async function withErrorHandling(asyncFn, options = {}) {
    try {
        const data = await asyncFn()
        return { success: true, data }
    } catch (error) {
        handleError(error, options)
        return { success: false, error }
    }
}

/**
 * 确认对话框
 * @param {string} message - 确认消息
 * @param {object} options - { title, type }
 * @returns {Promise<boolean>}
 */
export async function confirmAction(message, options = {}) {
    try {
        await ElMessageBox.confirm(message, options.title || '确认操作', {
            confirmButtonText: options.confirmText || '确定',
            cancelButtonText: options.cancelText || '取消',
            type: options.type || 'warning'
        })
        return true
    } catch {
        return false
    }
}

/**
 * 安全执行同步函数，捕获异常
 */
export function safeCall(fn, options = {}) {
    try {
        return fn()
    } catch (error) {
        handleError(error, options)
        return null
    }
}

export default {
    handleError,
    withErrorHandling,
    confirmAction,
    safeCall,
    ERROR_TYPES,
    ERROR_SEVERITY
}
