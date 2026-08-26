export const BLOCK_GRID = 20
export const BLOCK_GAP = 20
export const BLOCK_MIN_WIDTH = 200
export const BLOCK_MIN_HEIGHT = 160
export const BLOCK_TITLE_HEIGHT = 32
export const BLOCK_CONTENT_INSET = 20

export const snapBlockValue = value => Math.round(Number(value || 0) / BLOCK_GRID) * BLOCK_GRID

export function normalizeBlock(block = {}) {
    return {
        ...block,
        block_id: block.block_id || `block_${Date.now()}`,
        name: String(block.name || '新区块'),
        description: String(block.description || ''),
        color: block.color || 'orange',
        x: snapBlockValue(block.x),
        y: snapBlockValue(block.y),
        width: Math.max(BLOCK_MIN_WIDTH, snapBlockValue(block.width || 400)),
        height: Math.max(BLOCK_MIN_HEIGHT, snapBlockValue(block.height || 260))
    }
}

export function blockContentRect(block) {
    const value = normalizeBlock(block)
    return {
        x: value.x + BLOCK_CONTENT_INSET,
        y: value.y + BLOCK_TITLE_HEIGHT + BLOCK_CONTENT_INSET,
        width: Math.max(0, value.width - BLOCK_CONTENT_INSET * 2),
        height: Math.max(0, value.height - BLOCK_TITLE_HEIGHT - BLOCK_CONTENT_INSET * 2)
    }
}

export function nodeRect(node = {}) {
    const position = node.position || { x: 0, y: 0 }
    return {
        x: Number(position.x || 0),
        y: Number(position.y || 0),
        width: Number(node.w || node.size?.w || 160),
        height: Number(node.h || node.size?.h || 96)
    }
}

export function rectFullyContains(container, item) {
    return item.x >= container.x && item.y >= container.y
        && item.x + item.width <= container.x + container.width
        && item.y + item.height <= container.y + container.height
}

export function containedNodeIds(block, nodes = []) {
    const content = blockContentRect(block)
    return nodes.filter(node => rectFullyContains(content, nodeRect(node))).map(node => node.node_id)
}

export function blocksOverlapWithGap(first, second, gap = BLOCK_GAP) {
    const a = normalizeBlock(first)
    const b = normalizeBlock(second)
    return !(
        a.x + a.width + gap <= b.x
        || b.x + b.width + gap <= a.x
        || a.y + a.height + gap <= b.y
        || b.y + b.height + gap <= a.y
    )
}

export function canPlaceBlock(candidate, blocks = [], ignoredId = null) {
    return !blocks.some(block => block.block_id !== ignoredId && blocksOverlapWithGap(candidate, block))
}

export function resizeBlockFromHandle(block, handle, dx, dy) {
    const initial = normalizeBlock(block)
    let left = initial.x
    let top = initial.y
    let right = initial.x + initial.width
    let bottom = initial.y + initial.height
    if (handle.includes('w')) left = snapBlockValue(Math.min(right - BLOCK_MIN_WIDTH, initial.x + dx))
    if (handle.includes('e')) right = snapBlockValue(Math.max(left + BLOCK_MIN_WIDTH, right + dx))
    if (handle.includes('n')) top = snapBlockValue(Math.min(bottom - BLOCK_MIN_HEIGHT, initial.y + dy))
    if (handle.includes('s')) bottom = snapBlockValue(Math.max(top + BLOCK_MIN_HEIGHT, bottom + dy))
    return normalizeBlock({ ...initial, x: left, y: top, width: right - left, height: bottom - top })
}

export function findFreeBlockPosition(blocks = [], origin = { x: 80, y: 80 }) {
    const start = { x: snapBlockValue(origin.x), y: snapBlockValue(origin.y) }
    for (let ring = 0; ring < 80; ring += 1) {
        for (let row = 0; row <= ring; row += 1) {
            const candidate = normalizeBlock({ x: start.x + (ring - row) * BLOCK_GRID, y: start.y + row * BLOCK_GRID })
            if (canPlaceBlock(candidate, blocks)) return { x: candidate.x, y: candidate.y }
        }
    }
    return { x: start.x, y: start.y }
}
