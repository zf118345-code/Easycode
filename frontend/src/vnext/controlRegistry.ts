import type { ExecutionPlatformId, ParameterChoiceOption, ParameterDefinition, ParameterUiAction, ParameterControlType, PlatformId } from './types'

const TYPE_CONTROLS: Record<string, ParameterControlType> = {
    文本: 'text', 整数: 'number', 小数: 'number', 布尔: 'toggle',
    持续时间: 'duration', 时间点: 'time', 坐标: 'coordinate', 矩形: 'region',
    颜色: 'color', color: 'color',
    图片资源: 'resource', 控件选择器: 'control-selector', 拖拽路径: 'gesture-path',
    列表: 'list', 字典: 'key-value',
}

export function controlFor(parameter: ParameterDefinition): ParameterControlType {
    return parameter.ui?.control || TYPE_CONTROLS[parameter.value_type.replace(/^可选<|>$/g, '')] || 'expression'
}

export function controlActions(parameter: ParameterDefinition, platform?: ExecutionPlatformId): ParameterUiAction[] {
    if (platform === 'no_target') return []
    return (parameter.ui?.actions || []).filter(action => !platform || !action.platforms?.length || action.platforms.includes(platform))
}

export function choiceOptions(
    parameter: ParameterDefinition,
    platform?: ExecutionPlatformId,
    currentValue?: unknown,
): ParameterChoiceOption[] {
    return (parameter.constraints?.choices || []).flatMap((item) => {
        if (typeof item !== 'object' || item === null || !('value' in item)) {
            return [{ label: String(item), value: item }]
        }
        const choice = item as { label?: unknown; value: unknown; platforms?: PlatformId[] }
        const supported = !platform || !choice.platforms?.length
            || (platform !== 'no_target' && choice.platforms.includes(platform))
        if (supported) return [{ label: String(choice.label ?? choice.value), value: choice.value }]
        if (String(choice.value) === String(currentValue)) {
            return [{
                label: `${String(choice.label ?? choice.value)}（当前目标不可用）`,
                value: choice.value,
                disabled: true,
            }]
        }
        return []
    })
}

export function playerControlFor(parameter: ParameterDefinition): ParameterControlType {
    // Platform hosts may hide unavailable capture shortcuts, but must not
    // silently change the developer-selected value shape.
    return controlFor(parameter)
}

export function literalExpression(value: unknown): string {
    if (value === null || value === undefined) return '空'
    if (typeof value === 'string') return JSON.stringify(value)
    if (typeof value === 'number' || typeof value === 'boolean') return String(value)
    if (Array.isArray(value)) return `[${value.map(literalExpression).join(', ')}]`
    return `{${Object.entries(value as Record<string, unknown>).map(([key, child]) => `${JSON.stringify(key)}: ${literalExpression(child)}`).join(', ')}}`
}

export function parseSimpleExpression(expression: string): unknown {
    const value = expression.trim()
    if (value === '真' || value === 'true') return true
    if (value === '假' || value === 'false') return false
    if (value === '空' || value === 'null') return null
    if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value)
    if (/^(['"]).*\1$/s.test(value)) {
        try { return JSON.parse(value.replace(/^'/, '"').replace(/'$/, '"')) } catch { return value.slice(1, -1) }
    }
    if (/^(?:\[.*\]|\{.*\})$/s.test(value)) {
        try { return JSON.parse(value) } catch { return value }
    }
    return value
}
