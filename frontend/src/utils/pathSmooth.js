// src/utils/pathSmooth.js (或者直接加在 gridRouter.js 里)

/**
 * 将正交折线路径字符串自动转为带圆角的 SVG 路径
 * @param {Array<{x, y}>} points - 拐点坐标序列
 * @param {number} r - 圆角半径 (例如 8-12px)
 */
export function getRoundedPathString(points, r = 8) {
    if (!points || points.length < 2) return ''
    if (points.length === 2) {
        return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`
    }

    let pathParts = []
    pathParts.push(`M ${points[0].x} ${points[0].y}`)

    for (let i = 1; i < points.length - 1; i++) {
        const prev = points[i - 1]
        const curr = points[i]
        const next = points[i + 1]

        // 计算向量
        const v1 = { x: curr.x - prev.x, y: curr.y - prev.y }
        const v2 = { x: next.x - curr.x, y: next.y - curr.y }

        const len1 = Math.hypot(v1.x, v1.y)
        const len2 = Math.hypot(v2.x, v2.y)

        // 如果线段太短，无法容纳圆角，则按原直角处理
        const currentR = Math.min(r, len1 / 2, len2 / 2)

        if (currentR <= 0 || (v1.x === v2.x && v1.y === v2.y)) {
            pathParts.push(`L ${curr.x} ${curr.y}`)
            continue
        }

        // 单位向量
        const u1 = { x: v1.x / len1, y: v1.y / len1 }
        const u2 = { x: v2.x / len2, y: v2.y / len2 }

        // 圆角起点和终点
        const startPoint = {
            x: curr.x - u1.x * currentR,
            y: curr.y - u1.y * currentR
        }
        const endPoint = {
            x: curr.x + u2.x * currentR,
            y: curr.y + u2.y * currentR
        }

        // 判断顺时针还是逆时针弧向 (sweep flag)
        // 在正交网格中，cross product 用于判断转弯方向
        const cross = u1.x * u2.y - u1.y * u2.x
        const sweep = cross > 0 ? 1 : 0

        pathParts.push(`L ${startPoint.x} ${startPoint.y}`)
        pathParts.push(`A ${currentR} ${currentR} 0 0 ${sweep} ${endPoint.x} ${endPoint.y}`)
    }

    const last = points[points.length - 1]
    pathParts.push(`L ${last.x} ${last.y}`)

    return pathParts.join(' ')
}