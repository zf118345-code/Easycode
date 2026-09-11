<template>
    <div class="vnext-root">
        <div v-if="loading" class="startup"><LoaderCircle :size="20" /><span>正在准备 EasyCode vNext…</span></div>
        <VNextIdeV6 v-else-if="store.workspace" />
        <VNextWelcome v-else />
        <div v-if="startupError" class="startup-error" role="alert" aria-live="assertive"><CircleAlert :size="15" /><span>{{ startupError }}</span><VNextButton size="compact" :disabled="loading" @click="load">重试</VNextButton></div>
    </div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, onMounted, ref } from 'vue'
import { CircleAlert, LoaderCircle } from 'lucide-vue-next'
import VNextWelcome from './components/VNextWelcome.vue'
import VNextButton from './components/ui/VNextButton.vue'
import { useVNextStore } from './store'
const VNextIdeV6 = defineAsyncComponent(() => import('./components/VNextIdeV6.vue'))
const store = useVNextStore()
const loading = ref(true), startupError = ref('')
async function load() {
    loading.value = true
    startupError.value = ''
    try { await store.bootstrap() }
    catch (error) { startupError.value = error instanceof Error ? error.message : 'vNext初始化失败' }
    finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.vnext-root{width:100%;height:100%;overflow:hidden}.startup{width:100%;height:100%;display:flex;align-items:center;justify-content:center;gap:8px;background:var(--app-bg-base);color:var(--app-text-secondary);font-size: var(--app-font-compact)}.startup svg{animation:spin .8s linear infinite}.startup-error{position:fixed;left:50%;bottom:20px;z-index:3000;display:flex;align-items:center;gap:7px;max-width:min(620px,calc(100vw - 32px));padding:9px 10px 9px 12px;border:1px solid color-mix(in srgb,var(--app-color-danger) 45%,transparent);border-radius: var(--app-radius-md);background:var(--app-bg-raised);color:var(--app-color-danger);box-shadow:0 12px 32px rgba(0,0,0,.34);font-size: var(--app-font-caption);transform:translateX(-50%)}.startup-error span{min-width:0;overflow-wrap:anywhere}@keyframes spin{to{transform:rotate(360deg)}}
</style>
