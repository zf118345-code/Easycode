export const PLAYER_SCHEMA_VERSION = 3

const supportedTypes = new Set(['str', 'secret', 'number', 'slider', 'switch', 'select', 'checkbox_group', 'image_asset'])
const clone = (value) => {
    if (value === undefined) return undefined
    return JSON.parse(JSON.stringify(value))
}

export const normalizeOption = (option) => {
    if (option && typeof option === 'object' && !Array.isArray(option)) {
        const value = option.value ?? option.label ?? ''
        return { label: String(option.label ?? value), value }
    }
    return { label: String(option), value: option }
}

export const normalizePlayerSchema = (raw = {}) => {
    const schema = raw && typeof raw === 'object' ? clone(raw) : {}
    if (schema.schema_version != null && schema.schema_version !== PLAYER_SCHEMA_VERSION) {
        throw new Error(`Player 表单版本不受支持：${schema.schema_version}`)
    }
    const groups = Array.isArray(schema.groups) ? schema.groups : []
    return {
        ...schema,
        schema_version: PLAYER_SCHEMA_VERSION,
        form_title: String(schema.form_title || '客户运行配置面板'),
        groups: groups.filter(Boolean).map((group, groupIndex) => ({
            ...group,
            group_title: String(group.group_title || `配置分组 ${groupIndex + 1}`),
            fields: (Array.isArray(group.fields) ? group.fields : []).filter(Boolean).map(rawField => {
                const field = { ...rawField }
                const target = String(field.target || '').trim()
                const uiType = field.ui_type || 'str'
                if (!supportedTypes.has(uiType)) throw new Error(`不支持的 Player 控件类型：${uiType}`)
                let defaultValue = field.default
                if (defaultValue === undefined) {
                    if (uiType === 'switch') defaultValue = false
                    else if (uiType === 'number' || uiType === 'slider') defaultValue = 0
                    else if (uiType === 'checkbox_group') defaultValue = []
                    else defaultValue = ''
                }
                if (uiType === 'checkbox_group' && !Array.isArray(defaultValue)) {
                    defaultValue = defaultValue === '' || defaultValue == null ? [] : [defaultValue]
                }
                return {
                    ...field,
                    target,
                    label: String(field.label || target.slice(5) || '未命名参数'),
                    ui_type: uiType,
                    provider: String(field.provider || ''),
                    required: Boolean(field.required),
                    options: (Array.isArray(field.options) ? field.options : []).map(normalizeOption),
                    default: defaultValue
                }
            })
        }))
    }
}

export const targetSlot = (target = '') => {
    if (target.startsWith('$var.') && target.length > 5) return ['vars', target.slice(5)]
    if (target.startsWith('$ctx.') && target.length > 5) return ['ctx', target.slice(5)]
    if ((target.startsWith('$settings.') && target.length > 10) || (target.startsWith('$node.') && target.length > 6)) {
        return ['overrides', target]
    }
    return [null, null]
}

export const normalizeUserConfig = (raw = {}) => ({
    vars: { ...(raw?.vars || {}) },
    ctx: { ...(raw?.ctx || {}) },
    overrides: { ...(raw?.overrides || {}) }
})

export const buildPlayerConfig = (rawSchema, rawConfig = {}) => {
    const schema = normalizePlayerSchema(rawSchema)
    const config = normalizeUserConfig(rawConfig)
    schema.groups.forEach(group => group.fields.forEach(field => {
        const [slot, key] = targetSlot(field.target)
        if (slot && config[slot][key] === undefined) config[slot][key] = clone(field.default)
    }))
    return config
}

export const isPlayerFieldVisible = (field, model) => {
    const rule = field?.visible_if
    if (!rule || typeof rule !== 'object') return true
    let target = String(rule.target || rule.field || '')
    if (target && !target.startsWith('$')) target = `$var.${target}`
    const current = model[target]
    if ((rule.operator || 'eq') === 'ne') return current !== rule.value
    if (rule.operator === 'contains') return (Array.isArray(current) || typeof current === 'string') && current.includes(rule.value)
    if (rule.operator === 'in') return Array.isArray(rule.value) && rule.value.includes(current)
    return current === rule.value
}

export const validatePlayerConfig = (rawSchema, rawConfig) => {
    const schema = normalizePlayerSchema(rawSchema)
    const config = buildPlayerConfig(schema, rawConfig)
    const model = {}
    schema.groups.forEach(group => group.fields.forEach(field => {
        const [slot, key] = targetSlot(field.target)
        if (slot) model[field.target] = config[slot][key]
    }))
    const errors = []
    schema.groups.forEach(group => group.fields.forEach(field => {
        if (!isPlayerFieldVisible(field, model)) return
        const [slot, key] = targetSlot(field.target)
        if (!slot) {
            errors.push({ target: field.target, message: '字段目标不是受支持的运行时绑定' })
            return
        }
        const value = config[slot][key]
        if (field.required && (value === '' || value == null || (Array.isArray(value) && value.length === 0))) {
            errors.push({ target: field.target, message: `${field.label} 为必填项` })
            return
        }
        if (value === '' || value == null) return
        if (field.ui_type === 'number' || field.ui_type === 'slider') {
            if (typeof value !== 'number' || Number.isNaN(value)) errors.push({ target: field.target, message: `${field.label} 必须是数字` })
            else if (field.min != null && value < field.min) errors.push({ target: field.target, message: `${field.label} 不能小于 ${field.min}` })
            else if (field.max != null && value > field.max) errors.push({ target: field.target, message: `${field.label} 不能大于 ${field.max}` })
        }
        if (field.pattern && typeof value === 'string') {
            try {
                if (!new RegExp(`^(?:${field.pattern})$`).test(value)) errors.push({ target: field.target, message: `${field.label} 格式不正确` })
            } catch {
                errors.push({ target: field.target, message: `${field.label} 的校验表达式无效` })
            }
        }
        if (field.ui_type === 'image_asset' && value && !String(value).startsWith('asset://') && !String(value).startsWith('data:image/')) {
            errors.push({ target: field.target, message: `${field.label} 必须是项目图片或 Player 截图` })
        }
    }))
    return errors
}
