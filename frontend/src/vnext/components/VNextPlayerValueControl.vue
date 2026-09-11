<template>
    <VNextValueControl
        :control-type="control.type === 'button' ? 'expression' : control.type"
        :label="control.label"
        :value-type="control.source_type || 'string'"
        :model-value="modelValue"
        :required="control.required"
        :options="control.options"
        :constraints="control.constraints"
        :ui="control.parameter_ui"
        :assets="assets"
        :actions="actions"
        :placeholder="control.help"
        @update:model-value="emit('update:modelValue',$event)"
        @action="emit('action',$event)"
    />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VNextValueControl from './VNextValueControl.vue'
import { controlActions } from '../controlRegistry'
import type { AssetDefinition, ParameterDefinition, ParameterUiAction, PlatformId, PlayerControlDefinition } from '../types'

const props=withDefaults(defineProps<{control:PlayerControlDefinition;modelValue:unknown;assets?:AssetDefinition[];platform?:PlatformId;actionsEnabled?:boolean}>(),{assets:()=>[],platform:'windows',actionsEnabled:false})
const emit=defineEmits<{'update:modelValue':[value:unknown];action:[action:ParameterUiAction]}>()
const parameter=computed<ParameterDefinition>(()=>({
    parameter_id:'parameter_id' in props.control.binding?props.control.binding.parameter_id:props.control.control_id,
    name:props.control.label,
    value_type:props.control.source_type||'json',required:props.control.required,default:props.control.default,
    description:props.control.help,constraints:props.control.constraints||{},
    ui:props.control.parameter_ui||{control:props.control.type==='button'?'expression':props.control.type,actions:[]},
}))
const actions=computed(()=>props.actionsEnabled?controlActions(parameter.value,props.platform):[])
</script>
