<template>
    <ProgramStructuredValueEditor
        :title="title"
        :value="value"
        :available-values="availableValues"
        :constraints="constraints"
        :busy="busy"
        @save="emit('save', $event)"
        @cancel="emit('cancel')"
    />
</template>

<script setup lang="ts">
import ProgramStructuredValueEditor from './ProgramStructuredValueEditor.vue'
import type { AvailableProgramValue, ProgramValueNode } from './types'

withDefaults(defineProps<{
    title: string
    value: ProgramValueNode
    availableValues?: AvailableProgramValue[]
    busy?: boolean
    constraints?: Record<string, unknown>
}>(), { availableValues: () => [], busy: false, constraints: () => ({}) })
const emit = defineEmits<{ save: [value: ProgramValueNode]; cancel: [] }>()
</script>
