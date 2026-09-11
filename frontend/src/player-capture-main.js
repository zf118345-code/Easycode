import '@/assets/theme.css'

const root = document.querySelector('#app')
if (root) {
    root.innerHTML = `
        <main class="player-capture-ready" role="status" aria-live="polite">
            <span class="player-capture-ready__mark" aria-hidden="true"></span>
            <div>
                <strong>终端捕获宿主已就绪</strong>
                <p>选择与确认由 Windows 原生捕获窗口处理。</p>
            </div>
        </main>
    `
}

const style = document.createElement('style')
style.textContent = `
    html,body,#app{width:100%;height:100%;margin:0}
    body{background:var(--app-bg-page,#111318);color:var(--app-text-primary,#e9ecf2);font-family:var(--app-font-sans,"Segoe UI Variable","Microsoft YaHei UI",sans-serif)}
    .player-capture-ready{box-sizing:border-box;display:flex;align-items:center;justify-content:center;gap:12px;width:100%;height:100%;padding:24px}
    .player-capture-ready__mark{width:10px;height:10px;border-radius:50%;background:var(--app-color-success,#67c23a);box-shadow:0 0 0 5px color-mix(in srgb,var(--app-color-success,#67c23a) 16%,transparent)}
    .player-capture-ready strong{font-size:13px;font-weight:600}.player-capture-ready p{margin:5px 0 0;color:var(--app-text-muted,#8d94a3);font-size:11px}
`
document.head.append(style)

window.chrome?.webview?.postMessage({ event: 'capture-file-manager-ready', player_only: true })
