import { describe, expect, it } from 'vitest'
import { shortcutFromKeyboardEvent, shortcutMatches } from '../ideCommands'

function keyboard(key: string, options: Partial<KeyboardEventInit> = {}): KeyboardEvent {
    return new KeyboardEvent('keydown', { key, ...options })
}

describe('IDE shortcuts', () => {
    it('normalizes modifiers in the same order as the backend', () => {
        expect(shortcutFromKeyboardEvent(keyboard('m', { shiftKey: true, ctrlKey: true }))).toBe('Ctrl+Shift+M')
        expect(shortcutFromKeyboardEvent(keyboard('F10'))).toBe('F10')
        expect(shortcutFromKeyboardEvent(keyboard('Delete'))).toBe('Delete')
    })

    it('matches configured shortcuts case-insensitively', () => {
        expect(shortcutMatches(keyboard('f', { ctrlKey: true }), 'Ctrl+F')).toBe(true)
        expect(shortcutMatches(keyboard('f', { ctrlKey: true }), 'Ctrl+Shift+F')).toBe(false)
        expect(shortcutMatches(keyboard('f', { ctrlKey: true }), '')).toBe(false)
    })
})
