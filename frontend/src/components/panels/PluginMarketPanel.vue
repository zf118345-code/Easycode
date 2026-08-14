<!-- frontend/src/components/panels/PluginMarketPanel.vue -->
<template>
    <div class="panel-container">
        <div class="panel-section-title"><Puzzle :size="16" style="vertical-align: middle;" /> 扩展插件中心</div>
        <div class="panel-body">
            <div class="plugin-item" v-for="p in plugins" :key="p.name">
                <div class="p-info">
                    <span class="p-name">{{ p.name }}</span>
                    <span class="p-desc">{{ p.desc }}</span>
                </div>
                <el-button size="small" type="primary" plain>安装</el-button>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue'
import { Puzzle } from 'lucide-vue-next'
const plugins = ref([
  { name: 'OCR 增强插件', desc: '提供高精度离线文字识别支持' },
  { name: 'ADB 远程控制', desc: '支持安卓模拟器多开同步点击' }
])
</script>

<style scoped>
    .panel-container {
        height: 100%;
        display: flex;
        flex-direction: column;
        background: var(--el-bg-color);
        color: var(--el-text-color-regular);
    }

    .panel-section-title {
        padding: 10px 12px;
        font-size: 12px;
        font-weight: 600;
        border-bottom: 1px solid var(--el-border-color-light);
        color: var(--el-text-color-primary);
    }

    .panel-body {
        flex: 1;
        padding: 10px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .plugin-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px;
        background: var(--el-fill-color-blank);
        border-radius: 6px;
        border: 1px solid var(--el-border-color-light);
    }

    .p-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .p-name {
        font-size: 12px;
        font-weight: 600;
        color: var(--el-text-color-primary);
    }

    .p-desc {
        font-size: 10px;
        color: var(--el-text-color-secondary);
    }
</style>