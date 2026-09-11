<template>
    <label class="vnext-list-search">
        <Search :size="14" aria-hidden="true" />
        <span class="sr-only">{{ ariaLabel }}</span>
        <input
            ref="inputElement"
            :value="modelValue"
            type="search"
            :placeholder="placeholder"
            :aria-label="ariaLabel"
            autocomplete="off"
            @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        />
        <VNextIconButton v-if="clearable && modelValue" :label="`清除${ariaLabel}`" @click="emit('update:modelValue', '')"><X aria-hidden="true" /></VNextIconButton>
    </label>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Search, X } from 'lucide-vue-next'
import VNextIconButton from './VNextIconButton.vue'

withDefaults(defineProps<{ modelValue: string; placeholder: string; ariaLabel?: string; clearable?: boolean }>(), {
    ariaLabel: '搜索', clearable: false,
})
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const inputElement = ref<HTMLInputElement | null>(null)

defineExpose({
    focus: () => inputElement.value?.focus(),
    select: () => inputElement.value?.select(),
})
</script>

<style scoped>
.vnext-list-search { box-sizing: border-box; height: var(--app-control-default); min-height: var(--app-control-default); display: flex; align-items: center; gap: 7px; margin: 10px var(--app-pane-inline-padding) 6px; padding: 0 9px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-md); background: var(--app-bg-input); color: var(--app-text-secondary); }
.vnext-list-search:focus-within { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.vnext-list-search input { min-width: 0; flex: 1; height: 100%; padding: 0; border: 0; outline: 0; background: transparent; color: var(--app-text-primary); font: inherit; font-size: var(--app-font-xs); }
.vnext-list-search input::placeholder { color: var(--app-text-placeholder); }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
</style>
