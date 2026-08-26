import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
    ElAlert,
    ElButton,
    ElCheckbox,
    ElCheckboxGroup,
    ElDatePicker,
    ElDialog,
    ElDropdown,
    ElDropdownItem,
    ElDropdownMenu,
    ElInput,
    ElInputNumber,
    ElLoading,
    ElOption,
    ElSelect,
    ElSlider,
    ElSwitch,
    ElTag,
    ElTimePicker
} from 'element-plus'
import 'element-plus/es/components/base/style/css'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/checkbox/style/css'
import 'element-plus/es/components/date-picker/style/css'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/dropdown/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/input-number/style/css'
import 'element-plus/es/components/loading/style/css'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/slider/style/css'
import 'element-plus/es/components/switch/style/css'
import 'element-plus/es/components/tag/style/css'
import 'element-plus/es/components/time-picker/style/css'
import PlayerView from './views/PlayerView.vue'
import '@/assets/theme.css'

const app = createApp(PlayerView)
app.use(createPinia())
;[
    ElAlert, ElButton, ElCheckbox, ElCheckboxGroup, ElDatePicker, ElDialog,
    ElDropdown, ElDropdownItem, ElDropdownMenu, ElInput, ElInputNumber,
    ElOption, ElSelect, ElSlider, ElSwitch, ElTag, ElTimePicker
].forEach(component => app.component(component.name, component))
app.use(ElLoading)
app.mount('#app')
