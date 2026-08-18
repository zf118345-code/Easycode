<!-- VariableAwareInput.vue：统一输入框（普通文本 + $var{} / $ctx{} / $env{} 变量高亮 chip）
  交互（参考成熟平台）：
  - 聚焦编辑期间保持纯文本（$var{name} 原样显示），方便修改；
  - 失去焦点时，完整变量 token 转为绿色发光 chip（前后自动补一个显示空格，存储值保持原文）；
  - 退格：第一下删 chip 前的空格，第二下整块删除 chip（浏览器原生原子元素行为）；
  - 点击发光 name → 重新展开为 $var{name} 纯文本可编辑（光标置于 } 前）；点击外部/失焦恢复发光。
  应用于所有 str / string / textarea / variable 类型的参数输入（控件库统一入口）。
-->
<template>
    <div
        ref="editorRef"
        class="var-aware-input"
        :class="{ 'is-multiline': isMultiline, 'is-empty': isEmpty }"
        contenteditable="true"
        :data-placeholder="placeholder"
        spellcheck="false"
        @input="onInput"
        @focus="onFocus"
        @blur="onBlur"
        @click="onClick"
        @keydown="onKeydown"
        @compositionstart="composing = true"
        @compositionend="onCompositionEnd" />
</template>

<script setup>
    import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

    const props = defineProps({
        config: { type: Object, default: () => ({}) },
        modelValue: { type: [String, Number], default: '' },
        label: { type: String, default: '' }
    })
    const emit = defineEmits(['update:modelValue'])

    const editorRef = ref(null)
    const composing = ref(false)
    const focused = ref(false)
    const editingToken = ref('')   // 正在编辑的变量 token（点击 chip 展开后）

    // 统一变量语法：$var{name} / $ctx{name} / $env{name} / $sys{name}
    const VAR_RE = /\$((?:var|ctx|env|sys))\{([^{}]*)\}/g

    const isMultiline = computed(() => props.config?.type === 'textarea')
    const placeholder = computed(() => props.config?.placeholder || '请输入...')
    const isEmpty = computed(() => !(props.modelValue || ''))

    // ===== 值 ↔ DOM =====

    function splitTokens(value) {
        const out = []
        VAR_RE.lastIndex = 0
        let last = 0
        let m
        while ((m = VAR_RE.exec(value))) {
            if (m.index > last) out.push({ type: 'text', text: value.slice(last, m.index) })
            out.push({ type: 'var', token: m[0], name: m[2] })
            last = m.index + m[0].length
        }
        if (last < value.length) out.push({ type: 'text', text: value.slice(last) })
        return out
    }

    /** 从 DOM 重建纯文本值（chip 取 data-token 原文，忽略显示用空格） */
    function getValueFromDom() {
        const el = editorRef.value
        if (!el) return ''
        let value = ''
        for (const node of el.childNodes) {
            if (node.nodeType === Node.TEXT_NODE) {
                value += node.nodeValue
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                value += node.dataset?.token ?? node.textContent
            }
        }
        return value
    }

    /**
     * 渲染值：聚焦（编辑态）→ 纯文本；失焦 → 完整 token 转发光 chip。
     * chip 间距由 CSS margin 提供（不产生空格文本节点），
     * 保证存储值始终为 $var{name} 原文、往返展开不污染。
     */
    function renderValue(value) {
        const el = editorRef.value
        if (!el) return
        el.innerHTML = ''
        if (!value) return

        const chipMode = !focused.value && !editingToken.value
        for (const t of splitTokens(value)) {
            if (t.type === 'var' && chipMode) {
                const chip = document.createElement('span')
                chip.className = 'var-chip'
                chip.contentEditable = 'false'
                chip.dataset.token = t.token
                chip.textContent = t.name
                el.appendChild(chip)
            } else {
                // 编辑态：token 以原文文本渲染（t.text 仅文本类型存在，var 类型取 token 原文）
                el.appendChild(document.createTextNode(t.text ?? t.token ?? ''))
            }
        }
    }

    // ===== 光标管理（基于 DOM 文本偏移） =====

    function getCaretOffset() {
        const sel = window.getSelection()
        if (!sel || !sel.rangeCount || !editorRef.value.contains(sel.anchorNode)) return -1
        const range = sel.getRangeAt(0).cloneRange()
        range.selectNodeContents(editorRef.value)
        range.setEnd(sel.anchorNode, sel.anchorOffset)
        return range.toString().length
    }

    function setCaretOffset(offset) {
        const el = editorRef.value
        if (offset < 0 || !el) return
        const selection = window.getSelection()
        if (!selection) return
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
        let remaining = offset
        let node
        while ((node = walker.nextNode())) {
            const len = node.nodeValue.length
            if (remaining <= len) {
                const range = document.createRange()
                range.setStart(node, remaining)
                range.collapse(true)
                selection.removeAllRanges()
                selection.addRange(range)
                return
            }
            remaining -= len
        }
    }

    // ===== 事件 =====

    function onInput() {
        if (composing.value) return
        // 聚焦期间保持纯文本：值直接来自 textContent，光标由浏览器原生保持，不做 DOM 重建
        emit('update:modelValue', getValueFromDom())
    }

    function onCompositionEnd() {
        composing.value = false
        onInput()
    }

    function onFocus() {
        focused.value = true
        // 失焦态可能已 chip 化：聚焦后展开回纯文本，便于直接编辑
        renderValue(getValueFromDom())
        // 光标默认置于末尾（点 chip 进入的场景由 onClick 单独定位）
        if (!editingToken.value) {
            setCaretOffset(getValueFromDom().length)
        }
    }

    function onBlur() {
        focused.value = false
        editingToken.value = ''
        // 失焦：完整 token 转为发光 chip（值不变）
        renderValue(getValueFromDom())
    }

    function onClick(e) {
        const chip = e.target.closest?.('.var-chip')
        if (!chip) return
        // 点击发光 name → 展开为 $var{name} 纯文本可编辑（光标置于 } 前）
        const token = chip.dataset.token
        if (!token) return
        focused.value = true
        editingToken.value = token
        renderValue(getValueFromDom())
        const pos = getValueFromDom().indexOf(token)
        setCaretOffset(pos >= 0 ? pos + token.length - 1 : -1)
    }

    function onKeydown(e) {
        // 单行输入框：回车即确认（失焦）
        if (e.key === 'Enter' && !isMultiline.value) {
            e.preventDefault()
            editorRef.value?.blur()
        }
    }

    onMounted(() => {
        renderValue(String(props.modelValue ?? ''))
    })
    onUnmounted(() => {
        // 移除 document 级监听
    })
    // 外部更新（撤销/重置/清空）时按当前模式同步 DOM
    watch(() => props.modelValue, (val) => {
        const dom = getValueFromDom()
        if (String(val ?? '') !== dom) {
            renderValue(String(val ?? ''))
        }
    })
