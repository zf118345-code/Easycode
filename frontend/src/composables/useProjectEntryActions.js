import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@/stores'

function projectErrorMessage(result, fallback) {
    return result?.inspection?.errors?.join('；') || fallback
}

export function useProjectEntryActions() {
    const projectStore = useProjectStore()

    const openProjectPath = async (path, { successMessage = true } = {}) => {
        if (!String(path || '').trim()) return false
        try {
            let result = await projectStore.loadProjectByPath(String(path).trim())
            const inspection = result?.inspection
            if (!result?.workspace && inspection?.status === 'empty') {
                await ElMessageBox.confirm('这是一个空文件夹，是否在其中创建 EasyCode 项目？', '初始化项目', {
                    confirmButtonText: '创建项目', cancelButtonText: '取消', type: 'info'
                })
                result = await projectStore.loadProjectByPath(path, {
                    initialize: true,
                    projectName: inspection?.project_name || ''
                })
            } else if (!result?.workspace && inspection?.status === 'uninitialized') {
                await ElMessageBox.confirm(
                    '该文件夹已有其他内容。确认后只新增 EasyCode 项目文件，不会覆盖现有内容。',
                    '初始化非空文件夹',
                    { confirmButtonText: '确认初始化', cancelButtonText: '取消', type: 'warning' }
                )
                result = await projectStore.loadProjectByPath(path, {
                    initialize: true,
                    confirmNonempty: true
                })
            }
            if (!result?.workspace) throw new Error(projectErrorMessage(result, '项目无法打开'))
            if (successMessage) ElMessage.success(`已打开项目：${projectStore.currentProjectName}`)
            if (result?.inspection?.warnings?.length) ElMessage.warning(result.inspection.warnings.join('；'))
            return true
        } catch (error) {
            if (error === 'cancel' || error === 'close') return false
            ElMessage.error(`打开项目失败：${error?.message || error}`)
            return false
        }
    }

    const chooseAndOpenProject = async () => {
        try {
            const path = await projectStore.chooseProjectFolder()
            if (!path) return false
            return await openProjectPath(path)
        } catch (error) {
            ElMessage.error(error?.message || '无法打开文件夹选择器')
            return false
        }
    }

    return { openProjectPath, chooseAndOpenProject }
}
