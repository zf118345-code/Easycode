<template>
    <main class="welcome-shell">
        <section class="welcome-main" aria-labelledby="welcome-title">
            <div class="brand-mark"><Braces :size="22" /></div>
            <h1 id="welcome-title">EasyCode</h1>
            <p>用顺序清晰的结构化语句构建、调试并交付自动化应用。</p>
            <div class="welcome-actions">
                <VNextButton tone="primary" appearance="solid" :disabled="store.busy" @click="openExisting"><template #icon><FolderOpen /></template>打开项目</VNextButton>
                <VNextButton :disabled="store.busy" @click="openCreateDialog"><template #icon><FolderPlus /></template>新建项目</VNextButton>
            </div>
            <p v-if="error" class="welcome-error" role="alert"><CircleAlert :size="15" />{{ error }}</p>
            <section v-if="recentProjects.length" class="recent-projects" aria-labelledby="recent-title">
                <header><h2 id="recent-title">最近项目</h2><span>{{ recentProjects.length }}</span></header>
                <div class="recent-list">
                    <button v-for="project in recentProjects" :key="project.path" type="button" :disabled="store.busy" @click="openRecent(project)">
                        <Folder :size="15" /><span><strong>{{ project.name }}</strong><small>{{ project.path }}</small></span>
                    </button>
                </div>
            </section>
        </section>
        <VNextCreateProjectDialog :open="showCreate" @close="closeCreateDialog" />
        <div v-if="recovery" class="dialog-backdrop">
            <section ref="recoveryDialogElement" class="recovery-dialog" role="alertdialog" aria-modal="true" aria-labelledby="recovery-title" tabindex="-1" @keydown="trapDialogFocus" @keydown.esc.stop="recovery = null">
                <header><div><h2 id="recovery-title">项目需要恢复</h2><p>源文件不会被自动猜测修复。请选择一个确认可用的历史版本。</p></div><VNextIconButton label="关闭" data-dialog-initial-focus @click="recovery = null"><X /></VNextIconButton></header>
                <div class="recovery-body">
                    <article v-for="program in recovery.damaged_programs" :key="program.function_id">
                        <div class="damaged-title"><CircleAlert :size="16" /><span><strong>{{ program.is_entry ? '主程序' : program.function_id }}</strong><small>{{ program.message }}</small></span></div>
                        <p v-if="!program.history.length" class="no-history">没有可用历史版本。损坏文件保持原样，请从备份恢复。</p>
                        <ol v-else><li v-for="item in program.history" :key="item.history_id"><span><strong>{{ item.display_name }}</strong><small>{{ formatTime(item.created_at) }} · {{ item.statement_count }} 条语句</small></span><VNextButton size="compact" :disabled="store.busy || recoveryBusy" @click="restore(program, item.history_id)">恢复此版本</VNextButton></li></ol>
                    </article>
                    <p v-if="recoveryError" class="dialog-error" role="alert"><CircleAlert :size="14" />{{ recoveryError }}</p>
                </div>
            </section>
        </div>
    </main>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Braces, CircleAlert, Folder, FolderOpen, FolderPlus, X } from 'lucide-vue-next'
import { useVNextStore } from '../store'
import { vnextApi } from '../api'
import { trapDialogFocus, useDialogFocusReturn } from '../dialogFocus'
import VNextCreateProjectDialog from './VNextCreateProjectDialog.vue'
import VNextButton from './ui/VNextButton.vue'
import VNextIconButton from './ui/VNextIconButton.vue'
import { readRecentProjects, rememberProject, type RecentProject } from '../projectHistory'
const store = useVNextStore()
const showCreate = ref(false), error = ref('')
interface RecoveryProgram { function_id: string; is_entry: boolean; message: string; current_revision: string; history: Array<{ history_id: string; created_at: string; display_name: string; statement_count: number }> }
interface RecoveryState { path: string; damaged_programs: RecoveryProgram[] }
const recovery = ref<RecoveryState | null>(null)
const recoveryDialogElement = ref<HTMLElement | null>(null)
const recoveryBusy = ref(false)
const recoveryError = ref('')
useDialogFocusReturn(() => Boolean(recovery.value), recoveryDialogElement)
let createDialogTrigger: HTMLElement | null = null
const recentProjects = ref<RecentProject[]>(readRecentProjects())
function openCreateDialog(event: MouseEvent) { createDialogTrigger = event.currentTarget as HTMLElement; showCreate.value = true }
function closeCreateDialog() { showCreate.value = false; queueMicrotask(() => createDialogTrigger?.focus()) }
async function openExisting() {
    error.value = ''
    try { const path = await store.chooseFolder(); if (!path) return; const result = await store.openProject(path); if (!result.workspace) { if (openRecovery(path, result.inspection)) return; throw new Error((result.inspection?.errors as string[] | undefined)?.join('；') || '这不是可用的 EasyCode vNext 项目') } rememberRecent(result.workspace.project_name, result.workspace.project_path) }
    catch (reason) { error.value = reason instanceof Error ? reason.message : '打开项目失败' }
}
async function openRecent(project: RecentProject) {
    error.value = ''
    try { const result = await store.openProject(project.path); if (!result.workspace) { if (openRecovery(project.path, result.inspection)) return; throw new Error((result.inspection?.errors as string[] | undefined)?.join('；') || '项目已移动、删除或不是可用的 EasyCode vNext 项目') } rememberRecent(result.workspace.project_name, result.workspace.project_path) }
    catch (reason) { error.value = reason instanceof Error ? reason.message : '打开最近项目失败' }
}
function rememberRecent(name: string, path: string) { recentProjects.value = rememberProject(name, path) }
function openRecovery(path: string, inspection: Record<string, unknown>): boolean {
    if (inspection.status !== 'recovery' || !Array.isArray(inspection.damaged_programs)) return false
    recovery.value = { path, damaged_programs: inspection.damaged_programs as RecoveryProgram[] }; recoveryError.value = ''; return true
}
function formatTime(value: string): string { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false }) }
async function restore(program: RecoveryProgram, historyId: string) {
    if (!recovery.value || recoveryBusy.value) return
    recoveryBusy.value = true; recoveryError.value = ''; const path = recovery.value.path
    try {
        await vnextApi.recoverProgram({ path, function_id: program.function_id, history_id: historyId, expected_revision: program.current_revision })
        const result = await store.openProject(path)
        if (!result.workspace) { if (openRecovery(path, result.inspection)) return; throw new Error((result.inspection?.errors as string[] | undefined)?.join('；') || '恢复后仍无法打开项目') }
        recovery.value = null; rememberRecent(result.workspace.project_name, result.workspace.project_path)
    } catch (reason) { recoveryError.value = reason instanceof Error ? reason.message : '恢复项目失败' }
    finally { recoveryBusy.value = false }
}
</script>

