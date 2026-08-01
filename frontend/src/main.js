// main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import { piniaLoggerPlugin } from './stores/plugins/loggerPlugin'

const app = createApp(App)

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
}

const pinia = createPinia()
pinia.use(piniaLoggerPlugin) // 注册 Pinia 状态日志插件

app.use(pinia)
app.use(ElementPlus)
app.mount('#app')