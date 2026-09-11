import { describe, expect, it } from 'vitest'

import { compatibleAvailableValues } from '../controlContract'
import { isProgramTypeCompatible } from '../typeCompatibility'
import { compatibleProgramValues } from '../valueFactories'
import type { AvailableProgramValue } from '../types'

describe('Program type compatibility', () => {
    it('mirrors the canonical safe widening rules', () => {
        expect(isProgramTypeCompatible('int64', 'float64')).toBe(true)
        expect(isProgramTypeCompatible('int64', 'percentage')).toBe(true)
        expect(isProgramTypeCompatible('string', 'relative_path')).toBe(true)
        expect(isProgramTypeCompatible('string', 'enum<mouse_button>')).toBe(true)
        expect(isProgramTypeCompatible('asset_ref<image>', 'asset_ref')).toBe(true)
        expect(isProgramTypeCompatible('int64', 'optional<float64>')).toBe(true)
        expect(isProgramTypeCompatible('null', 'optional<string>')).toBe(true)
    })

    it('accepts only recursively serializable message values', () => {
        expect(isProgramTypeCompatible('list<map<string,string>>', 'message_value')).toBe(true)
        expect(isProgramTypeCompatible('map<string,list<int64>>', 'message_value')).toBe(true)
        expect(isProgramTypeCompatible('map<int64,string>', 'message_value')).toBe(false)
        expect(isProgramTypeCompatible('record<image_match>', 'message_value')).toBe(false)
    })

    it('keeps incompatible domain values out of reference pickers', () => {
        const values: AvailableProgramValue[] = [
            { source: 'local', id: 'count', display_name: '次数', value_type: 'int64' },
            { source: 'local', id: 'text', display_name: '文本', value_type: 'string' },
            { source: 'local', id: 'point', display_name: '坐标', value_type: 'point' },
        ]

        expect(compatibleProgramValues(values, 'float64').map((item) => item.id)).toEqual(['count'])
        expect(compatibleAvailableValues(values, 'url').map((item) => item.id)).toEqual(['text'])
        expect(compatibleAvailableValues(values, 'rect')).toEqual([])
    })
})
