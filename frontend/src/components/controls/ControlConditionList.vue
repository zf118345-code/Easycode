<!-- frontend/src/components/controls/ControlConditionList.vue -->
<template>
    <div class="condition-list-wrapper">
        <!-- 1. 普通条件检测节点 (用于 LogicCheck 节点) -->
        <template v-if="config.type === 'condition_list_editor' || config.type === 'condition_list'">
            <div v-for="(cond, idx) in (modelValue || [])" :key="idx" class="cond-card">
                <div class="card-info">
                    <span class="cond-desc"><component :is="getCondIcon(cond)" :size="14" style="vertical-align: middle;" /> {{ formatCondDesc(cond) }}</span>
                </div>
                <div class="card-btns">
                    <el-button link size="small" type="primary" @click="$emit('open-cond-dialog', { idx, data: cond, isBranch: false })">编辑</el-button>
                    <el-button link size="small" type="danger" @click="removeCond(idx)">删除</el-button>
                </div>
            </div>
            <el-button type="primary" size="small" class="add-btn" @click="$emit('open-cond-dialog', { idx: -1, data: null, isBranch: false })">
                <Plus :size="14" style="vertical-align: middle;" /> 添加判断条件
            </el-button>
        </template>

        <!-- 2. 分流分支候选列表 (用于 Branch 多分支节点，已彻底隐藏“成功跳转”冗余提示) -->
        <template v-else-if="config.type === 'branch_candidate_editor' || config.type === 'candidates'">
            <div v-for="(cand, idx) in (modelValue || [])" :key="idx" class="cond-card">
                <div class="card-info">
                    <div class="cond-desc"><component :is="getCondIcon(cand.condition || cand)" :size="14" style="vertical-align: middle;" /> {{ formatCondDesc(cand.condition || cand) }}</div>
                </div>
                <div class="card-btns">
                    <el-button link size="small" type="primary" @click="$emit('open-cond-dialog', { idx, data: cand, isBranch: true })">编辑分支</el-button>
                    <el-button link size="small" type="danger" @click="removeCond(idx)">删除</el-button>
                </div>
            </div>
            <el-button type="success" size="small" class="add-btn" @click="$emit('open-cond-dialog', { idx: -1, data: null, isBranch: true })">
                <Shuffle :size="14" style="vertical-align: middle;" /> 添加分流条件分支
            </el-button>
        </template>
    </div>
</template>

<script setup>
    import { Plus, Shuffle, Image, Type, Hash, AppWindow, FolderOpen } from 'lucide-vue-next'

    const props = defineProps({
        config: { type: Object, required: true },
        modelValue: { type: Array, default: () => [] }
    })

    const emit = defineEmits(['update:modelValue', 'open-cond-dialog'])

    const removeCond = (idx) => {
        const updated = [...(props.modelValue || [])]
        updated.splice(idx, 1)
        emit('update:modelValue', updated)
    }

    // 根据条件类型返回对应的 Lucide 图标组件
    const getCondIcon = (item) => {
        const condType = item?.condition_type || item?.type || 'variable_check'
        const iconMap = {
            image_exists: Image,
            text_contains: Type,
            variable_check: Hash,
            window_state: AppWindow,
            file_exists: FolderOpen
        }
        return iconMap[condType] || Hash
    }

    // 智能格式化动态 Schema 的条件预览描述
    const formatCondDesc = (item) => {
        if (!item) return '未配置条件'
        const condType = item.condition_type || item.type || 'variable_check'
        const params = item.params || item

        if (condType === 'image_exists') {
            const opText = params.exist_mode === 'not_exists' ? '屏幕不存在' : '屏幕存在'
            return `${opText} 图片: [${params.image_source || '未选图片'}]`
        }

        if (condType === 'text_contains') {
            const modeMap = { contains: '包含', not_contains: '不包含', equals: '等于' }
            const modeText = modeMap[params.exist_mode] || '包含'
            return `屏幕文本 (${modeText}): [${params.target_text || '未设文本'}]`
        }

        if (condType === 'variable_check') {
            const varName = params.variable_name || params.var_name || '未选变量'
            const op = params.operator || 'eq'
            const val = params.compare_value ?? params.target_value ?? ''
            return `变量判定: ${varName} (${op}) ${val}`
        }

        if (condType === 'window_state') {
            return `窗口状态: [${params.window_title || '默认窗口'}] (${params.state_check || '存在'})`
        }

        if (condType === 'file_exists') {
            return `文件检查: [${params.file_path || '未设路径'}]`
        }

        return `判定类型: ${condType}`
    }
</script>

<style scoped>
    .condition-list-wrapper {
        display: flex;
        flex-direction: column;
        gap: 8px;
        width: 100%;
    }

    .cond-card {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 10px;
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-border-color-light);
        border-radius: var(--app-radius-sm, 6px);
        font-size: 12px;
        color: var(--el-text-color-regular);
        gap: 8px;
    }

    .card-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
        flex: 1;
        overflow: hidden;
    }

    .cond-desc {
        word-break: break-all;
        font-weight: 500;
        color: var(--el-text-color-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .card-btns {
        display: flex;
        align-items: center;
        gap: 4px;
        flex-shrink: 0;
    }

    .add-btn {
        width: 100%;
        margin-top: 4px;
    }
</style>