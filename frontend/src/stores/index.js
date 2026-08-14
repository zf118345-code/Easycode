// stores/index.js - 向后兼容的重导出
// 大 Store 已拆分为 5 个独立 Store，此处保持旧 API 兼容
export { useProjectStore } from './projectStore'
export { useUiStore } from './uiStore'
export { useExecutionStore } from './executionStore'
export { useTopologyStore } from './topologyStore'
export { useContextStore } from './contextStore'
export { DEFAULT_UI_STATE } from './projectStore'

// 向后兼容：useMainStore 代理到各子 Store
import { defineStore } from 'pinia'
import { useProjectStore } from './projectStore'
import { useUiStore } from './uiStore'
import { useExecutionStore } from './executionStore'
import { useTopologyStore } from './topologyStore'
import { useContextStore } from './contextStore'

export const useMainStore = defineStore('main', {
    state: () => ({}),
    getters: {
        projectStore() { return useProjectStore() },
        uiStore() { return useUiStore() },
        executionStore() { return useExecutionStore() },
        topologyStore() { return useTopologyStore() },
        contextStore() { return useContextStore() }
    }
})
