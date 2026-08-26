<template>
    <el-dialog
        :model-value="modelValue"
        title="新建项目"
        width="560px"
        append-to-body
        :close-on-click-modal="false"
        @update:model-value="emit('update:modelValue', $event)"
        @opened="focusPathInput">
        <div class="project-create-content">
            <label for="project-directory">项目目录</label>
            <el-input
                id="project-directory"
                ref="pathInputRef"
                v-model="projectPath"
                clearable
                placeholder="例如 D:\PycharmProjects\tuiyan"
                @keyup.enter="createProject">
                <template #append>
                    <el-button title="选择项目文件夹" :disabled="busy" @click="chooseFolder">
                        <FolderOpen :size="16" />
                    </el-button>
                </template>
            </el-input>
            <div class="project-name-preview">
                <Folder :size="14" />
                <span>项目名称</span>
                <strong>{{ inferredProjectName || '等待选择目录' }}</strong>
            </div>
            <p class="project-create-help">
                目录不存在时会自动创建；项目名称默认使用路径最后一级文件夹名称。
            </p>
        </div>
        <template #footer>
            <el-button :disabled="busy" @click="emit('update:modelValue', false)">取消</el-button>
            <el-button type="primary" :loading="busy" :disabled="!inferredProjectName" @click="createProject">
                创建项目
            </el-button>
        </template>
    </el-dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Folder, FolderOpen } from 'lucide-vue-next'
import { useProjectStore } from '@/stores'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'created'])
const projectStore = useProjectStore()
const projectPath = ref('')
const pathInputRef = ref(null)
const busy = ref(false)

const normalizedPath = computed(() => projectPath.value.trim().replace(/[\\/]+$/, ''))
const inferredProjectName = computed(() => normalizedPath.value.split(/[\\/]/).filter(Boolean).pop() || '')

watch(() => props.modelValue, visible => {
    if (visible) projectPath.value = ''
})

const focusPathInput = () => nextTick(() => pathInputRef.value?.focus?.())

const chooseFolder = async () => {
    try {
        const path = await projectStore.chooseProjectFolder()
        if (path) projectPath.value = path
    } catch (error) {
        ElMessage.error(error?.message || '无法打开文件夹选择器')
    }
}

const createProject = async () => {
    const path = normalizedPath.value
    const projectName = inferredProjectName.value
    if (!path || !projectName || busy.value) return ElMessage.warning('请输入或选择项目目录')
    busy.value = true
    try {
        const inspection = await projectStore.inspectProject(path)
        if (['valid', 'read_only'].includes(inspection?.status)) {
            return ElMessage.warning('该目录已经是 EasyCode 项目，请使用“打开项目”')
        }
        if (inspection?.status === 'invalid') {
            throw new Error(inspection.errors?.join('；') || '目录包含冲突或损坏的 EasyCode 文件')
        }
        let confirmNonempty = false
        if (inspection?.status === 'uninitialized') {
            await ElMessageBox.confirm(
                '该目录已有其他内容。创建项目只会新增 EasyCode 文件，不会覆盖原文件。',
                '确认初始化非空目录',
                { confirmButtonText: '继续创建', cancelButtonText: '取消', type: 'warning' }
            )
            confirmNonempty = true
        }
        const result = await projectStore.loadProjectByPath(path, {
            initialize: true,
            confirmNonempty,
            projectName
        })
        if (!result?.workspace) throw new Error(result?.inspection?.errors?.join('；') || '项目创建失败')
        emit('update:modelValue', false)
        emit('created', result)
        ElMessage.success(`已创建项目：${projectStore.currentProjectName}`)
    } catch (error) {
        if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.message || '项目创建失败')
    } finally {
        busy.value = false
    }
}
</script>

<style scoped>
.project-create-content { display: flex; flex-direction: column; gap: 10px; }
.project-create-content > label { color: var(--el-text-color-regular); font-size: 12px; font-weight: 600; }
.project-name-preview { display: flex; align-items: center; gap: 7px; min-height: 30px; padding: 7px 10px; border-radius: 7px; background: var(--el-fill-color-light); color: var(--el-text-color-secondary); font-size: 12px; }
.project-name-preview strong { margin-left: auto; color: var(--el-text-color-primary); }
.project-create-help { color: var(--el-text-color-placeholder); font-size: 11px; line-height: 1.6; }
</style>
