package com.easycode.player.input

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Build
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.easycode.player.runtime.RuntimeFailure
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class EasyCodeAccessibilityService : AccessibilityService() {
    override fun onServiceConnected() {
        instance = this
    }

    override fun onDestroy() {
        if (instance === this) instance = null
        super.onDestroy()
    }

    override fun onInterrupt() = Unit
    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    fun gesture(points: List<Pair<Float, Float>>, durationMs: Long): Boolean {
        if (Build.VERSION.SDK_INT < 24) return false
        return gestureApi24(points, durationMs)
    }

    @android.annotation.TargetApi(24)
    private fun gestureApi24(points: List<Pair<Float, Float>>, durationMs: Long): Boolean {
        if (points.isEmpty()) return false
        val path = Path().apply {
            moveTo(points.first().first, points.first().second)
            points.drop(1).forEach { lineTo(it.first, it.second) }
        }
        val description = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0L, durationMs.coerceAtLeast(1L)))
            .build()
        val latch = CountDownLatch(1)
        var completed = false
        Handler(Looper.getMainLooper()).post {
            val dispatched = dispatchGesture(
                description,
                object : GestureResultCallback() {
                    override fun onCompleted(gestureDescription: GestureDescription?) {
                        completed = true
                        latch.countDown()
                    }

                    override fun onCancelled(gestureDescription: GestureDescription?) {
                        latch.countDown()
                    }
                },
                null,
            )
            if (!dispatched) latch.countDown()
        }
        return latch.await(durationMs.coerceAtLeast(1L) + 2_000L, TimeUnit.MILLISECONDS) && completed
    }

    fun replaceFocusedText(text: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: return false
        return focused.performAction(
            AccessibilityNodeInfo.ACTION_SET_TEXT,
            Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text) },
        )
    }

    fun snapshotControls(): List<AndroidControlSnapshot> = onMainThread {
        val root = rootInActiveWindow
            ?: throw RuntimeFailure("control.semantic_tree_unavailable", SEMANTIC_TREE_UNAVAILABLE)
        val result = mutableListOf<AndroidControlSnapshot>()
        fun visit(node: AccessibilityNodeInfo, path: List<Int>, depth: Int) {
            if (depth > 64) throw RuntimeFailure("control.tree_too_large", "控件树层级超过 64 层")
            val rect = Rect().also(node::getBoundsInScreen)
            result += AndroidControlSnapshot(
                packageName = node.packageName?.toString().orEmpty(),
                resourceId = node.viewIdResourceName.orEmpty(),
                text = node.text?.toString().orEmpty(),
                contentDescription = node.contentDescription?.toString().orEmpty(),
                className = node.className?.toString().orEmpty(),
                bounds = intArrayOf(rect.left, rect.top, rect.right, rect.bottom),
                path = path,
                clickable = node.isClickable,
                editable = node.isEditable || node.className?.toString().orEmpty().endsWith("EditText") ||
                    node.className?.toString().orEmpty().endsWith("AutoCompleteTextView"),
                enabled = node.isEnabled,
                visible = node.isVisibleToUser,
                checked = node.isChecked,
                selected = node.isSelected,
                focusable = node.isFocusable,
                focused = node.isFocused,
                scrollable = node.isScrollable,
            )
            if (result.size > 10_000) throw RuntimeFailure("control.tree_too_large", "控件树节点超过 10000 个")
            for (index in 0 until node.childCount) {
                node.getChild(index)?.let { child ->
                    try { visit(child, path + index, depth + 1) } finally { child.recycle() }
                }
            }
        }
        try { visit(root, emptyList(), 0) } finally { root.recycle() }
        if (AndroidControlSelectors.meaningful(result).isEmpty()) {
            throw RuntimeFailure("control.semantic_tree_unavailable", SEMANTIC_TREE_UNAVAILABLE)
        }
        result
    }

    fun captureSelectorAt(x: Int, y: Int, targetId: String, snapshot: List<AndroidControlSnapshot>? = null): Map<String, Any?> =
        AndroidControlSelectors.atPoint(snapshot ?: snapshotControls(), x, y).selector(targetId)

    fun captureCandidatesAt(
        x: Int,
        y: Int,
        snapshot: List<AndroidControlSnapshot>? = null,
    ): List<AndroidControlSnapshot> =
        AndroidControlSelectors.candidatesAt(snapshot ?: snapshotControls(), x, y)

    fun findControl(selector: Any?, targetId: String): AndroidControlSnapshot? =
        AndroidControlSelectors.find(snapshotControls(), selector, targetId)

    fun performControl(selector: Any?, targetId: String, action: String, text: String = ""): Any? = onMainThread {
        val expected = AndroidControlSelectors.find(snapshotControls(), selector, targetId) ?: return@onMainThread null
        val root = rootInActiveWindow
            ?: throw RuntimeFailure("control.reference_stale", "控件已变化，无法重新定位", transient = true)
        var result: Any? = null
        var found = false
        fun visit(node: AccessibilityNodeInfo, path: List<Int>) {
            if (found) return
            val rect = Rect().also(node::getBoundsInScreen)
            val current = AndroidControlSnapshot(
                node.packageName?.toString().orEmpty(), node.viewIdResourceName.orEmpty(),
                node.text?.toString().orEmpty(), node.contentDescription?.toString().orEmpty(),
                node.className?.toString().orEmpty(), intArrayOf(rect.left, rect.top, rect.right, rect.bottom),
                path, node.isClickable,
                node.isEditable || node.className?.toString().orEmpty().endsWith("EditText") ||
                    node.className?.toString().orEmpty().endsWith("AutoCompleteTextView"),
                node.isEnabled,
                node.isVisibleToUser, node.isChecked, node.isSelected,
                node.isFocusable, node.isFocused, node.isScrollable,
            )
            if (current.path == expected.path) {
                found = true
                result = when (action) {
                    "read" -> current.text.ifBlank { current.contentDescription }
                    "status" -> mapOf(
                        "control_status.field.enabled" to current.enabled,
                        "control_status.field.visible" to current.visible,
                        "control_status.field.checked" to current.checked,
                        "control_status.field.selected" to current.selected,
                        "control_status.field.editable" to current.editable,
                        "control_status.field.focusable" to current.focusable,
                        "control_status.field.focused" to current.focused,
                        "control_status.field.current_value" to current.text.ifBlank { current.contentDescription }.takeIf { it.isNotBlank() },
                        "control_status.field.rect" to mapOf(
                            "kind" to "rect", "x" to current.bounds[0], "y" to current.bounds[1],
                            "width" to current.bounds[2] - current.bounds[0],
                            "height" to current.bounds[3] - current.bounds[1],
                        ),
                    )
                    "click" -> clickNodeOrAncestor(node)
                    "focus" -> node.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
                    "select" -> node.performAction(AccessibilityNodeInfo.ACTION_SELECT)
                    "toggle" -> clickNodeOrAncestor(node)
                    "scroll_into_view" -> {
                        if (android.os.Build.VERSION.SDK_INT < 23) {
                            throw RuntimeFailure("control.operation_unsupported", "滚动到控件需要 Android 6.0 或以上")
                        }
                        showOnScreenApi23(node)
                    }
                    "input" -> {
                        // An already-focused control may legitimately return false for ACTION_FOCUS.
                        // SET_TEXT is the authoritative result and must still be attempted.
                        node.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
                        node.performAction(
                            AccessibilityNodeInfo.ACTION_SET_TEXT,
                            Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text) },
                        )
                    }
                    else -> throw RuntimeFailure("control.operation_unsupported", "Android 本机不支持控件操作：$action")
                }
                return
            }
            for (index in 0 until node.childCount) node.getChild(index)?.let { child ->
                try { visit(child, path + index) } finally { child.recycle() }
            }
        }
        try { visit(root, emptyList()) } finally { root.recycle() }
        if (!found) throw RuntimeFailure("control.reference_stale", "控件已变化，无法重新定位", transient = true)
        result
    }

    @android.annotation.TargetApi(23)
    private fun showOnScreenApi23(node: AccessibilityNodeInfo): Boolean =
        node.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_SHOW_ON_SCREEN.id)

    private fun clickNodeOrAncestor(node: AccessibilityNodeInfo): Boolean {
        var current: AccessibilityNodeInfo? = AccessibilityNodeInfo.obtain(node)
        try {
            while (current != null) {
                if (current.isClickable && current.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
                val parent = current.parent
                current.recycle()
                current = parent
            }
            return false
        } finally {
            current?.recycle()
        }
    }

    private fun <T> onMainThread(operation: () -> T): T {
        if (Looper.myLooper() == Looper.getMainLooper()) return operation()
        val latch = CountDownLatch(1)
        var value: T? = null
        var failure: Throwable? = null
        Handler(Looper.getMainLooper()).post {
            try { value = operation() } catch (error: Throwable) { failure = error } finally { latch.countDown() }
        }
        if (!latch.await(5, TimeUnit.SECONDS)) throw RuntimeFailure("control.driver_unavailable", "Android 控件查询超时", transient = true)
        failure?.let { throw it }
        @Suppress("UNCHECKED_CAST") return value as T
    }

    fun globalKey(name: String): Boolean = when (name.lowercase()) {
        "back" -> performGlobalAction(GLOBAL_ACTION_BACK)
        "home" -> performGlobalAction(GLOBAL_ACTION_HOME)
        "recent", "recents", "app_switch" -> performGlobalAction(GLOBAL_ACTION_RECENTS)
        "notifications" -> performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
        "quick_settings" -> performGlobalAction(GLOBAL_ACTION_QUICK_SETTINGS)
        else -> false
    }

    companion object {
        @Volatile private var instance: EasyCodeAccessibilityService? = null

        fun requireConnected(): EasyCodeAccessibilityService = instance
            ?: throw RuntimeFailure(
                "input.accessibility_disabled",
                "EasyCode 本机输入服务未启用；请在系统无障碍设置中授权后重试",
            )

        fun requireConnectedForControl(): EasyCodeAccessibilityService = instance
            ?: throw RuntimeFailure(
                "control.permission_required",
                "控件捕获需要无障碍权限；请授权 EasyCode 后重试",
            )

        fun connected(): Boolean = instance != null

    }
}
