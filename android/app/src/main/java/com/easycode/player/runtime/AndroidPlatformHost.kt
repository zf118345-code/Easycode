package com.easycode.player.runtime

import android.content.ComponentName
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import com.easycode.player.capture.AndroidVisionHost
import com.easycode.player.capture.ScreenCaptureService
import com.easycode.player.input.AndroidInputHost
import com.easycode.player.input.AndroidControlHost
import com.easycode.player.input.EasyCodeAccessibilityService
import java.time.Instant
import java.util.UUID

class AndroidPlatformHost(
    private val context: Context,
    private val targetId: String,
    private val targetName: String,
    private val control: RuntimeControl,
) {
    fun execute(opcode: String, arguments: Map<String, Any?>): Any? {
        return when (opcode) {
        "target.status" -> targetStatus(resolveTarget(arguments, optional = true))
        "target.wait_online" -> {
            val requested = resolveTarget(arguments, optional = false)
            val timeout = duration(arguments.entries.firstOrNull { it.key.endsWith(".parameter.timeout") }?.value, 60_000L)
            val deadline = System.nanoTime() + timeout * 1_000_000L
            while (true) {
                control.checkpoint()
                val status = targetStatus(requested)
                if (status["target_info.field.online"] == true) return status
                if (System.nanoTime() >= deadline) return null
                control.sleep(100L)
            }
            @Suppress("UNREACHABLE_CODE") null
        }
        "host.app.start" -> startApplication(arguments)
        "clipboard.read_text" -> readClipboard()
        "clipboard.write_text" -> {
            val content = arguments["official.clipboard.write_text.parameter.content"] as? String
                ?: throw RuntimeFailure("runtime.argument_type", "剪贴板内容必须是文本")
            clipboard().setPrimaryClip(ClipData.newPlainText("EasyCode", content))
            null
        }
        "host.app.wait_exit" -> throw RuntimeFailure(
            "application.lifecycle_unavailable",
            "Android 本机无法可靠观察其他应用退出，不能伪造等待结果",
        )
            else -> throw RuntimeFailure("runtime.operation_unsupported", "Android 平台宿主不支持：$opcode")
        }
    }

    private fun clipboard(): ClipboardManager =
        context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
            ?: throw RuntimeFailure("clipboard.unavailable", "当前设备没有系统剪贴板")

    private fun readClipboard(): String? {
        val clip = clipboard().primaryClip ?: return null
        if (clip.itemCount <= 0) return null
        return clip.getItemAt(0).coerceToText(context)?.toString()
    }

    private fun resolveTarget(arguments: Map<String, Any?>, optional: Boolean): String {
        val raw = arguments.entries.firstOrNull { it.key.endsWith(".parameter.target") }?.value
        if (raw == null && optional) return targetId
        val id = (raw as? Map<*, *>)?.get("target_id")?.toString().orEmpty()
        if (id.isBlank()) throw RuntimeFailure("target.reference_invalid", "目标引用缺少稳定 target_id")
        if (id != targetId) throw RuntimeFailure("target.reference_missing", "APK 不能切换到另一台设备目标：$id")
        return id
    }

    private fun targetStatus(requested: String): Map<String, Any?> {
        if (requested.isNotBlank() && requested != targetId) throw RuntimeFailure("target.reference_missing", "目标引用不属于当前手机")
        val metrics = context.resources.displayMetrics
        val capabilities = buildList {
            add("application.launch")
            add("host.clipboard")
            if (ScreenCaptureService.ready()) add("target.capture_frame")
            if (EasyCodeAccessibilityService.connected()) {
                add("target.input")
                add("input.key")
                add("control.semantic")
            }
        }
        return mapOf(
            "target_info.field.target_id" to targetId,
            "target_info.field.name" to targetName.ifBlank { "当前 Android 手机" },
            "target_info.field.kind" to "android_local",
            "target_info.field.online" to true,
            "target_info.field.ready" to true,
            "target_info.field.viewport" to mapOf(
                "kind" to "rect", "x" to 0, "y" to 0,
                "width" to metrics.widthPixels, "height" to metrics.heightPixels,
            ),
            "target_info.field.space_version" to "$targetId:${metrics.widthPixels}x${metrics.heightPixels}",
            "target_info.field.capabilities" to capabilities,
            "target_info.field.detail" to "Android 本机运行时",
        )
    }

    private fun startApplication(arguments: Map<String, Any?>): Map<String, Any?> {
        val application = arguments["official.application.start.parameter.application"] as? Map<*, *>
            ?: throw RuntimeFailure("application.reference_invalid", "应用参数必须是 application_ref")
        val platform = application["application_ref.field.platform"]?.toString().orEmpty()
        if (platform !in setOf("android_local", "android_native")) {
            throw RuntimeFailure("application.reference_invalid", "Android APK 不能启动非 Android 应用引用")
        }
        val extra = arguments["official.application.start.parameter.arguments"] as? List<*> ?: emptyList<Any?>()
        if (extra.isNotEmpty()) {
            throw RuntimeFailure("application.reference_invalid", "Android 本机首版不接受自由命令行参数")
        }
        val packageName = application["application_ref.field.package"]?.toString().orEmpty()
        val activity = application["application_ref.field.activity"]?.toString().orEmpty()
        if (!PACKAGE.matches(packageName) || (activity.isNotBlank() && !ACTIVITY.matches(activity))) {
            throw RuntimeFailure("application.reference_invalid", "Android 包名或 Activity 格式无效")
        }
        val launch = if (activity.isBlank()) {
            context.packageManager.getLaunchIntentForPackage(packageName)
                ?: throw RuntimeFailure("application.not_found", "设备没有可启动的应用：$packageName")
        } else {
            Intent(Intent.ACTION_MAIN).setComponent(
                ComponentName(packageName, if (activity.startsWith('.')) packageName + activity else activity),
            )
        }
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            context.startActivity(launch)
        } catch (error: Exception) {
            throw RuntimeFailure("application.launch_failed", "Android 应用启动失败：${error.message}", true, error)
        }
        return mapOf(
            "application_run_ref.field.run_id" to "application_run.${UUID.randomUUID()}",
            "application_run_ref.field.platform" to "android_local",
            "application_run_ref.field.application" to application,
            "application_run_ref.field.process_id" to 0,
            "application_run_ref.field.target_id" to targetId,
            "application_run_ref.field.started_at" to Instant.now().toString(),
        )
    }

    private fun duration(value: Any?, default: Long): Long = when (value) {
        null -> default
        is Number -> value.toLong()
        is Map<*, *> -> (value["milliseconds"] as? Number)?.toLong()
            ?: throw RuntimeFailure("runtime.argument_type", "持续时间参数无效")
        else -> throw RuntimeFailure("runtime.argument_type", "持续时间参数无效")
    }.coerceAtLeast(0L)

    companion object {
        private val PACKAGE = Regex("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+")
        private val ACTIVITY = Regex("\\.?[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)*")
    }
}

