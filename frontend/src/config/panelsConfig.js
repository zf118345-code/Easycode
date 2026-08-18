// frontend/src/config/panelsConfig.js
import { defineAsyncComponent } from 'vue'
import { FolderTree, Binary, Puzzle, Sliders, Terminal, Bug } from 'lucide-vue-next'

export const leftPanelsConfig = [
    {
        id: 'explorer',
        title: '项目资源管理器',
        icon: FolderTree,
        component: defineAsyncComponent(() => import('@/components/panels/ProjectExplorerPanel.vue'))
    },
    {
        id: 'variables',
        title: '全局变量监控',
        icon: Binary,
        component: defineAsyncComponent(() => import('@/components/panels/GlobalVariablesPanel.vue'))
    },
    {
        id: 'plugins',
        title: '扩展插件中心',
        icon: Puzzle,
        component: defineAsyncComponent(() => import('@/components/panels/PluginMarketPanel.vue'))
    }
]

export const rightPanelsConfig = [
    {
        id: 'inspector',
        title: '节点属性检查器',
        icon: Sliders,
        component: defineAsyncComponent(() => import('@/components/inspector/InspectorPanel.vue'))
    },
    {
        id: 'variable-inspector',
        title: '变量监控',
        icon: Bug,
        component: defineAsyncComponent(() => import('@/components/panels/VariableInspectorPanel.vue'))
    }
]

export const bottomPanelsConfig = [
    {
        id: 'console',
        title: '运行日志',
        icon: Terminal,
        component: defineAsyncComponent(() => import('@/components/canvas/CanvasLogPanel.vue'))
    }
]
