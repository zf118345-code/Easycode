<template>
    <div class="dialog-backdrop" @mousedown.self="$emit('cancel')">
        <section class="shortcut-dialog" role="dialog" aria-modal="true" aria-labelledby="shortcut-title" @keydown="trapDialogFocus" @keydown.esc.stop="$emit('cancel')">
            <header>
                <div><h2 id="shortcut-title">键盘快捷键</h2><p>只影响这台电脑上的 EasyCode，不会写入项目或发布包。</p></div>
                <VNextIconButton label="关闭" @click="$emit('cancel')"><X /></VNextIconButton>
            </header>
            <div class="shortcut-tools">
                <VNextTextField v-model="query" type="search" aria-label="搜索快捷键" placeholder="搜索命令或按键" autofocus />
                <VNextButton @click="resetAll">恢复默认</VNextButton>
            </div>
            <p v-if="error" class="form-error" role="alert">{{ error }}</p>
            <div class="shortcut-list">
                <section v-for="group in visibleGroups" :key="group">
                    <h3>{{ group }}</h3>
                    <div v-for="command in visibleCommands(group)" :key="command.id" class="shortcut-row">
                        <div><strong>{{ command.label }}</strong><span>{{ command.description }}</span></div>
                        <button
                            type="button"
                            class="shortcut-recorder"
                            :class="{ recording: recordingId === command.id }"
                            @click="recordingId = command.id"
                            @keydown="record($event, command.id)"
                        >{{ recordingId === command.id ? '请按快捷键…' : draft[command.id] || '未设置' }}</button>
                        <button type="button" class="shortcut-clear" aria-label="清除快捷键" @click="draft[command.id] = ''">清除</button>
                    </div>
                </section>
            </div>
            <footer>
                <VNextButton :disabled="busy" @click="$emit('cancel')">取消</VNextButton>
                <VNextButton tone="primary" appearance="solid" :loading="busy" :disabled="Boolean(error)" @click="save">保存</VNextButton>
            </footer>
        </section>
    </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { trapDialogFocus } from '../dialogFocus'
import { IDE_COMMANDS, shortcutFromKeyboardEvent, type IdeCommandGroup } from '../ideCommands'
import VNextButton from './ui/VNextButton.vue'
import VNextIconButton from './ui/VNextIconButton.vue'
import VNextTextField from './ui/VNextTextField.vue'

const props = defineProps<{ shortcuts: Record<string, string>; defaults: Record<string, string>; busy?: boolean }>()
const emit = defineEmits<{ cancel: []; save: [shortcuts: Record<string, string>] }>()
const query = ref('')
const recordingId = ref('')
const draft = reactive<Record<string, string>>({ ...props.shortcuts })
const groups: IdeCommandGroup[] = ['编辑', '视图', '运行', '帮助']
const shortcutCommands = IDE_COMMANDS.filter(item => item.shortcut)
const duplicate = computed(() => {
    const seen = new Map<string, string>()
    for (const command of shortcutCommands) {
        const value = (draft[command.id] || '').toLocaleLowerCase()
        if (!value) continue
        if (seen.has(value)) return `“${draft[command.id]}”同时分配给了两个命令，请先清除其中一个。`
        seen.set(value, command.id)
    }
    return ''
})
const error = computed(() => duplicate.value)
const visibleGroups = computed(() => groups.filter(group => visibleCommands(group).length))
function visibleCommands(group: IdeCommandGroup) {
    const term = query.value.trim().toLocaleLowerCase()
    return shortcutCommands.filter(item => item.group === group && (!term || `${item.label} ${item.description} ${draft[item.id] || ''}`.toLocaleLowerCase().includes(term)))
}
function record(event: KeyboardEvent, commandId: string) {
    if (recordingId.value !== commandId) return
    event.preventDefault()
    event.stopPropagation()
    if (event.key === 'Backspace' || event.key === 'Delete') draft[commandId] = ''
    else {
        const value = shortcutFromKeyboardEvent(event)
        if (!value || ['Control', 'Shift', 'Alt', 'Meta'].includes(event.key)) return
        draft[commandId] = value
    }
    recordingId.value = ''
}
function resetAll() { Object.assign(draft, props.defaults); recordingId.value = '' }
function save() { if (!error.value) emit('save', { ...draft }) }
watch(() => props.shortcuts, value => Object.assign(draft, value), { deep: true })
</script>

<style scoped>
.dialog-backdrop { position: fixed; inset: 0; z-index: 2400; display: grid; place-items: center; padding: 20px; background: rgba(7, 7, 6, .72); }
.shortcut-dialog { width: min(780px, calc(100vw - 36px)); height: min(680px, calc(100vh - 48px)); display: grid; grid-template-rows: auto auto auto minmax(0, 1fr) auto; overflow: hidden; border: 1px solid var(--app-overlay-border); border-radius: var(--app-radius-lg); background: var(--app-bg-raised); box-shadow: var(--app-shadow-lg); }
.shortcut-dialog > header { display: flex; align-items: flex-start; justify-content: space-between; padding: 15px 18px; border-bottom: 1px solid var(--app-border-subtle); }
.shortcut-dialog h2 { margin: 0; color: var(--app-text-primary); font-size: var(--app-font-md); }
.shortcut-dialog header p { margin: 4px 0 0; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.shortcut-tools { display: flex; gap: 8px; padding: 12px 18px; }
.shortcut-tools > :first-child { min-width: 0; flex: 1; }
.form-error { margin: 0 18px 8px; color: var(--app-color-danger); font-size: var(--app-font-xs); }
.shortcut-list { grid-row: 4; min-height: 0; overflow: auto; padding: 0 18px 16px; }
.shortcut-list h3 { margin: 14px 0 5px; color: var(--app-text-secondary); font-size: var(--app-font-xs); font-weight: 600; }
.shortcut-row { min-height: var(--app-list-row-rich); display: grid; grid-template-columns: minmax(0, 1fr) 180px 44px; align-items: center; gap: 8px; border-top: 1px solid var(--app-border-subtle); }
.shortcut-row > div { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.shortcut-row strong { color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 500; }
.shortcut-row span { overflow: hidden; color: var(--app-text-placeholder); font-size: var(--app-font-xs); text-overflow: ellipsis; white-space: nowrap; }
.shortcut-recorder { height: var(--app-control-default); border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-input); color: var(--app-text-regular); font: inherit; cursor: pointer; }
.shortcut-recorder.recording { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); color: var(--app-color-primary); }
.shortcut-clear { min-height: var(--app-control-default); border: 0; background: transparent; color: var(--app-text-secondary); font: inherit; font-size: var(--app-font-xs); cursor: pointer; }
.shortcut-dialog > footer { grid-row: 5; display: flex; justify-content: flex-end; gap: 8px; padding: 12px 18px; border-top: 1px solid var(--app-border-subtle); }
@media (max-width: 680px) {
    .shortcut-row { grid-template-columns: minmax(0, 1fr) 120px 40px; }
    .shortcut-row span { display: none; }
}
</style>
