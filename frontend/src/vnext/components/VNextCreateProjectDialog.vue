<template>
    <div v-if="open" class="dialog-backdrop" @mousedown.self="$emit('close')">
        <section class="create-dialog" role="dialog" aria-modal="true" aria-labelledby="create-project-title" tabindex="-1" @keydown="trapDialogFocus" @keydown.esc.stop="$emit('close')">
            <header><div><h2 id="create-project-title">新建项目</h2><p>选择一个不存在或完全空白的目录。</p></div><VNextIconButton label="关闭" @click="$emit('close')"><X /></VNextIconButton></header>
            <div class="create-body">
                <div class="project-path-row app-form-row">
                    <label for="vnext-project-path" class="app-form-label">项目目录</label>
                    <input
                        id="vnext-project-path"
                        ref="pathInput"
                        v-model="projectPath"
                        class="app-form-control"
                        placeholder="例如 D:\PycharmProjects\MyAutomation"
                        autocomplete="off"
                        :aria-invalid="error ? 'true' : undefined"
                        :aria-describedby="error ? 'create-project-error' : inferredName ? 'create-project-preview' : undefined"
                        @keyup.enter="createProject"
                    />
                    <VNextIconButton class="app-field-action" role="field" size="default" label="选择文件夹" @click="choosePath"><FolderOpen /></VNextIconButton>
                    <div v-if="inferredName && !error" id="create-project-preview" class="project-preview app-form-help"><Folder :size="14" /><span>将创建“{{ inferredName }}”</span></div>
                    <p v-if="error" id="create-project-error" class="dialog-error app-form-error" role="alert"><CircleAlert :size="14" />{{ error }}</p>
                </div>
            </div>
            <footer><VNextButton @click="$emit('close')">取消</VNextButton><VNextButton tone="primary" appearance="solid" :loading="store.busy" :disabled="!inferredName" @click="createProject">创建项目</VNextButton></footer>
        </section>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { CircleAlert, Folder, FolderOpen, X } from 'lucide-vue-next'
import { trapDialogFocus } from '../dialogFocus'
import { rememberProject } from '../projectHistory'
import { useVNextStore } from '../store'
import type { WorkspaceIdentity } from '../types'
import VNextButton from './ui/VNextButton.vue'
import VNextIconButton from './ui/VNextIconButton.vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (_event: 'close'): void; (_event: 'created', _workspace: WorkspaceIdentity): void }>()
const store = useVNextStore()
const projectPath = ref('')
const error = ref('')
const pathInput = ref<HTMLInputElement | null>(null)
const normalizedPath = computed(() => projectPath.value.trim().replace(/[\\/]+$/, ''))
const inferredName = computed(() => normalizedPath.value.split(/[\\/]/).filter(Boolean).pop() || '')

watch(() => props.open, visible => {
    if (!visible) return
    error.value = ''
    nextTick(() => pathInput.value?.focus())
})

async function choosePath() {
    error.value = ''
    try { const path = await store.chooseFolder(); if (path) projectPath.value = path }
    catch (reason) { error.value = reason instanceof Error ? reason.message : '无法选择文件夹' }
}

async function createProject() {
    if (!normalizedPath.value || !inferredName.value || store.busy) return
    error.value = ''
    try {
        const result = await store.openProject(normalizedPath.value, { initialize: true, projectName: inferredName.value })
        if (!result.workspace) throw new Error((result.inspection?.errors as string[] | undefined)?.join('；') || '项目目录必须不存在或完全为空')
        rememberProject(result.workspace.project_name, result.workspace.project_path)
        emit('created', result.workspace)
        emit('close')
    } catch (reason) { error.value = reason instanceof Error ? reason.message : '创建项目失败' }
}
</script>

<style scoped>
.dialog-backdrop{position:fixed;inset:0;z-index:2000;display:grid;place-items:center;padding:20px;background:rgba(7,7,6,.76)}.create-dialog{width:min(560px,calc(100vw - 24px));overflow:hidden;border:1px solid var(--app-overlay-border);border-radius: var(--app-radius-lg);background:var(--app-bg-raised);color:var(--app-text-regular);box-shadow:var(--app-shadow-lg)}.create-dialog header,.create-dialog footer{display:flex;align-items:center;justify-content:space-between;padding:14px 18px}.create-dialog header{border-bottom:1px solid var(--app-border-subtle)}.create-dialog footer{justify-content:flex-end;gap:8px;border-top:1px solid var(--app-border-subtle)}.create-dialog h2{margin:0;color:var(--app-text-primary);font-size: var(--app-font-page-title);line-height:22px;font-weight:600}.create-dialog header p{margin:2px 0 0;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.create-body{padding:18px}.create-body>label{display:block;margin-bottom:7px;color:var(--app-text-regular);font-size: var(--app-font-compact);font-weight:500}.path-control{display:flex;height: var(--app-control-default);border:1px solid var(--app-border-default);border-radius: var(--app-radius-md);background:var(--app-bg-input)}.path-control:focus-within{border-color:var(--app-color-primary);box-shadow:var(--focus-ring)}.path-control input{min-width:0;flex:1;padding:0 10px;border:0;outline:0;background:transparent;color:var(--app-text-primary)}.project-preview{display:flex;align-items:center;gap:7px;margin-top:10px;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.dialog-error{display:flex;align-items:flex-start;gap:6px;margin:12px 0 0;color:var(--app-color-danger);font-size: var(--app-font-caption);line-height:16px}
.create-dialog { container-type: inline-size; }
.project-path-row { --app-form-row-label-min: 84px; --app-form-row-label-max: 96px; }
.project-path-row > .app-form-control { width: 100%; height: var(--app-control-default); padding: 0 10px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); outline: 0; background: var(--app-bg-input); color: var(--app-text-primary); }
.project-path-row > .app-form-control:focus { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.project-path-row > .app-form-control[aria-invalid='true'] { border-color: var(--app-color-danger); }
.project-path-row > .project-preview,
.project-path-row > .dialog-error { grid-column: 2 / -1; margin: var(--app-spacing-xs) 0 0; font-size: var(--app-font-caption); }
.project-path-row > .dialog-error { color: var(--app-color-danger); }
@container (max-width: 300px) {
    .project-path-row { grid-template-columns: minmax(0, 1fr) auto; row-gap: var(--app-form-label-control-gap); }
    .project-path-row > .app-form-label { grid-column: 1 / -1; }
    .project-path-row > .project-preview,
    .project-path-row > .dialog-error { grid-column: 1 / -1; }
}
</style>
