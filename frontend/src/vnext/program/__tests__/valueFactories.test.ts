import { describe, expect, it } from 'vitest'

import { controlForParameter } from '../controlContract'
import { canMaterializeProgramValue, defaultProgramValue } from '../valueFactories'

describe('portable scalar controls', () => {
    it.each(['relative_path', 'url', 'timezone'])('materializes %s as an editable text literal', (valueType) => {
        expect(canMaterializeProgramValue(valueType)).toBe(true)
        expect(defaultProgramValue(valueType, `value_${valueType}`)).toEqual({
            value_id: `value_${valueType}`,
            kind: 'literal',
            value_type: valueType,
            value: '',
        })
        expect(controlForParameter({
            parameter_id: `parameter_${valueType}`,
            display_name: valueType,
            value_type: valueType,
            required: true,
        })).toBe('text')
    })
})
