<template><span class="vnext-spinner" role="status" :aria-label="label" /></template>
<script setup lang="ts">withDefaults(defineProps<{ label?: string }>(), { label: '正在加载' })</script>
<style scoped>
.vnext-spinner { box-sizing: border-box; width: 14px; height: 14px; display: inline-block; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: vnext-spinner-spin .7s linear infinite; }
@keyframes vnext-spinner-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .vnext-spinner { animation-duration: 1.4s; } }
</style>
