import { defineStore } from 'pinia'
import { workspaceApi } from '@/api/workspaceApi'

export const useContextStore = defineStore('context', {
    state: () => ({
        currentContext: {
            workMode: 'window',
            windowTitle: '',
            isEmulator: false,
            offsetTop: 0,
            offsetBottom: 0,
            offsetLeft: 0,
            offsetRight: 0,
            targetContentWidth: 0,
            targetContentHeight: 0
        }
    }),

    actions: {
        async loadContext() {
            const { useProjectStore } = await import('./projectStore')
            const projectStore = useProjectStore()
            if (!projectStore.currentProjectPath) return
            try {
                const ctx = await workspaceApi.getContext(projectStore.currentProjectPath)
                if (ctx) {
                    this.currentContext = {
                        workMode: ctx.windowTitle ? 'window' : 'desktop',
                        ...ctx
                    }
                }
            } catch (err) {
                console.error('加载工作区上下文失败', err)
            }
        },

        async setCurrentContext(context) {
            this.currentContext = { ...context }
            const { useProjectStore } = await import('./projectStore')
            const projectStore = useProjectStore()
            if (projectStore.currentProjectPath) {
                await workspaceApi.saveContext(projectStore.currentProjectPath, context)
            }
        }
    }
})
