export interface RgbaColor {
    red: number
    green: number
    blue: number
    alpha: number
}

export const COLOR_FIELD_IDS = {
    red: 'color.field.red',
    green: 'color.field.green',
    blue: 'color.field.blue',
    alpha: 'color.field.alpha',
} as const

function channel(value: unknown, fallback = 0): number {
    const number = Number(value)
    return Number.isFinite(number) ? Math.max(0, Math.min(255, Math.round(number))) : fallback
}

export function normalizeRgbaColor(value: unknown, fallback: RgbaColor = { red: 0, green: 0, blue: 0, alpha: 255 }): RgbaColor {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return { ...fallback }
    const record = value as Record<string, unknown>
    return {
        red: channel(record.red ?? record[COLOR_FIELD_IDS.red], fallback.red),
        green: channel(record.green ?? record[COLOR_FIELD_IDS.green], fallback.green),
        blue: channel(record.blue ?? record[COLOR_FIELD_IDS.blue], fallback.blue),
        alpha: channel(record.alpha ?? record[COLOR_FIELD_IDS.alpha], fallback.alpha),
    }
}

export function parseRgbaHex(raw: string, currentAlpha = 255): RgbaColor | null {
    const match = raw.trim().match(/^#?([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i)
    if (!match) return null
    let hex = match[1]
    if (hex.length === 3) hex = [...hex].map((part) => `${part}${part}`).join('')
    return {
        red: Number.parseInt(hex.slice(0, 2), 16),
        green: Number.parseInt(hex.slice(2, 4), 16),
        blue: Number.parseInt(hex.slice(4, 6), 16),
        alpha: hex.length === 8 ? Number.parseInt(hex.slice(6, 8), 16) : channel(currentAlpha, 255),
    }
}

export function formatRgbaHex(value: unknown, includeAlpha = false): string {
    const color = normalizeRgbaColor(value)
    const parts = [color.red, color.green, color.blue, ...(includeAlpha ? [color.alpha] : [])]
    return `#${parts.map((part) => part.toString(16).padStart(2, '0')).join('').toUpperCase()}`
}

export function colorRecordFields(value: unknown): Record<string, { kind: 'literal'; value_type: 'int64'; value: number }> {
    const color = normalizeRgbaColor(value)
    return Object.fromEntries(Object.entries(COLOR_FIELD_IDS).map(([name, fieldId]) => [
        fieldId,
        { kind: 'literal', value_type: 'int64', value: color[name as keyof RgbaColor] },
    ]))
}
