<template>
    <div class="command-backdrop" @mousedown.self="emit('cancel')">
        <section class="command-palette" role="dialog" aria-modal="true" aria-labelledby="command-palette-title" @keydown="trapDialogFocus" @keydown.esc.stop="emit('cancel')">
            <h2 id="command-palette-title">运行 EasyCode 命令</h2>
            <label class="command-search">
                <Search :size="16" aria-hidden="true" />
                <input ref="searchInput" v-model="query" type="search" aria-label="搜索命令" placeholder="输入功能名称，例如：资源、运行、快捷键" @keydown="onSearchKeydown" />
                <kbd>Esc</kbd>
            </label>
            <div v-if="visibleCommands.length" ref="results" class="command-results" role="listbox" aria-label="命令搜索结果">
                <button
                    v-for="(command, index) in visibleCommands"
                    :key="command.id"
                    type="button"
                    role="option"
                    :aria-selected="index === activeIndex"
                    :disabled="!enabled(command.id)"
                    @mouseenter="activeIndex = index"
                    @click="choose(command.id)"
                >
                    <span><strong>{{ command.label }}</strong><small>{{ command.group }} · {{ command.description }}</small></span>
                    <span class="command-meta"><kbd v-if="shortcuts[command.id]">{{ shortcuts[command.id] }}</kbd><em v-if="!enabled(command.id)">{{ disabledReason(command.id) }}</em></span>
                </button>
            </div>
            <VNextWorkspaceState v-else class="command-empty" compact kind="filtered" title="没有匹配的命令" description="可以换一个更短的功能名称。"><template #icon><SearchX :size="22" /></template></VNextWorkspaceState>
        </section>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Search, SearchX } from 'lucide-vue-next'
import { trapDialogFocus } from '../dialogFocus'
import { IDE_COMMANDS } from '../ideCommands'
import VNextWorkspaceState from './ui/VNextWorkspaceState.vue'

const props = defineProps<{
    shortcuts: Record<string, string>
    enabled: (commandId: string) => boolean
    disabledReason: (commandId: string) => string
}>()
const emit = defineEmits<{ cancel: []; command: [commandId: string] }>()
const query = ref('')
const activeIndex = ref(0)
const searchInput = ref<HTMLInputElement | null>(null)
const results = ref<HTMLElement | null>(null)
const visibleCommands = computed(() => {
    const term = query.value.trim().toLocaleLowerCase()
    const commands = IDE_COMMANDS.filter(command => command.id !== 'help.command_palette')
    if (!term) return commands
    return commands.filter(command => `${command.label} ${command.group} ${command.description} ${props.shortcuts[command.id] || ''}`.toLocaleLowerCase().includes(term))
})

function move(direction: -1 | 1): void {
    if (!visibleCommands.value.length) return
    let next = activeIndex.value
    for (let count = 0; count < visibleCommands.value.length; count += 1) {
        next = (next + direction + visibleCommands.value.length) % visibleCommands.value.length
        if (props.enabled(visibleCommands.value[next].id)) break
    }
    activeIndex.value = next
    void nextTick(() => results.value?.querySelector<HTMLElement>(`button:nth-child(${next + 1})`)?.scrollIntoView({ block: 'nearest' }))
}
function choose(commandId: string): void { if (props.enabled(commandId)) emit('command', commandId) }
function onSearchKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); move(event.key === 'ArrowDown' ? 1 : -1); return }
    if (event.key === 'Enter') { event.preventDefault(); const command = visibleCommands.value[activeIndex.value]; if (command) choose(command.id) }
}
watch(visibleCommands, commands => { activeIndex.value = Math.max(0, commands.findIndex(command => props.enabled(command.id))) })
onMounted(() => { activeIndex.value = Math.max(0, visibleCommands.value.findIndex(command => props.enabled(command.id))); searchInput.value?.focus() })
</script>

<style scoped>
.command-backdrop{position:fixed;inset:0;z-index:2500;display:flex;align-items:flex-start;justify-content:center;padding:9vh 18px 18px;background:rgba(7,7,6,.78);backdrop-filter:blur(1px)}
.command-palette{width:min(680px,calc(100vw - 28px));max-height:min(620px,82vh);display:grid;grid-template-rows:50px minmax(0,1fr);overflow:hidden;border:1px solid var(--app-overlay-border);border-radius:var(--app-radius-lg);background:var(--app-bg-overlay);box-shadow:var(--app-shadow-lg)}
.command-palette h2{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.command-search{display:flex;align-items:center;gap:9px;margin:8px;padding:0 10px;border:1px solid var(--app-color-primary);border-radius:var(--app-radius-sm);background:var(--app-bg-input);box-shadow:var(--focus-ring);color:var(--app-text-secondary)}
.command-search input{min-width:0;flex:1;height: var(--app-control-default);border:0;outline:0;background:transparent;color:var(--app-text-primary);font:inherit;font-size:var(--app-font-sm)}
.command-search kbd,.command-results kbd{color:var(--app-text-placeholder);font:inherit;font-size: var(--app-font-caption);white-space:nowrap}
.command-results{min-height:0;overflow:auto;padding:3px 7px 8px}
.command-results button{width:100%;min-height:47px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:6px 10px;border:0;border-radius:var(--app-radius-sm);background:transparent;color:var(--app-text-regular);font:inherit;text-align:left;cursor:pointer}
.command-results button[aria-selected=true]:not(:disabled),.command-results button:hover:not(:disabled){background:var(--app-bg-active);color:var(--app-text-primary)}
.command-results button:disabled{opacity:.48;cursor:default}.command-results button>span{min-width:0;display:flex;flex-direction:column;gap:3px}.command-results strong{font-size:var(--app-font-sm);font-weight:600}.command-results small{overflow:hidden;color:var(--app-text-secondary);font-size:var(--app-font-xs);text-overflow:ellipsis;white-space:nowrap}.command-meta{flex:0 0 auto;align-items:flex-end!important}.command-results em{max-width:180px;color:var(--app-text-placeholder);font-size: var(--app-font-caption);font-style:normal;text-align:right}
.command-empty{min-height:170px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;color:var(--app-text-secondary);text-align:center}.command-empty strong{color:var(--app-text-primary);font-size:var(--app-font-sm)}.command-empty span{font-size:var(--app-font-xs)}
@media(max-width:620px){.command-backdrop{padding:48px 8px 8px}.command-palette{width:100%;max-height:calc(100vh - 58px)}.command-results small{white-space:normal}.command-results em{display:none}}
.command-results button { min-height: var(--app-list-row-rich); padding-block: 5px; }
</style>
