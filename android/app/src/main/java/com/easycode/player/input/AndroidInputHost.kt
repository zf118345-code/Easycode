package com.easycode.player.input

import android.content.Context
import com.easycode.player.runtime.RuntimeControl
import com.easycode.player.runtime.RuntimeFailure

class AndroidInputHost(
    private val context: Context,
    private val control: RuntimeControl,
) {
    fun execute(opcode: String, arguments: Map<String, Any?>): Any? {
        val service = EasyCodeAccessibilityService.requireConnected()
        return when (opcode) {
            "input.click" -> click(service, arguments)
            "input.text" -> typeText(service, arguments)
            "input.scroll" -> scroll(service, arguments)
            "input.drag" -> drag(service, arguments)
            "input.key" -> key(service, arguments)
            else -> throw RuntimeFailure("input.unsupported", "Android 本机输入不支持指令：$opcode")
        }
    }

    private fun click(service: EasyCodeAccessibilityService, arguments: Map<String, Any?>) {
        val point = displayPoint(point(argument(arguments, "official.input.click.parameter.position")))
        val button = string(arguments, "official.input.click.parameter.button", "primary")
        if (button !in setOf("primary", "left", "touch")) {
            throw RuntimeFailure("target.pointer_button_unsupported", "Android 触控只支持主按键")
        }
        val count = integer(arguments, "official.input.click.parameter.count", 1)
        if (count !in 1..100_000) {
            throw RuntimeFailure("target.invalid_click_count", "点击次数必须是 1..100000 的整数")
        }
        val hold = duration(arguments, "official.input.click.parameter.hold", 0L)
        if (hold !in 0L..60_000L) {
            throw RuntimeFailure("target.invalid_click_hold", "保持时间必须在 0 至 60 秒之间")
        }
        val interval = duration(arguments, "official.input.click.parameter.interval", 80L)
        repeat(count) { index ->
            control.checkpoint()
            if (!service.gesture(listOf(point), if (hold > 0L) hold else 60L)) failure("点击手势被系统取消")
            if (index + 1 < count) control.sleep(interval)
        }
    }

    private fun typeText(service: EasyCodeAccessibilityService, arguments: Map<String, Any?>) {
        val content = string(arguments, "official.input.type_text.parameter.content")
        val mode = string(arguments, "official.input.type_text.parameter.mode", "auto")
        if (mode !in setOf("auto", "target")) {
            throw RuntimeFailure("target.input_mode_unsupported", "Android 本机只支持通过可访问性替换当前输入框文本")
        }
        if (!service.replaceFocusedText(content)) {
            throw RuntimeFailure("target.focus_missing", "当前没有允许 EasyCode 写入的可访问性输入框")
        }
    }

    private fun scroll(service: EasyCodeAccessibilityService, arguments: Map<String, Any?>) {
        val metrics = context.resources.displayMetrics
        val mode = string(arguments, "official.input.scroll.parameter.mode", "auto")
        if (mode !in setOf("auto", "touch")) {
            throw RuntimeFailure("target.scroll_mode_unsupported", "Android 本机滚动只支持自动或触控模式")
        }
        val direction = string(arguments, "official.input.scroll.parameter.direction", "down")
        val distance = number(arguments, "official.input.scroll.parameter.distance", 0.6)
        if (!distance.isFinite() || distance <= 0.0 || distance > 1.0) {
            throw RuntimeFailure("target.invalid_scroll_distance", "Android 单次滚动距离必须在 0..1 之间")
        }
        val duration = duration(arguments, "official.input.scroll.parameter.duration", 350L)
        val rawStart = argument(arguments, "official.input.scroll.parameter.start")
        val start = if (rawStart == null) {
            Pair(metrics.widthPixels * 0.5f, metrics.heightPixels * 0.65f)
        } else {
            displayPoint(point(rawStart))
        }
        val delta = when (direction) {
            "down" -> Pair(0f, -metrics.heightPixels * distance.toFloat())
            "up" -> Pair(0f, metrics.heightPixels * distance.toFloat())
            "right" -> Pair(-metrics.widthPixels * distance.toFloat(), 0f)
            "left" -> Pair(metrics.widthPixels * distance.toFloat(), 0f)
            else -> throw RuntimeFailure("target.scroll_direction_unsupported", "滚动方向无效：$direction")
        }
        val end = Pair(
            (start.first + delta.first).coerceIn(1f, metrics.widthPixels - 1f),
            (start.second + delta.second).coerceIn(1f, metrics.heightPixels - 1f),
        )
        if (!service.gesture(listOf(start, end), duration)) failure("滚动手势被系统取消")
        control.sleep(duration(arguments, "official.input.scroll.parameter.hold", 80L))
    }

    private fun drag(service: EasyCodeAccessibilityService, arguments: Map<String, Any?>) {
        val raw = argument(arguments, "official.input.drag.parameter.path")
        val points = when (raw) {
            is List<*> -> raw.map(::point)
            is Map<*, *> -> (raw["points"] as? List<*>)?.map(::point).orEmpty()
            else -> emptyList()
        }
        if (points.size < 2 || points.size > 100_000) {
            throw RuntimeFailure("target.invalid_drag_path", "拖拽路径必须包含 2..100000 个点")
        }
        val easing = string(arguments, "official.input.drag.parameter.easing", "linear")
        if (easing != "linear") {
            throw RuntimeFailure(
                "target.drag_easing_unsupported",
                "Android AccessibilityService 不能忠实实现 $easing 缓动；当前只支持 linear",
            )
        }
        val duration = duration(arguments, "official.input.drag.parameter.duration", 350L)
        if (duration !in 1L..60_000L) {
            throw RuntimeFailure("target.invalid_duration", "移动时长必须在 1 毫秒至 60 秒之间")
        }
        val displayPoints = points.map(::displayPoint)
        if (!service.gesture(displayPoints, duration)) failure("拖拽手势被系统取消")
    }

    private fun key(service: EasyCodeAccessibilityService, arguments: Map<String, Any?>) {
        val action = string(arguments, "official.input.key.parameter.action", "press")
        val hold = duration(arguments, "official.input.key.parameter.hold", 0L)
        if (action != "press" || hold != 0L) {
            throw RuntimeFailure(
                "target.invalid_key_action",
                "Android AccessibilityService 只支持一次性全局按键，不伪装按下/松开或长按",
            )
        }
        val raw = argument(arguments, "official.input.key.parameter.key")
        val name = when (raw) {
            is String -> raw
            is Map<*, *> -> raw["key"]?.toString() ?: raw["name"]?.toString().orEmpty()
            else -> raw?.toString().orEmpty()
        }
        if (!service.globalKey(name)) {
            throw RuntimeFailure("target.invalid_key", "Android 无障碍不支持此按键：$name")
        }
    }

    private fun argument(arguments: Map<String, Any?>, id: String): Any? = arguments[id]

    private fun string(arguments: Map<String, Any?>, id: String, default: String = ""): String =
        arguments[id]?.toString() ?: default

    private fun integer(arguments: Map<String, Any?>, id: String, default: Int): Int {
        val value = arguments[id] ?: return default
        val number = value as? Number
            ?: throw RuntimeFailure("runtime.argument_type", "整数参数无效：$id")
        val double = number.toDouble()
        if (!double.isFinite() || double % 1.0 != 0.0 || double < Int.MIN_VALUE || double > Int.MAX_VALUE) {
            throw RuntimeFailure("runtime.argument_type", "整数参数无效：$id")
        }
        return double.toInt()
    }

    private fun number(arguments: Map<String, Any?>, id: String, default: Double): Double {
        val value = arguments[id] ?: return default
        return (value as? Number)?.toDouble()
            ?: throw RuntimeFailure("runtime.argument_type", "数值参数无效：$id")
    }

    private fun duration(arguments: Map<String, Any?>, id: String, default: Long): Long = when (val value = arguments[id]) {
        null -> default
        is Number -> value.toLong()
        is Map<*, *> -> (value["milliseconds"] as? Number)?.toLong()
            ?: throw RuntimeFailure("runtime.argument_type", "持续时间参数无效：$id")
        else -> throw RuntimeFailure("runtime.argument_type", "持续时间参数无效：$id")
    }.coerceAtLeast(0L)

    private fun point(value: Any?): Pair<Float, Float> {
        val map = value as? Map<*, *>
            ?: throw RuntimeFailure("target.invalid_point", "坐标参数必须是 point")
        val x = map["x"] as? Number ?: throw RuntimeFailure("target.invalid_point", "坐标缺少 x")
        val y = map["y"] as? Number ?: throw RuntimeFailure("target.invalid_point", "坐标缺少 y")
        val result = Pair(x.toFloat(), y.toFloat())
        if (!result.first.isFinite() || !result.second.isFinite()) {
            throw RuntimeFailure("target.invalid_point", "坐标必须是有限数值")
        }
        return result
    }

    private fun displayPoint(value: Pair<Float, Float>): Pair<Float, Float> {
        val metrics = context.resources.displayMetrics
        if (value.first < 0f || value.second < 0f ||
            value.first >= metrics.widthPixels || value.second >= metrics.heightPixels
        ) {
            throw RuntimeFailure("target.invalid_point", "坐标超出当前 Android 屏幕范围")
        }
        return value
    }

    private fun failure(message: String): Nothing = throw RuntimeFailure("target.driver_failed", message, transient = true)
}
