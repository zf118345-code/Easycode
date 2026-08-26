<template>
    <section class="contract-section">
        <header>
            <span>{{ title }}</span>
            <button type="button" :title="`新增${title}`" :aria-label="`新增${title}`" @click="$emit('add')">
                <Plus :size="13" />
            </button>
        </header>

        <div v-for="(item, index) in items" :key="item[idField]" class="contract-item">
            <div class="contract-row">
                <input
                    :value="item.name"
                    :title="reference(item)"
                    :aria-label="`${title}名称`"
                    @change="rename(item, index, $event)"
                />
                <select
                    :value="item.type || 'any'"
                    :aria-label="`${item.name || title}类型`"
                    @change="changeType(item, $event)"
                >
                    <option v-for="type in types" :key="type" :value="type">{{ type }}</option>
                </select>
                <button
                    v-if="prefix"
                    type="button"
                    :title="`复制 ${reference(item)}`"
                    :aria-label="`复制 ${reference(item)}`"
                    @click="copyReference(item)"
                >
                    <CopyPlus :size="12" />
                </button>
                <button
                    type="button"
                    :title="`删除${title} ${item.name || index + 1}`"
                    :aria-label="`删除${title} ${item.name || index + 1}`"
                    @click="$emit('remove', index)"
                >
                    <Trash2 :size="12" />
                </button>
            </div>

            <div class="contract-meta">
                <input
                    v-if="idField !== 'output_id'"
                    :value="item.default_value ?? ''"
                    placeholder="默认值"
                    :aria-label="`${item.name || title}默认值`"
                    @change="changeDefault(item, $event)"
                />
                <label v-if="idField === 'parameter_id'" title="调用方必须传入该参数">
                    <input
                        type="checkbox"
                        :checked="Boolean(item.required)"
                        @change="changeRequired(item, $event)"
                    />
                    <span>必填</span>
                </label>
                <input
                    :value="item.description || ''"
                    placeholder="契约说明"
                    :aria-label="`${item.name || title}说明`"
                    @change="changeDescription(item, $event)"
                />
            </div>
        </div>

        <div v-if="!items.length" class="empty-contract">暂无{{ title }}</div>
    </section>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { CopyPlus, Plus, Trash2 } from 'lucide-vue-next'
import { formatScopedReference } from '@/utils/functionContract'

const props = defineProps({
    title: { type: String, default: '' },
    prefix: { type: String, default: '' },
    idField: { type: String, default: '' },
    items: { type: Array, default: () => [] }
})

const emit = defineEmits(['add', 'remove', 'rename', 'change'])
const types = ['any', 'string', 'number', 'boolean', 'list', 'dict', 'point', 'region']
const scope = () => String(props.prefix || '').match(/^\$([a-z]+)/)?.[1] || ''
const reference = item => scope() ? formatScopedReference(scope(), item.name) : item.name

async function copyReference(item) {
    try {
        await navigator.clipboard.writeText(reference(item))
        ElMessage.success('变量引用已复制')
    } catch {
        ElMessage.error('复制失败')
    }
}

function rename(item, index, event) {
    const previousName = item.name
    item.name = event.target.value.trim()
    emit('rename', { item, index, previousName, nextName: item.name })
}

function changeType(item, event) {
    item.type = event.target.value
    emit('change')
}

function changeDefault(item, event) {
    item.default_value = event.target.value === '' ? null : event.target.value
    emit('change')
}

function changeRequired(item, event) {
    item.required = event.target.checked
    emit('change')
}

function changeDescription(item, event) {
    item.description = event.target.value
    emit('change')
}
</script>

<style scoped>
.contract-section{margin-top:12px}.contract-section>header{height:27px;display:flex;align-items:center;border-bottom:1px solid var(--app-separator);font-weight:650}.contract-section>header span{flex:1}.contract-section button{width:24px;height:24px;display:grid;place-items:center;padding:0;border:0;border-radius:6px;background:transparent;color:var(--app-text-secondary);cursor:pointer}.contract-section button:hover{background:var(--el-fill-color-light);color:var(--app-text-primary)}.contract-item{padding:7px 0;border-bottom:1px solid color-mix(in srgb,var(--app-separator) 55%,transparent)}.contract-row{min-height:29px;display:grid;grid-template-columns:minmax(90px,1fr) 72px 24px 24px;align-items:center;gap:4px}.contract-row>input,.contract-row select,.contract-meta>input{box-sizing:border-box;min-width:0;width:100%;height:27px;padding:0 7px;border:1px solid var(--app-border-subtle);border-radius:6px;outline:0;background:var(--app-input-bg);color:var(--app-text-primary);font:inherit}.contract-row select{padding-right:3px;color:var(--app-text-secondary);font-size:10px}.contract-row>input:focus,.contract-row select:focus,.contract-meta>input:focus{border-color:var(--el-color-primary);box-shadow:var(--focus-ring)}.contract-meta{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px;padding:5px 0 1px}.contract-meta>input{font-size:10px}.contract-meta>input:last-child{grid-column:1/-1}.contract-meta label{height:27px;display:flex;align-items:center;gap:4px;padding:0 7px;border:1px solid var(--app-border-subtle);border-radius:6px;color:var(--app-text-secondary);font-size:10px;white-space:nowrap}.contract-meta label input{width:13px;height:13px;margin:0;accent-color:var(--el-color-primary)}.empty-contract{height:29px;display:flex;align-items:center;color:var(--app-text-placeholder)}
</style>
