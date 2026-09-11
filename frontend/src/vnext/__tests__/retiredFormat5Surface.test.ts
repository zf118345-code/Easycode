import { describe, expect, it } from 'vitest'
import apiSource from '../api.ts?raw'
import storeSource from '../store.ts?raw'
import typesSource from '../types.ts?raw'
import ideSource from '../components/VNextIdeV6.vue?raw'
import designerSource from '../components/VNextPlayerWorkspace.vue?raw'
import playerSource from '../VNextPlayerApp.vue?raw'

const productionSurface = () => [apiSource, storeSource, typesSource, ideSource, designerSource, playerSource].join('\n')

describe('format 6 retired frontend surface', () => {
    it('不再引用格式 5 源码、文本分析、旧运行或页面拓扑入口', () => {
        const surface = productionSurface()
        const retiredMarkers = [
            '/api/vnext/sources',
            '/api/vnext/analyze',
            '/api/vnext/edit/call-argument',
            '/api/vnext/run-project',
            'src/main.easy',
            'matched_pages',
            'topology_page',
            'EasyCodeEditor',
        ]

        for (const marker of retiredMarkers) expect(surface).not.toContain(marker)
    })

    it('Player 只从格式 6 绑定目录和运行接口取得真实能力', () => {
        const surface = productionSurface()
        expect(surface).toContain('/api/vnext/player/binding-sources')
        expect(surface).toContain('/api/vnext/player/preview-run')
        expect(surface).toContain('/api/vnext/player/runtime/run')
    })
})
