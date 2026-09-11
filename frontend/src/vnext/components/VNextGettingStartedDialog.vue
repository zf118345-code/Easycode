<template>
    <div class="help-backdrop" @mousedown.self="emit('close')">
        <section class="help-dialog" role="dialog" aria-modal="true" aria-labelledby="getting-started-title" @keydown="trapDialogFocus" @keydown.esc.stop="emit('close')">
            <header><div><h2 id="getting-started-title">EasyCode 使用入门</h2><p>从目标和素材开始，逐步得到可独立运行的 Player。</p></div><button ref="closeButton" type="button" aria-label="关闭使用入门" @click="emit('close')"><X :size="16" /></button></header>
            <div class="help-body">
                <section><span>1</span><div><h3>连接运行目标</h3><p>先登记 Windows 窗口、模拟器 ADB 或 Android 本机，检查当前能力和权限。</p><button type="button" @click="choose('view.targets')">打开运行目标</button></div></section>
                <section><span>2</span><div><h3>采集可复用素材</h3><p>录入图像、OCR 区域或页面素材。资源使用稳定 ID，改名不会破坏流程。</p><button type="button" @click="choose('view.resources')">打开资源</button></div></section>
                <section><span>3</span><div><h3>按顺序搭建流程</h3><p>从左侧函数库插入语句，在右侧填写参数；检查器会在运行前指出缺失目标和类型错误。</p><button type="button" @click="choose('view.program')">打开程序</button></div></section>
                <section><span>4</span><div><h3>交付与排查</h3><p>按需制作 Player 表单；运行记录保留画面和时间线，计划与实例负责本地及局域网调度。</p><div class="help-actions"><button type="button" @click="choose('view.player')">制作 Player</button><button type="button" @click="choose('view.replay')">查看运行记录</button></div></div></section>
            </div>
            <footer><span><kbd>Ctrl+Shift+P</kbd> 随时搜索全部命令</span><button type="button" @click="choose('help.shortcuts')">查看快捷键</button></footer>
        </section>
    </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { X } from 'lucide-vue-next'
import { trapDialogFocus } from '../dialogFocus'

const emit = defineEmits<{ close: []; command: [commandId: string] }>()
const closeButton = ref<HTMLButtonElement | null>(null)
function choose(commandId: string): void { emit('command', commandId) }
onMounted(() => closeButton.value?.focus())
</script>

<style scoped>
.help-backdrop{position:fixed;inset:0;z-index:2450;display:grid;place-items:center;padding:18px;background:rgba(7,7,6,.72)}
.help-dialog{width:min(760px,calc(100vw - 28px));max-height:calc(100vh - 36px);display:grid;grid-template-rows:auto minmax(0,1fr) auto;overflow:hidden;border:1px solid var(--app-overlay-border);border-radius:var(--app-radius-lg);background:var(--app-bg-overlay);box-shadow:var(--app-shadow-lg);color:var(--app-text-regular)}
.help-dialog>header{display:flex;align-items:flex-start;justify-content:space-between;padding:17px 19px;border-bottom:1px solid var(--app-border-subtle)}h2,h3,p{margin:0}.help-dialog h2{font-size:var(--app-font-md);color:var(--app-text-primary)}.help-dialog header p{margin-top:5px;color:var(--app-text-secondary);font-size:var(--app-font-xs)}
.help-dialog header button{width:28px;height: var(--app-control-compact);display:grid;place-items:center;border:0;border-radius:var(--app-radius-sm);background:transparent;color:var(--app-text-secondary);cursor:pointer}.help-dialog header button:hover{background:var(--app-bg-hover);color:var(--app-text-primary)}
.help-body{min-height:0;overflow:auto;display:grid;grid-template-columns:1fr 1fr;gap:1px;padding:1px;background:var(--app-border-subtle)}.help-body>section{display:flex;gap:12px;min-height:174px;padding:20px;background:var(--app-bg-raised)}.help-body>section>span{width:27px;height:27px;display:grid;flex:0 0 auto;place-items:center;border-radius:50%;background:var(--app-color-primary-dim);color:var(--app-color-primary);font-weight:700}.help-body>section>div{display:flex;min-width:0;align-items:flex-start;flex-direction:column}.help-body h3{font-size:var(--app-font-sm);color:var(--app-text-primary)}.help-body p{flex:1;margin:8px 0 14px;color:var(--app-text-secondary);font-size:var(--app-font-xs);line-height:1.65}.help-body button,.help-dialog>footer button{min-height: var(--app-control-compact);padding:0 10px;border:1px solid var(--app-border-default);border-radius:var(--app-radius-sm);background:transparent;color:var(--app-text-regular);font:inherit;font-size:var(--app-font-xs);cursor:pointer}.help-body button:hover,.help-dialog>footer button:hover{background:var(--app-bg-hover);color:var(--app-text-primary)}.help-actions{display:flex;flex-wrap:wrap;gap:6px}
.help-dialog>footer{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 18px;border-top:1px solid var(--app-border-subtle);color:var(--app-text-secondary);font-size:var(--app-font-xs)}kbd{padding:2px 5px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-sm);background:var(--app-bg-input);font:inherit;color:var(--app-text-regular)}
@media(max-width:620px){.help-backdrop{padding:8px}.help-dialog{width:100%;max-height:calc(100vh - 16px)}.help-body{grid-template-columns:1fr}.help-body>section{min-height:150px;padding:16px}.help-dialog>footer{align-items:flex-start;flex-direction:column}}
</style>
