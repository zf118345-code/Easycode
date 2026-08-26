<!-- frontend/src/components/ProjectSettingsDialog.vue
  项目设置（顶部「编辑 (E) → 项目设置」）：
  - 全局生效的引擎参数，以项目为单位存储（project.json 的 settings 段）
  - 按类型分组展示（加载与等待 / 弹窗处理 / 识别匹配 / 执行引擎 / 日志与调试）
  - 分组与字段元数据由后端下发（core/settings.py SETTINGS_GROUPS），前端自动渲染
-->
<template>
    <el-dialog
        v-model="dialogVisible"
        title="项目设置"
        width="760px"
        append-to-body
        :close-on-click-modal="false"
        custom-class="project-settings-dialog">
        <div v-loading="loading" class="ps-body">
            <div class="ps-tip">
                以下参数<b>以当前项目为单位全局生效</b>（保存后立即作用于本项目所有流程）。
                修改后点击「保存」；未配置的项使用默认值。
            </div>

            <div v-for="group in groups" :key="group.key" class="ps-group">
                <div class="ps-group-head">
                    <span class="ps-group-title">{{ group.title }}</span>
                    <span class="ps-group-desc">{{ group.desc }}</span>
                </div>
                <div class="ps-fields">
                    <div v-for="field in group.fields" :key="field.key" class="ps-field">
                        <div class="ps-field-label">{{ field.label }}</div>
                        <div class="ps-field-control">
                            <el-input-number
                                v-if="field.type === 'number'"
                                v-model="localSettings[field.key]"
                                :min="field.min" :max="field.max"
                                controls-position="right"
                                style="width: 180px;" size="small" />
                            <el-switch
                                v-else-if="field.type === 'bool'"
                                v-model="localSettings[field.key]"
                                inline-prompt
                                active-text="允许"
                                inactive-text="禁止" />
                            <el-input
                                v-else
                                v-model="localSettings[field.key]"
                                size="small" style="width: 220px;" />
                        </div>
                        <div class="ps-field-desc">{{ field.desc }}</div>
                    </div>
                </div>
            </div>
        </div>

        <template #footer>
            <div class="ps-footer">
                <el-button size="small" @click="restoreDefaults">恢复默认</el-button>
                <el-button size="small" @click="dialogVisible = false">取消</el-button>
                <el-button type="primary" size="small" :loading="saving" :disabled="loading" @click="handleSave">保存</el-button>
            </div>
        </template>
    </el-dialog>
</template>

<script setup>
    import { ref, reactive, computed, watch } from 'vue'
    import { ElMessage } from 'element-plus'
    import client from '@/api/client'
    import { useIdeStore } from '@/stores'

    const props = defineProps({
        modelValue: { type: Boolean, default: false }
    })

    const emit = defineEmits(['update:modelValue'])

    const store = useIdeStore()

    const dialogVisible = computed({
        get: () => props.modelValue,
        set: (val) => emit('update:modelValue', val)
    })

    const groups = ref([])
    const localSettings = reactive({})
    const loading = ref(false)
    const saving = ref(false)

    const loadSettings = async () => {
        if (!store.currentProjectPath) return
        loading.value = true
        try {
            const res = await client.get('/api/project/settings', {
                params: { project_path: store.currentProjectPath }
            })
            const raw = res?.data || res
            const settings = raw.settings || {}
            groups.value = raw.groups || []
            Object.keys(localSettings).forEach(k => delete localSettings[k])
            Object.assign(localSettings, settings)
        } catch (err) {
            ElMessage.error('加载项目设置失败: ' + (err.message || err))
        } finally {
            loading.value = false
        }
    }

    const restoreDefaults = () => {
        groups.value.forEach(g => {
            (g.fields || []).forEach(f => {
                localSettings[f.key] = undefined
            })
        })
        ElMessage.info('已清空自定义值，保存后将使用默认值')
    }

    const handleSave = async () => {
        if (!store.currentProjectPath) return
        saving.value = true
        try {
            // 独立设置接口和项目元数据自动保存写同一个 project.json。
            // 必须先排空旧快照，随后把后端结果同步回 store，避免下一次
            // 自动保存使用旧 settings 覆盖刚刚的设置。
            await store.flushPendingSaves()
            const payload = {}
            Object.entries(localSettings).forEach(([k, v]) => {
                if (v !== undefined && v !== null && v !== '') payload[k] = v
            })
            const result = await client.put('/api/project/settings', {
                project_path: store.currentProjectPath,
                settings: payload
            })
            store.blueprint.settings = { ...(result?.settings || payload) }
            ElMessage.success('项目设置已保存（当前项目全局生效）')
            dialogVisible.value = false
        } catch (err) {
            ElMessage.error('保存项目设置失败: ' + (err.message || err))
        } finally {
            saving.value = false
        }
    }

    watch(() => props.modelValue, (val) => {
        if (val) loadSettings()
    }, { immediate: false })
</script>

<style scoped>
    .ps-body {
        max-height: 62vh;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .ps-tip {
        font-size: 12px;
        color: var(--el-text-color-secondary);
        padding: 10px 12px;
        background: var(--el-fill-color-light);
        border-radius: 8px;
        border: 1px solid var(--el-border-color-lighter);
    }

    .ps-group {
        border: 1px solid var(--el-border-color-light);
        border-radius: 8px;
        overflow: hidden;
        background: var(--el-fill-color-blank);
    }

    .ps-group-head {
        padding: 10px 14px;
        background: var(--el-fill-color-light);
        border-bottom: 1px solid var(--el-border-color-lighter);
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .ps-group-title {
        font-size: 13px;
        font-weight: 600;
        color: var(--el-color-primary);
    }

    .ps-group-desc {
        font-size: 11px;
        color: var(--el-text-color-secondary);
    }

    .ps-fields {
        padding: 4px 14px;
    }

    .ps-field {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 9px 0;
        border-bottom: 1px dashed var(--el-border-color-lighter);
    }

    .ps-field:last-child {
        border-bottom: none;
    }

    .ps-field-label {
        width: 170px;
        flex-shrink: 0;
        font-size: 12px;
        color: var(--el-text-color-primary);
    }

    .ps-field-control {
        flex-shrink: 0;
    }

    .ps-field-desc {
        flex: 1;
        font-size: 11px;
        color: var(--el-text-color-secondary);
        line-height: 1.5;
    }

    .ps-footer {
        display: flex;
        justify-content: flex-end;
        gap: 4px;
    }
</style>
