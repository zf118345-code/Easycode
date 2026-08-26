<template><el-select :model-value="modelValue" placeholder="选择函数结果" @update:model-value="$emit('update:modelValue', $event)"><el-option v-for="item in outcomes" :key="item.outcome_id" :value="item.outcome_id" :label="item.name"><span class="option"><i :class="item.color || 'success'" />{{ item.name }}</span></el-option></el-select></template>
<script setup>
import { computed } from 'vue'; import { useProjectStore } from '@/stores'
defineProps({ modelValue: { type: String, default: '' } }); defineEmits(['update:modelValue'])
const store = useProjectStore(); const outcomes = computed(() => store.currentFunction?.outcomes || [])
</script>
<style scoped>.option{display:flex;align-items:center;gap:7px}.option i{width:7px;height:7px;border-radius:50%;background:#54a875}.option i.danger{background:#dc655f}</style>