class AndroidStandardImageHost(
    private val vision: AndroidVisionHost,
    private val input: AndroidInputHost,
    private val controls: AndroidControlHost,
    private val control: RuntimeControl,
) {
    fun execute(opcode: String, arguments: Map<String, Any?>): Any? = when (opcode) {
        "standard.image.wait_visible" -> waitVisible(arguments, "official.image.wait_visible")
        "standard.image.wait_hidden" -> waitHidden(arguments, "official.image.wait_hidden")
        "standard.image.click_once" -> clickOnce(arguments, "official.image.click_once")
        "standard.image.click_until_hidden" -> clickUntilHidden(arguments, "official.image.click_until_hidden")
        "standard.image.click_position_until_visible" -> clickPositionUntilCondition(
            arguments, "official.image.click_position_until_visible", true,
        )
        "standard.image.click_position_until_hidden" -> clickPositionUntilCondition(
            arguments, "official.image.click_position_until_hidden", false,
        )
        "standard.text.match" -> textMatch(arguments, "official.text.match")
        "standard.text.wait_visible" -> textWaitVisible(arguments, "official.text.wait_visible")
        "standard.control.wait_visible" -> controlWait(arguments, "official.control.wait_visible", true)
        "standard.control.wait_hidden" -> controlWait(arguments, "official.control.wait_hidden", false)
        else -> throw RuntimeFailure("runtime.operation_unsupported", "Android 标准函数不支持：$opcode")
    }

    private fun controlWait(arguments: Map<String, Any?>, owner: String, visible: Boolean): Any? {
        val timeout = duration(arguments["$owner.parameter.timeout"], 10_000L)
        val interval = duration(arguments["$owner.parameter.interval"], 100L).coerceAtLeast(16L)
        val deadline = System.nanoTime() + timeout * 1_000_000L
        while (true) {
            control.checkpoint()
            val result = controls.execute(
                "control.find",
                mapOf("official.control.find.parameter.selector" to arguments["$owner.parameter.selector"]),
            )
            if ((result != null) == visible) return if (visible) result else true
            if (System.nanoTime() >= deadline) return if (visible) null else false
            control.sleep(interval)
        }
    }

    private fun textMatch(arguments: Map<String, Any?>, owner: String): Any? {
        val result = vision.execute("text.recognize", ocrArguments(arguments, owner)) as? Map<*, *>
            ?: return null
        return if (matches(result["ocr_result.field.text"]?.toString().orEmpty(), arguments, owner)) result else null
    }

    private fun textWaitVisible(arguments: Map<String, Any?>, owner: String): Any? {
        val timeout = duration(arguments["$owner.parameter.timeout"], 3_000L)
        val interval = duration(arguments["$owner.parameter.interval"], 100L).coerceAtLeast(16L)
        val stable = integer(arguments["$owner.parameter.stable_frames"], 1).coerceIn(1, 100)
        val deadline = System.nanoTime() + timeout * 1_000_000L
        var consecutive = 0
        var latest: Any? = null
        while (true) {
            control.checkpoint()
            val result = vision.execute("text.recognize", ocrArguments(arguments, owner)) as? Map<*, *>
            val matched = result != null && matches(
                result["ocr_result.field.text"]?.toString().orEmpty(), arguments, owner,
            )
            if (matched) {
                consecutive++
                latest = result
            } else {
                consecutive = 0
                latest = null
            }
            if (consecutive >= stable) return latest
            if (System.nanoTime() >= deadline) return null
            control.sleep(interval)
        }
    }

    private fun matches(actual: String, arguments: Map<String, Any?>, owner: String): Boolean {
        val expected = arguments["$owner.parameter.text"]?.toString().orEmpty()
        return textMatches(
            actual,
            expected,
            arguments["$owner.parameter.mode"]?.toString() ?: "contains",
        )
    }

    companion object {
        internal fun textMatches(actual: String, expected: String, mode: String): Boolean {
            if (expected.isEmpty()) throw RuntimeFailure("runtime.argument_range", "目标文字不能为空")
            return when (mode) {
            "exact" -> actual == expected
            "contains" -> expected in actual
            "regex" -> try {
                Regex(expected).containsMatchIn(actual)
            } catch (error: IllegalArgumentException) {
                throw RuntimeFailure("text.regex_invalid", "正则表达式无效：${error.message}", cause = error)
            }
            else -> throw RuntimeFailure("runtime.argument_range", "文字匹配方式无效")
            }
        }
    }

    private fun ocrArguments(source: Map<String, Any?>, owner: String): Map<String, Any?> = buildMap {
        for (name in listOf("region", "language", "preprocess")) {
            if (source.containsKey("$owner.parameter.$name")) {
                put("official.text.recognize.parameter.$name", source["$owner.parameter.$name"])
            }
        }
        put("official.text.recognize.parameter.frame", null)
    }

    private fun waitVisible(arguments: Map<String, Any?>, owner: String): Any? {
        val timeout = duration(arguments["$owner.parameter.timeout"], 3_000L)
        val interval = duration(arguments["$owner.parameter.interval"], 100L).coerceAtLeast(16L)
        val stable = integer(arguments["$owner.parameter.stable_frames"], 1).coerceIn(1, 100)
        val deadline = System.nanoTime() + timeout * 1_000_000L
        var consecutive = 0
        var latest: Any? = null
        while (true) {
            control.checkpoint()
            latest = vision.execute("vision.find", baseArguments(arguments, owner, "official.image.find"))
            consecutive = if (latest != null) consecutive + 1 else 0
            if (consecutive >= stable) return latest
            if (System.nanoTime() >= deadline) return null
            control.sleep(interval)
        }
    }

    private fun waitHidden(arguments: Map<String, Any?>, owner: String): Boolean {
        val timeout = duration(arguments["$owner.parameter.timeout"], 3_000L)
        val interval = duration(arguments["$owner.parameter.interval"], 100L).coerceAtLeast(16L)
        val stable = integer(arguments["$owner.parameter.stable_frames"], 2).coerceIn(1, 100)
        val deadline = System.nanoTime() + timeout * 1_000_000L
        var hidden = 0
        while (true) {
            control.checkpoint()
            val found = vision.execute("vision.find", baseArguments(arguments, owner, "official.image.find"))
            hidden = if (found == null) hidden + 1 else 0
            if (hidden >= stable) return true
            if (System.nanoTime() >= deadline) return false
            control.sleep(interval)
        }
    }

    private fun clickOnce(arguments: Map<String, Any?>, owner: String): Any? {
        val match = waitVisible(arguments, owner) as? Map<*, *> ?: return null
        val point = match["image_match.field.center"]
        input.execute("input.click", mapOf(
            "official.input.click.parameter.position" to point,
            "official.input.click.parameter.button" to arguments["$owner.parameter.button"],
            "official.input.click.parameter.count" to 1,
            "official.input.click.parameter.interval" to 0,
        ))
        return match
    }

    private fun clickUntilHidden(arguments: Map<String, Any?>, owner: String): Map<String, Any?> {
        val timeout = duration(arguments["$owner.parameter.timeout"], 10_000L)
        val interval = duration(arguments["$owner.parameter.interval"], 200L).coerceAtLeast(16L)
        val stable = integer(arguments["$owner.parameter.stable_frames"], 2).coerceIn(1, 100)
        val deadline = System.nanoTime() + timeout * 1_000_000L
        var clicks = 0
        var hidden = 0
        var lastMatch: Map<*, *>? = null
        while (true) {
            control.checkpoint()
            val match = vision.execute("vision.find", baseArguments(arguments, owner, "official.image.find")) as? Map<*, *>
            if (match == null) hidden++ else {
                hidden = 0
                lastMatch = match
                input.execute("input.click", mapOf(
                    "official.input.click.parameter.position" to match["image_match.field.center"],
                    "official.input.click.parameter.button" to arguments["$owner.parameter.button"],
                    "official.input.click.parameter.count" to 1,
                    "official.input.click.parameter.interval" to 0,
                ))
                clicks++
            }
            if (hidden >= stable) return mapOf(
                "image_click_loop_result.field.click_count" to clicks,
                "image_click_loop_result.field.hidden" to true,
                "image_click_loop_result.field.last_match" to lastMatch,
            )
            if (System.nanoTime() >= deadline) return mapOf(
                "image_click_loop_result.field.click_count" to clicks,
                "image_click_loop_result.field.hidden" to false,
                "image_click_loop_result.field.last_match" to lastMatch,
            )
            control.sleep(interval)
        }
    }

    private fun clickPositionUntilCondition(
        arguments: Map<String, Any?>,
        owner: String,
        visible: Boolean,
    ): Map<String, Any?> {
        val timeout = duration(arguments["$owner.parameter.timeout"], 10_000L)
        val interval = duration(arguments["$owner.parameter.interval"], 200L).coerceAtLeast(16L)
        val stable = integer(
            arguments["$owner.parameter.stable_frames"], if (visible) 1 else 2,
        ).coerceIn(1, 100)
        val deadline = System.nanoTime() + timeout * 1_000_000L
        var clicks = 0
        var consecutive = 0
        var lastMatch: Map<*, *>? = null
        while (true) {
            control.checkpoint()
            val match = vision.execute(
                "vision.find", baseArguments(arguments, owner, "official.image.find"),
            ) as? Map<*, *>
            val reached = (match != null) == visible
            if (reached) {
                consecutive++
                if (match != null) lastMatch = match
                if (consecutive >= stable) return mapOf(
                    "image_click_condition_result.field.reached" to true,
                    "image_click_condition_result.field.click_count" to clicks,
                    "image_click_condition_result.field.last_match" to lastMatch,
                )
            } else {
                consecutive = 0
                if (match != null) lastMatch = match
                input.execute("input.click", mapOf(
                    "official.input.click.parameter.position" to arguments["$owner.parameter.position"],
                    "official.input.click.parameter.button" to arguments["$owner.parameter.button"],
                    "official.input.click.parameter.count" to 1,
                    "official.input.click.parameter.interval" to 0,
                ))
                clicks++
            }
            if (System.nanoTime() >= deadline) return mapOf(
                "image_click_condition_result.field.reached" to false,
                "image_click_condition_result.field.click_count" to clicks,
                "image_click_condition_result.field.last_match" to lastMatch,
            )
            control.sleep(interval)
        }
    }

    private fun baseArguments(source: Map<String, Any?>, owner: String, target: String): Map<String, Any?> = buildMap {
        for (name in listOf("image", "similarity", "region")) {
            if (source.containsKey("$owner.parameter.$name")) put("$target.parameter.$name", source["$owner.parameter.$name"])
        }
        put("$target.parameter.frame", null)
    }

    private fun duration(value: Any?, default: Long): Long = when (value) {
        null -> default
        is Number -> value.toLong()
        is Map<*, *> -> (value["milliseconds"] as? Number)?.toLong()
            ?: throw RuntimeFailure("runtime.argument_type", "持续时间参数无效")
        else -> throw RuntimeFailure("runtime.argument_type", "持续时间参数无效")
    }.coerceAtLeast(0L)

    private fun integer(value: Any?, default: Int): Int = when (value) {
        null -> default
        is Number -> value.toInt()
        else -> throw RuntimeFailure("runtime.argument_type", "整数参数无效")
    }
}
