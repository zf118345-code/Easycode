package com.easycode.player.input

import com.easycode.player.runtime.RuntimeFailure
import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertSame

class AndroidControlModelTest {
    private fun node(
        resourceId: String = "demo:id/login",
        className: String = "android.widget.Button",
        bounds: IntArray = intArrayOf(100, 200, 500, 320),
        path: List<Int> = listOf(0, 1),
    ) = AndroidControlSnapshot(
        packageName = "demo", resourceId = resourceId, text = "登录",
        contentDescription = "登录按钮", className = className, bounds = bounds,
        path = path, clickable = true, editable = false, enabled = true,
    )

    @Test
    fun selectorRoundTripsWithoutNativeNodeHandle() {
        val original = node()
        val selector = original.selector("target.phone")
        assertEquals(original, AndroidControlSelectors.find(listOf(original), selector, "target.phone"))
        assertEquals(original, AndroidControlSelectors.atPoint(listOf(original), 200, 250))
    }

    @Test
    fun validSelectorCanReturnNormalNoMatch() {
        val original = node()
        val selector = original.selector("target.phone").toMutableMap().apply {
            this["control_selector.field.resource_id"] = "demo:id/missing"
        }
        assertNull(AndroidControlSelectors.find(listOf(original), selector, "target.phone"))
    }

    @Test
    fun surfaceViewDoesNotBecomeAFakeControl() {
        val surface = node(resourceId = "", className = "android.view.SurfaceView")
        val error = assertFailsWith<RuntimeFailure> {
            AndroidControlSelectors.atPoint(listOf(surface), 200, 250)
        }
        assertEquals("control.semantic_tree_unavailable", error.errorId)
    }

    @Test
    fun selectorCannotCrossTarget() {
        val original = node()
        val error = assertFailsWith<RuntimeFailure> {
            AndroidControlSelectors.find(listOf(original), original.selector("target.phone"), "target.other")
        }
        assertEquals("control.reference_invalid", error.errorId)
    }

    @Test
    fun candidatesStartAtDeepestControlAndOnlyWalkItsParentPath() {
        val root = node(
            resourceId = "",
            className = "android.widget.FrameLayout",
            bounds = intArrayOf(0, 0, 1080, 2400),
            path = emptyList(),
        )
        val panel = node(
            resourceId = "demo:id/login_panel",
            className = "android.widget.LinearLayout",
            bounds = intArrayOf(40, 120, 800, 600),
            path = listOf(0),
        )
        val button = node(path = listOf(0, 1))
        val sibling = node(
            resourceId = "demo:id/other",
            bounds = intArrayOf(600, 200, 900, 320),
            path = listOf(1),
        )

        val candidates = AndroidControlSelectors.candidatesAt(
            listOf(root, panel, button, sibling),
            200,
            250,
        )

        assertEquals(listOf(button, panel, root), candidates)
        assertSame(root, AndroidControlSelectors.find(listOf(root, panel, button), root.selector("target.phone"), "target.phone"))
    }
}
