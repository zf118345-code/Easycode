import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
    ElButton, ElDialog, ElDropdown, ElDropdownItem, ElDropdownMenu,
    ElInput, ElLoading, ElOption, ElSelect, ElTree
} from 'element-plus'
import 'element-plus/es/components/base/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/tree/style/css'
import 'element-plus/es/components/dropdown/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/loading/style/css'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import '@/assets/theme.css'
import CaptureFileManagerView from '@/views/CaptureFileManagerView.vue'

const app = createApp(CaptureFileManagerView)
app.use(createPinia())
app.component(ElButton.name, ElButton)
app.component(ElDialog.name, ElDialog)
app.component(ElDropdown.name, ElDropdown)
app.component(ElDropdownItem.name, ElDropdownItem)
app.component(ElDropdownMenu.name, ElDropdownMenu)
app.component(ElInput.name, ElInput)
app.component(ElOption.name, ElOption)
app.component(ElSelect.name, ElSelect)
app.component(ElTree.name, ElTree)
app.use(ElLoading)
app.mount('#app')
