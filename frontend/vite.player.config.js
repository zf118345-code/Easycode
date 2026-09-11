import { fileURLToPath, URL } from 'node:url'
import path from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'


const playerCaptureEntry = {
    name: 'easycode-player-capture-entry',
    transformIndexHtml: {
        order: 'pre',
        handler(html, context) {
            if (!context.path.endsWith('/capture.html')) return html
            return html.replace('/src/capture-main.js', '/src/player-capture-main.js')
        },
    },
}


export default defineConfig({
    // Relative assets allow the same compiled Player graph to run from the
    // Windows loopback host and the APK's isolated app-assets origin.
    base: './',
    plugins: [playerCaptureEntry, vue()],
    resolve: {
        alias: {
            '@': fileURLToPath(new URL('./src', import.meta.url)),
        },
    },
    build: {
        // Android 5+ can receive an independently updated System WebView.
        // Keep the shared Player bundle at the oldest engine we explicitly
        // probe in the native host; newer syntax must not silently turn the
        // Player into a blank page on otherwise supported API levels.
        target: 'chrome64',
        outDir: path.resolve(__dirname, '../release/player-web'),
        emptyOutDir: true,
        sourcemap: false,
        rollupOptions: {
            input: {
                player: path.resolve(__dirname, 'player.html'),
                capture: path.resolve(__dirname, 'capture.html'),
                console: path.resolve(__dirname, 'console.html'),
            },
            output: {
                manualChunks(id) {
                    if (!id.includes('node_modules')) return undefined
                    if (id.includes('lucide-vue-next')) return 'vendor-lucide'
                    if (id.includes('/vue/') || id.includes('pinia')) return 'vendor-vue'
                    return 'vendor-player'
                },
            },
        },
    },
})
