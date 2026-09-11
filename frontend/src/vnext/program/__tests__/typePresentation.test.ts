import { describe, expect, it } from 'vitest'
import { programTypeDisplayName } from '../typePresentation'

describe('program type presentation', () => {
    it('keeps internal type IDs out of common and nested user-facing labels', () => {
        expect(programTypeDisplayName('int64')).toBe('整数')
        expect(programTypeDisplayName('optional<image_match>')).toBe('可选的图像匹配结果')
        expect(programTypeDisplayName('optional<timezone>')).toBe('可选的时区')
        expect(programTypeDisplayName('instance_ref')).toBe('Player 实例')
        expect(programTypeDisplayName('directory_ref<read_write>')).toBe('文件夹')
        expect(programTypeDisplayName('optional<http_body>')).toBe('可选的请求正文')
        expect(programTypeDisplayName('map<string,list<int64>>')).toBe('字典（文本 → 列表（整数））')
    })
})
