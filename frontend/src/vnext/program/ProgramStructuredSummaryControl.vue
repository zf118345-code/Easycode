<template>
    <div class="app-control-row structured-summary-control">
        <div
            class="app-control-surface structured-summary-surface"
            data-control-surface
            :data-empty="empty ? 'true' : undefined"
            :data-disabled="disabled ? 'true' : undefined"
            :aria-invalid="invalid ? 'true' : undefined"
            :aria-describedby="describedBy || undefined"
        >
            <span :title="summary">{{ summary }}</span>
            <small v-if="status" class="app-control-adornment">{{ status }}</small>
        </div>
        <button
            type="button"
            class="app-field-action"
            :disabled="disabled"
            :title="actionLabel"
            :aria-label="actionLabel"
            @click="emit('edit')"
        >
            <PencilLine :size="14" aria-hidden="true" />
        </button>
    </div>
</template>

<script setup lang="ts">
import { PencilLine } from 'lucide-vue-next'

withDefaults(defineProps<{
    summary: string
    status?: string
    actionLabel?: string
    empty?: boolean
    disabled?: boolean
    invalid?: boolean
    describedBy?: string
}>(), {
    status: '',
    actionLabel: '编辑结构化内容',
    empty: false,
    disabled: false,
    invalid: false,
    describedBy: '',
})

const emit = defineEmits<{ edit: [] }>()
</script>

<style scoped>
.structured-summary-surface > span {
    min-width: 0;
    flex: 1;
    overflow: hidden;
    color: inherit;
    font-size: var(--app-font-xs);
    text-overflow: ellipsis;
    white-space: nowrap;
}

.structured-summary-surface[aria-invalid='true'] { border-color: var(--app-color-danger); }
</style>