</script>

<style scoped>
    .var-aware-input {
        width: 100%;
        min-height: 32px;
        padding: 5px 11px;
        box-sizing: border-box;
        border: 1px solid var(--el-border-color);
        border-radius: 4px;
        background: var(--el-fill-color-blank, #fff);
        color: var(--el-text-color-regular);
        font-size: 13px;
        line-height: 1.5;
        outline: none;
        white-space: pre-wrap;
        word-break: break-all;
        text-align: left;
        cursor: text;
        transition: border-color 0.15s, box-shadow 0.15s;
    }
    .var-aware-input:hover {
        border-color: var(--el-border-color-hover, #c0c4cc);
    }
    .var-aware-input:focus {
        border-color: var(--el-color-primary);
        box-shadow: 0 0 0 1px var(--el-color-primary);
    }
    .var-aware-input.is-multiline {
        min-height: 64px;
        resize: vertical;
        overflow-y: auto;
    }
    .var-aware-input.is-empty::before {
        content: attr(data-placeholder);
        color: var(--el-text-color-placeholder);
        pointer-events: none;
    }
</style>

<!-- 动态创建的 chip 元素不带 scoped data-v 属性，样式需放非 scoped 块 -->
<style>
    .var-aware-input .var-chip {
        display: inline;
        margin: 0 4px;   /* 视觉间距由 margin 提供，不产生空格文本节点，避免值污染 */
        padding: 0 5px;
        border-radius: 4px;
        background: rgba(78, 209, 156, 0.16);
        color: #4ed19c;
        font-weight: 600;
        box-shadow: 0 0 0 1px rgba(78, 209, 156, 0.35), 0 0 8px rgba(78, 209, 156, 0.28);
        cursor: pointer;
        user-select: none;
        white-space: nowrap;
        transition: background 0.15s;
    }
    .var-aware-input .var-chip:hover {
        background: rgba(78, 209, 156, 0.3);
    }
</style>
