<template>
    <component
        :is="as"
        class="vnext-navigation-item app-navigation-item"
        :class="[{ active: selected, 'is-selected': selected, 'is-child': child }, `is-${density}`]"
        :type="as === 'button' ? 'button' : undefined"
        :disabled="as === 'button' ? disabled : undefined"
        :aria-selected="selectable ? selected : undefined"
        v-bind="$attrs"
    ><slot /></component>
</template>

<script setup lang="ts">
defineOptions({ inheritAttrs: false })
withDefaults(defineProps<{
    as?: 'button' | 'div'
    selected?: boolean
    selectable?: boolean
    disabled?: boolean
    child?: boolean
    density?: 'compact' | 'rich' | 'multiline'
}>(), { as: 'button', selected: false, selectable: false, disabled: false, child: false, density: 'compact' })
</script>

<style scoped>
.vnext-navigation-item { width: 100%; }
.vnext-navigation-item:disabled { opacity: .35; cursor: not-allowed; }
</style>
