import { describe, it, expect } from 'vitest'
import { useUndoRedo } from '../useUndoRedo'

function createHarness(initial) {
    let state = JSON.parse(JSON.stringify(initial))
    const undoRedo = useUndoRedo({
        getState: () => JSON.parse(JSON.stringify(state)),
        setState: (snapshot) => {
            state = JSON.parse(JSON.stringify(snapshot))
        }
    })
    return { undoRedo, get: () => state, set: (next) => { state = JSON.parse(JSON.stringify(next)) } }
}

describe('useUndoRedo', () => {
    it('commit -> 修改 -> undo 恢复到修改前，redo 重做', () => {
        const { undoRedo, get, set } = createHarness({ value: 1 })

        expect(undoRedo.canUndo.value).toBe(false)

        undoRedo.commit()
        set({ value: 2 })

        expect(get().value).toBe(2)
        expect(undoRedo.canUndo.value).toBe(true)

        undoRedo.undo()
        expect(get().value).toBe(1)
        expect(undoRedo.canRedo.value).toBe(true)

        undoRedo.redo()
        expect(get().value).toBe(2)
        expect(undoRedo.canRedo.value).toBe(false)
    })

    it('commit 新操作后清空 redo 栈', () => {
        const { undoRedo, get, set } = createHarness({ value: 1 })

        undoRedo.commit()
        set({ value: 2 })
        undoRedo.undo()
        expect(undoRedo.canRedo.value).toBe(true)

        // 在已撤销的状态上继续修改：commit 快照的是当前 value=1
        undoRedo.commit()
        set({ value: 3 })
        expect(undoRedo.canRedo.value).toBe(false)

        undoRedo.undo()
        expect(get().value).toBe(1)
    })

    it('undo 栈为空时 undo 不报错且状态不变', () => {
        const { undoRedo, get } = createHarness({ value: 1 })
        undoRedo.undo()
        expect(get().value).toBe(1)
    })

    it('快照为深拷贝，后续修改不污染历史', () => {
        const { undoRedo, get, set } = createHarness({ nested: { items: [1, 2] } })
        undoRedo.commit()
        set({ nested: { items: [1, 2, 3] } })

        undoRedo.undo()
        expect(get().nested.items).toEqual([1, 2])
    })

    it('clear 清空历史', () => {
        const { undoRedo, get, set } = createHarness({ value: 1 })
        undoRedo.commit()
        set({ value: 2 })
        undoRedo.clear()
        expect(undoRedo.canUndo.value).toBe(false)
        expect(undoRedo.canRedo.value).toBe(false)
        expect(get().value).toBe(2)
    })
})
