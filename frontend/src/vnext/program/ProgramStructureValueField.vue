<template>
    <section class="value-field">
        <ProgramParameterControl
            :statement-id="statementId"
            :parameter="parameter"
            :value="value"
            :available-values="availableValues"
            :diagnostics="diagnostics"
            :disabled="busy"
            :value-editor-available="true"
            @update="emit('update', $event)"
            @open-value-editor="emit('openValueEditor', $event)"
        />
    </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ProgramParameterControl from './ProgramParameterControl.vue'
import type { ParameterControlType } from '../types'
import type {
    AvailableProgramValue,
    ProgramParameterContract,
    ProgramValueNode,
    ProgramValueEditorRequest,
    ProgramValueUpdate,
} from './types'

const props = withDefaults(defineProps<{
    statementId?: string
    title: string
    parameterId: string
    value: ProgramValueNode
    valueType?: string
    required?: boolean
    control?: ParameterControlType
    constraints?: ProgramParameterContract['constraints']
    availableValues?: AvailableProgramValue[]
    diagnostics?: string[]
    busy?: boolean
}>(), {
    statementId: '',
    valueType: '',
    required: false,
    control: undefined,
    constraints: () => ({}),
    availableValues: () => [],
    diagnostics: () => [],
    busy: false,
})

const emit = defineEmits<{ update: [update: ProgramValueUpdate]; openValueEditor: [request: ProgramValueEditorRequest] }>()
const parameter = computed<ProgramParameterContract>(() => ({
    parameter_id: props.parameterId,
    display_name: props.title,
    value_type: props.valueType || props.value.value_type,
    required: props.required,
    constraints: props.constraints,
    ...(props.control ? { ui: { control: props.control } } : {}),
    allowed_sources: ['fixed', 'reference', 'computed'],
}))
</script>

<style scoped>
.value-field {
    min-width: 0;
    border-bottom: 1px solid var(--app-border-subtle);
}
</style>
