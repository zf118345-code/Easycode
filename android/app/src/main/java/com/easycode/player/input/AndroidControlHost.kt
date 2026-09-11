package com.easycode.player.input

import com.easycode.player.runtime.RuntimeControl
import com.easycode.player.runtime.RuntimeFailure
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

class AndroidControlHost(
    private val targetId: String,
    private val control: RuntimeControl,
) : AutoCloseable {
    private val references = ConcurrentHashMap<String, Any?>()

    fun execute(opcode: String, arguments: Map<String, Any?>): Any? {
        control.checkpoint()
        val service = EasyCodeAccessibilityService.requireConnectedForControl()
        if (opcode == "control.find") {
            val selector = arguments["official.control.find.parameter.selector"]
            val found = service.findControl(selector, targetId) ?: return null
            val token = "control_ref.${UUID.randomUUID().toString().replace("-", "")}" 
            references[token] = selector
            return mapOf(
                "control_ref.field.token" to token,
                "control_ref.field.target_id" to targetId,
                "control_ref.field.name" to found.displayName,
                "control_ref.field.automation_id" to found.resourceId,
                "control_ref.field.control_type" to found.className.substringAfterLast('.'),
                "control_ref.field.rect" to mapOf(
                    "kind" to "rect", "x" to found.bounds[0], "y" to found.bounds[1],
                    "width" to found.bounds[2] - found.bounds[0], "height" to found.bounds[3] - found.bounds[1],
                ),
            )
        }
        if (opcode == "control.click_selector") {
            val selector = arguments["official.control.click_selector.parameter.selector"]
                ?: throw RuntimeFailure("control.selector_invalid", "需要控件选择器")
            val mode = arguments["official.control.click_selector.parameter.mode"]?.toString() ?: "auto"
            if (mode != "auto") throw RuntimeFailure("control.operation_unsupported", "Android 本机控件只支持自动操作")
            if (service.findControl(selector, targetId) == null) {
                throw RuntimeFailure("control.not_found", "控件未找到，未执行点击", transient = true)
            }
            val result = service.performControl(selector, targetId, "click", "")
            if (result == null || result == false) {
                throw RuntimeFailure("control.operation_failed", "控件操作未完成", transient = true)
            }
            return true
        }
        val functionId = when (opcode) {
            "control.click" -> "official.control.click"
            "control.read_text" -> "official.control.read_text"
            "control.input_text" -> "official.control.type_text"
            "control.read_status" -> "official.control.read_status"
            "control.focus" -> "official.control.focus"
            "control.set_value" -> "official.control.set_value"
            "control.select" -> "official.control.select"
            "control.toggle" -> "official.control.toggle"
            "control.scroll_into_view" -> "official.control.scroll_into_view"
            else -> throw RuntimeFailure("control.operation_unsupported", "Android 本机不支持控件操作：$opcode")
        }
        val reference = arguments["$functionId.parameter.control"] as? Map<*, *>
            ?: throw RuntimeFailure("control.reference_invalid", "需要强类型控件引用")
        if (reference["control_ref.field.target_id"]?.toString() != targetId) {
            throw RuntimeFailure("control.reference_invalid", "控件引用不属于当前目标")
        }
        val selector = references[reference["control_ref.field.token"]?.toString()]
            ?: throw RuntimeFailure("control.reference_invalid", "控件引用已失效")
        val mode = arguments["$functionId.parameter.mode"]?.toString() ?: "auto"
        if (mode != "auto") throw RuntimeFailure("control.operation_unsupported", "Android 本机控件只支持自动操作")
        val action = when (opcode) {
            "control.click" -> "click"
            "control.read_text" -> "read"
            "control.read_status" -> "status"
            "control.focus" -> "focus"
            "control.set_value", "control.input_text" -> "input"
            "control.select" -> "select"
            "control.toggle" -> "toggle"
            else -> "scroll_into_view"
        }
        val result = service.performControl(
            selector, targetId, action,
            (arguments["$functionId.parameter.content"] ?: arguments["$functionId.parameter.value"])?.toString().orEmpty(),
        )
        if (result == null) throw RuntimeFailure("control.reference_stale", "控件已变化，无法重新定位", transient = true)
        if (result is Boolean && !result) throw RuntimeFailure("control.operation_failed", "控件操作未完成", transient = true)
        return if (opcode in setOf("control.click", "control.focus", "control.set_value", "control.select", "control.toggle", "control.scroll_into_view")) true else result
    }

    override fun close() = references.clear()
}
