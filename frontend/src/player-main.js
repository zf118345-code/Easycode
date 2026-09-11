import './vnext/playerLegacyRuntime'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import VNextPlayerApp from './vnext/VNextPlayerApp.vue'
import '@/assets/theme.css'

createApp(VNextPlayerApp).use(createPinia()).mount('#app')
