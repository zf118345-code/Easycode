package com.easycode.player.input

import android.app.Activity
import android.app.Instrumentation
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.util.Log
import com.easycode.player.runtime.RuntimeFailure

/** Offline real-device Harness; no AndroidX test dependency is required. */
class ControlVerificationInstrumentation : Instrumentation() {
    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        start()
    }

    override fun onStart() {
        super.onStart()
        val result = Bundle()
        try {
            Log.i(TAG, "stage=start-settings")
            targetContext.startActivity(
                Intent(Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            )
            val serviceDeadline = System.currentTimeMillis() + 30_000L
            while (!EasyCodeAccessibilityService.connected() && System.currentTimeMillis() < serviceDeadline) {
                Thread.sleep(100L)
            }

            Log.i(TAG, "stage=require-service")
            val service = EasyCodeAccessibilityService.requireConnectedForControl()
            val targetId = "target.android.local.harness"
            Log.i(TAG, "stage=snapshot-initial")
            val initial = AndroidControlSelectors.meaningful(service.snapshotControls())
            check(initial.any { it.text.isNotBlank() }) { "系统设置必须暴露可读语义节点" }
            val search = initial.firstOrNull {
                it.clickable && (
                    listOf(it.resourceId, it.text, it.contentDescription).any { value -> value.contains("search", ignoreCase = true) } ||
                        it.resourceId.endsWith(":id/header_view")
                    )
            } ?: error("系统设置没有暴露搜索控件")
            val selector = search.selector(targetId)
            Log.i(TAG, "stage=find-click")
            check(service.findControl(selector, targetId) != null) { "Accessibility 选择器无法重新定位" }
            check(service.performControl(selector, targetId, "click") == true) { "ACTION_CLICK 未生效" }

            Thread.sleep(800L)
            Log.i(TAG, "stage=snapshot-editable")
            val editable = AndroidControlSelectors.meaningful(service.snapshotControls()).firstOrNull { it.editable }
                ?: error("点击搜索后没有出现可编辑控件")
            val editableSelector = editable.selector(targetId)
            val probe = "EasyCodeAccessibilityProbe"
            Log.i(TAG, "stage=input")
            check(service.performControl(editableSelector, targetId, "input", probe) == true) { "ACTION_SET_TEXT 未生效" }
            Thread.sleep(300L)
            Log.i(TAG, "stage=readback")
            check(AndroidControlSelectors.meaningful(service.snapshotControls()).any { it.editable && it.text == probe }) {
                "ACTION_SET_TEXT 无法从真实控件树回读"
            }
            try {
                service.findControl(selector, "target.other")
                error("跨目标选择器没有被拒绝")
            } catch (error: RuntimeFailure) {
                check(error.errorId == "control.reference_invalid") { "跨目标错误语义不正确：${error.errorId}" }
            }

            Log.i(TAG, "stage=surface-fallback")
            targetContext.startActivity(
                Intent(targetContext, SurfaceOnlyHarnessActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            )
            Thread.sleep(500L)
            try {
                service.snapshotControls()
                error("SurfaceView 页面被错误识别成控件树")
            } catch (error: RuntimeFailure) {
                check(error.errorId == "control.semantic_tree_unavailable") {
                    "SurfaceView 降级错误语义不正确：${error.errorId}"
                }
                check(error.message?.contains("图像、OCR 或坐标") == true) {
                    "SurfaceView 降级提示没有给出可操作替代方案"
                }
            }
            result.putString(
                "stream",
                "Accessibility capture/find/click/input/readback and SurfaceView fallback passed",
            )
            Log.i(TAG, "stage=passed")
            finish(Activity.RESULT_OK, result)
        } catch (error: Throwable) {
            Log.e(TAG, "stage=failed", error)
            result.putString("stream", "FAILED: ${error::class.java.simpleName}: ${error.message}")
            finish(Activity.RESULT_CANCELED, result)
        }
    }

    companion object {
        private const val TAG = "EasyCodeControlHarness"
    }
}
