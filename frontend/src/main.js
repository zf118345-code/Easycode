// main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import { piniaLoggerPlugin } from './stores/plugins/loggerPlugin'

// ⭐ 引入全局暗黑高级自定义样式表（放在 element-plus/dist/index.css 之后，覆盖默认样式）
import '@/assets/theme.css'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
}

const pinia = createPinia()
pinia.use(piniaLoggerPlugin)

app.use(pinia)
app.use(ElementPlus)
app.mount('#app')