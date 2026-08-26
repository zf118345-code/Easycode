<template>
    <section class="resource-panel">
        <FileBrowser v-if="store.currentProjectPath" :project-path="store.currentProjectPath" mode="manage" initial-path="image" fill-height @mutated="store.reloadAfterResourceMutation?.()" />
        <div v-else class="empty"><Images :size="25" /><strong>请先打开项目</strong><span>图片、OCR 与页面特征资源都保存在子项目目录中。</span></div>
    </section>
</template>
<script setup>
import { Images } from 'lucide-vue-next'
import { useProjectStore } from '@/stores'
import FileBrowser from '@/components/FileBrowser.vue'
const store = useProjectStore()
</script>
<style scoped>
.resource-panel{height:100%;min-width:0;overflow:hidden;background:var(--app-sidebar-bg)}.empty{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;padding:20px;color:var(--app-text-placeholder);font-size:11px;text-align:center}.empty strong{color:var(--app-text-secondary);font-size:12px}.empty span{max-width:220px;line-height:1.5}.resource-panel :deep(.tree-sidebar){width:108px;min-width:108px}.resource-panel :deep(.tree-header){padding:8px 6px}.resource-panel :deep(.tree-header>span){font-size:10px}.resource-panel :deep(.tree-header .trash-button){font-size:0}.resource-panel :deep(.tree-wrapper){padding:2px}.resource-panel :deep(.location-bar){padding:7px 8px;font-size:10px}.resource-panel :deep(.image-grid){grid-template-columns:repeat(auto-fill,minmax(76px,1fr));gap:7px;padding:7px}.resource-panel :deep(.image-name){font-size:10px}
</style>
