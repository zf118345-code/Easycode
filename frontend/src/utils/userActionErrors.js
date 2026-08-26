import { ElMessage } from 'element-plus'

export function isUserCancellation(error) {
    return error === 'cancel'
        || error === 'close'
        || error?.type === 'cancel'
        || error?.type === 'close'
}

export function notifyActionError(error, fallback = '操作失败') {
    if (isUserCancellation(error)) return false
    ElMessage.error(error?.message || error?.detail || fallback)
    return true
}

