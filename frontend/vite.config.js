import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

const devPort = Number(process.env.EASYCODE_DEV_PORT || 5173)
const apiTarget = process.env.EASYCODE_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
    plugins: [vue()],
    resolve: {
        alias: {
            '@': fileURLToPath(new URL('./src', import.meta.url))
        }
    },
    build: {
        // IDE、Player 与原生截图文件管理器是三个独立入口；发布检查要求
        // 三者同时存在，禁止依赖上一次构建遗留的 HTML。
        outDir: path.resolve(__dirname, '../release/web'),
        emptyOutDir: true,
        rollupOptions: {
            input: {
                index: path.resolve(__dirname, 'index.html'),
                player: path.resolve(__dirname, 'player.html'),
                capture: path.resolve(__dirname, 'capture.html')
            },
            output: {
                // 不再把 Element Plus 强制合并成单个公共块。三个入口使用的
                // 控件集合不同，交给 Rollup 按入口拆分，避免 Player 被迫下载
                // IDE 才需要的表格、树、表单等组件。
                manualChunks(id) {
                    if (!id.includes('node_modules')) return undefined
                    if (id.includes('element-plus')) return undefined
                    if (id.includes('lucide-vue-next')) return 'vendor-lucide'
                    if (id.includes('/vue/') || id.includes('pinia')) return 'vendor-vue'
                    return 'vendor-common'
                }
            }
        }
    },
    server: {
        host: '0.0.0.0',
        port: devPort,
        proxy: {
            '/api': {
                target: apiTarget,
                changeOrigin: true
            }
        }
    }
})
