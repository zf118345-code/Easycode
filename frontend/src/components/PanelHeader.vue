<template>
    <div class="panel-header">
        <span class="title">{{ title }}</span>
        <div class="actions">
            <!-- 允许外部插入自定义的内容（如工作区胶囊按钮） -->
            <slot></slot>

            <el-dropdown v-for="(action, idx) in actions"
                         :key="idx"
                         trigger="click"
                         @command="(cmd) => $emit('action', { panelId, method: cmd })">
                <el-button :icon="action.icon" size="small" circle />
                <el-dropdown-menu slot="dropdown">
                    <el-dropdown-item v-for="item in action.items" :key="item.label" :command="item.method">
                        {{ item.label }}
                    </el-dropdown-item>
                </el-dropdown-menu>
            </el-dropdown>
        </div>
    </div>
</template>

<script>
    export default {
        props: ['title', 'actions', 'panelId']
    }
</script>

<style scoped>
    .panel-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        height: 36px;
        padding: 0 12px;
        background: var(--el-fill-color-blank);
        border-radius: 6px 6px 0 0;
        flex-shrink: 0;
    }

    .title {
        color: var(--el-text-color-primary);
        font-weight: 600;
        font-size: 13px;
    }

    .actions {
        display: flex;
        align-items: center;
        gap: 8px; /* 稍微加大一点间距，让胶囊按钮和图标按钮保持舒服的距离 */
    }
</style>