<style scoped>
.welcome-shell{width:100%;height:100%;display:grid;place-items:center;background:var(--app-bg-base);color:var(--app-text-primary)}.welcome-main{width:min(520px,calc(100vw - 40px));display:flex;flex-direction:column;align-items:center;text-align:center}.brand-mark{width:44px;height:44px;display:grid;place-items:center;margin-bottom:16px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-lg);background:var(--app-bg-raised);color:var(--app-color-primary);box-shadow:0 8px 24px rgba(0,0,0,.28)}h1{margin:0;font-size:26px;line-height:34px;letter-spacing:-.025em;font-weight:600}.welcome-main>p{margin:7px 0 0;color:var(--app-text-secondary);font-size: var(--app-font-body);line-height:20px}.welcome-actions{display:flex;gap:8px;margin-top:28px}button:disabled{opacity:.45;cursor:not-allowed}.welcome-error{display:flex;align-items:center;gap:6px;color:var(--app-color-danger)!important}.recent-projects{width:min(480px,100%);margin-top:24px;text-align:left}.recent-projects>header{height: var(--app-control-compact);display:flex;align-items:center;justify-content:space-between;padding:0 6px}.recent-projects h2{margin:0;color:var(--app-text-secondary);font-size: var(--app-font-caption);font-weight:600}.recent-projects header span{color:var(--app-text-placeholder);font-size: var(--app-font-caption)}.recent-list{display:flex;flex-direction:column;gap:2px}.recent-list button{width:100%;min-height:42px;display:grid;grid-template-columns:22px minmax(0,1fr);align-items:center;gap:8px;padding:5px 8px;border:0;border-radius: var(--app-radius-md);background:transparent;color:var(--app-text-secondary);text-align:left;cursor:pointer}.recent-list button:hover:not(:disabled),.recent-list button:focus-visible{background:var(--app-bg-hover);color:var(--app-text-primary)}.recent-list button>span{min-width:0;display:flex;flex-direction:column;gap:1px}.recent-list strong{overflow:hidden;color:var(--app-text-regular);font-size: var(--app-font-caption);font-weight:500;text-overflow:ellipsis;white-space:nowrap}.recent-list small{overflow:hidden;color:var(--app-text-placeholder);font-size: var(--app-font-caption);text-overflow:ellipsis;white-space:nowrap}.dialog-backdrop{position:fixed;inset:0;z-index:2000;display:grid;place-items:center;padding:20px;background:rgba(7,7,6,.76)}
.recovery-dialog{width:min(660px,calc(100vw - 24px));max-height:min(720px,calc(100vh - 24px));display:flex;flex-direction:column;overflow:hidden;border:1px solid var(--app-overlay-border);border-radius: var(--app-radius-lg);background:var(--app-bg-raised);box-shadow:var(--app-shadow-lg);text-align:left}.recovery-dialog>header{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--app-border-subtle)}.recovery-dialog h2{margin:0;font-size: var(--app-font-page-title)}.recovery-dialog header p{margin:3px 0 0;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.recovery-body{overflow:auto;padding:12px}.recovery-body article{padding:10px;border:1px solid var(--app-border-subtle);border-radius: var(--app-radius-md)}.damaged-title{display:flex;gap:8px;color:var(--app-color-warning)}.damaged-title>span,.recovery-body li>span{min-width:0;display:flex;flex:1;flex-direction:column;gap:2px}.damaged-title small,.recovery-body li small{overflow:hidden;color:var(--app-text-muted);font-size: var(--app-font-caption);text-overflow:ellipsis;white-space:nowrap}.recovery-body ol{display:flex;flex-direction:column;gap:2px;margin:10px 0 0;padding:0;list-style:none}.recovery-body li{display:flex;align-items:center;gap:12px;min-height:45px;padding:6px 8px;border-radius: var(--app-radius-sm)}.recovery-body li:hover{background:var(--app-bg-hover)}.no-history{margin:10px 0 0;color:var(--app-color-danger);font-size: var(--app-font-caption)}
</style>
