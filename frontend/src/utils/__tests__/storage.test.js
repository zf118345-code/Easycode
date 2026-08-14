import { describe, it, expect, beforeEach, vi } from 'vitest'
import { storage } from '../storage'

describe('storage', () => {
    beforeEach(() => {
        localStorage.clear()
    })

    it('set/get 基本读写', () => {
        storage.set('key1', { name: 'test' })
        const result = storage.get('key1')
        expect(result).toEqual({ name: 'test' })
    })

    it('get 返回默认值', () => {
        const result = storage.get('nonexistent', 'default')
        expect(result).toBe('default')
    })

    it('remove 删除键', () => {
        storage.set('key2', 'value')
        storage.remove('key2')
        expect(storage.get('key2')).toBeNull()
    })

    it('TTL 过期', async () => {
        storage.set('key3', 'temp', { ttl: 50 })
        expect(storage.get('key3')).toBe('temp')
        await new Promise(r => setTimeout(r, 60))
        expect(storage.get('key3')).toBeNull()
    })

    it('命名空间隔离', () => {
        storage.set('key4', 'ns1', { namespace: 'ns1' })
        storage.set('key4', 'ns2', { namespace: 'ns2' })
        expect(storage.get('key4', null, { namespace: 'ns1' })).toBe('ns1')
        expect(storage.get('key4', null, { namespace: 'ns2' })).toBe('ns2')
    })

    it('keys 列出命名空间下所有键', () => {
        storage.set('a', 1)
        storage.set('b', 2)
        const keys = storage.keys()
        expect(keys).toContain('a')
        expect(keys).toContain('b')
    })

    it('clearNamespace 清除命名空间', () => {
        storage.set('key5', 'val')
        storage.clearNamespace()
        expect(storage.get('key5')).toBeNull()
    })

    it('setRaw/getRaw 原始字符串', () => {
        storage.setRaw('rawKey', 'rawValue')
        expect(storage.getRaw('rawKey')).toBe('rawValue')
    })
})
