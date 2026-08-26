// main.js
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
    ElEmpty,
    ElForm,
    ElFormItem,
    ElInput,
    ElInputNumber,
    ElLoading,
    ElOption,
    ElOptionGroup,
    ElRadio,
    ElRadioButton,
    ElRadioGroup,
    ElScrollbar,
    ElSelect,
    ElSlider,
    ElSwitch,
    ElTable,
    ElTableColumn,
    ElTag,
    ElTimePicker,
    ElTooltip,
    ElTree
} from 'element-plus'
import 'element-plus/theme-chalk/base.css'
import 'element-plus/theme-chalk/el-alert.css'
import 'element-plus/theme-chalk/el-button.css'
import 'element-plus/theme-chalk/el-checkbox.css'
import 'element-plus/theme-chalk/el-checkbox-group.css'
import 'element-plus/theme-chalk/el-date-picker.css'
import 'element-plus/theme-chalk/el-dialog.css'
import 'element-plus/theme-chalk/el-dropdown.css'
import 'element-plus/theme-chalk/el-dropdown-item.css'
import 'element-plus/theme-chalk/el-dropdown-menu.css'
import 'element-plus/theme-chalk/el-empty.css'
import 'element-plus/theme-chalk/el-form.css'
import 'element-plus/theme-chalk/el-form-item.css'
import 'element-plus/theme-chalk/el-input.css'
import 'element-plus/theme-chalk/el-input-number.css'
import 'element-plus/theme-chalk/el-option.css'
import 'element-plus/theme-chalk/el-option-group.css'
import 'element-plus/theme-chalk/el-radio.css'
import 'element-plus/theme-chalk/el-radio-button.css'
import 'element-plus/theme-chalk/el-radio-group.css'
import 'element-plus/theme-chalk/el-scrollbar.css'
import 'element-plus/theme-chalk/el-select.css'
import 'element-plus/theme-chalk/el-slider.css'
import 'element-plus/theme-chalk/el-switch.css'
import 'element-plus/theme-chalk/el-table.css'
import 'element-plus/theme-chalk/el-table-column.css'
import 'element-plus/theme-chalk/el-tag.css'
import 'element-plus/theme-chalk/el-time-picker.css'
import 'element-plus/theme-chalk/el-tooltip.css'
import 'element-plus/theme-chalk/el-tree.css'
import 'element-plus/theme-chalk/el-loading.css'
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-message-box.css'
import 'element-plus/theme-chalk/el-notification.css'
import App from './App.vue'
import { piniaLoggerPlugin } from './stores/plugins/loggerPlugin'

// ⭐ 引入全局暗黑高级自定义样式表（放在 element-plus/dist/index.css 之后，覆盖默认样式）
import '@/assets/theme.css'

const app = createApp(App)

const pinia = createPinia()
pinia.use(piniaLoggerPlugin)

app.use(pinia)

const elementComponents = [
    ElAlert, ElButton, ElCheckbox, ElCheckboxGroup, ElDatePicker, ElDialog,
    ElDropdown, ElDropdownItem, ElDropdownMenu, ElEmpty, ElForm, ElFormItem,
    ElInput, ElInputNumber, ElOption, ElOptionGroup, ElRadio, ElRadioButton,
    ElRadioGroup, ElScrollbar, ElSelect, ElSlider, ElSwitch, ElTable,
    ElTableColumn, ElTag, ElTimePicker, ElTooltip, ElTree
]

elementComponents.forEach(component => app.component(component.name, component))
app.use(ElLoading)
app.mount('#app')
