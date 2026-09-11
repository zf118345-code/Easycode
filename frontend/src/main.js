// main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { piniaLoggerPlugin } from './stores/plugins/loggerPlugin'

import '@/assets/theme.css'

const app = createApp(App)

const pinia = createPinia()
pinia.use(piniaLoggerPlugin)

app.use(pinia)
app.mount('#app')
