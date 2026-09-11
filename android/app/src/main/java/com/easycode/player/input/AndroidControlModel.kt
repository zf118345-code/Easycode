package com.easycode.player.input

import com.easycode.player.runtime.RuntimeFailure

private const val PREFIX = "control_selector.field."
const val ANDROID_CONTROL_PROVIDER = "android_accessibility"
const val SEMANTIC_TREE_UNAVAILABLE = "当前页面不提供可识别控件，请使用图像、OCR 或坐标"

data class AndroidControlSnapshot(
    val packageName: String,
    val resourceId: String,
    val text: String,
    val contentDescription: String,
    val className: String,
    val bounds: IntArray,
    val path: List<Int>,
    val clickable: Boolean,
    val editable: Boolean,
    val enabled: Boolean,
    val visible: Boolean? = null,
    val checked: Boolean? = null,
    val selected: Boolean? = null,
    val focusable: Boolean? = null,
    val focused: Boolean? = null,
    val scrollable: Boolean? = null,
) {
    val displayName: String get() = text.ifBlank {
        contentDescription.ifBlank { resourceId.substringAfterLast('/').ifBlank { className.substringAfterLast('.') } }
    }
    val area: Long get() = (bounds[2] - bounds[0]).coerceAtLeast(0).toLong() *
        (bounds[3] - bounds[1]).coerceAtLeast(0).toLong()
    val semantic: Boolean get() {
        val leaf = className.substringAfterLast('.').lowercase()
        if (leaf in setOf("surfaceview", "textureview", "viewrootimpl", "decorview")) return false
        val semanticRoles = setOf(
            "button", "imagebutton", "textview", "edittext", "checkbox", "radiobutton",
            "switch", "seekbar", "spinner", "listview", "recyclerview", "scrollview", "webview",
            "autocompletetextview", "multiautocompletetextview",
        )
        return resourceId.isNotBlank() || text.isNotBlank() || contentDescription.isNotBlank() ||
            clickable || editable || leaf in semanticRoles
    }

    fun contains(x: Int, y: Int): Boolean = x >= bounds[0] && x < bounds[2] && y >= bounds[1] && y < bounds[3]

    fun selector(targetId: String): Map<String, Any?> = linkedMapOf(
        "${PREFIX}schema_version" to 1L,
        "${PREFIX}provider" to ANDROID_CONTROL_PROVIDER,
        "${PREFIX}target_id" to targetId,
        "${PREFIX}package_name" to packageName,
        "${PREFIX}resource_id" to resourceId,
        "${PREFIX}name" to displayName,
        "${PREFIX}text" to text,
        "${PREFIX}content_description" to contentDescription,
        "${PREFIX}class_name" to className,
        "${PREFIX}control_type" to className.substringAfterLast('.'),
        "${PREFIX}index" to 0L,
        "${PREFIX}path" to path,
        "${PREFIX}rect" to mapOf(
            "kind" to "rect", "x" to bounds[0], "y" to bounds[1],
            "width" to (bounds[2] - bounds[0]).coerceAtLeast(0),
            "height" to (bounds[3] - bounds[1]).coerceAtLeast(0),
        ),
        "${PREFIX}ancestor_path" to emptyList<Any>(),
    )
}

object AndroidControlSelectors {
    fun meaningful(nodes: List<AndroidControlSnapshot>): List<AndroidControlSnapshot> =
        nodes.filter { it.semantic && it.area > 0L }

    fun atPoint(nodes: List<AndroidControlSnapshot>, x: Int, y: Int): AndroidControlSnapshot {
        val semantic = meaningful(nodes)
        if (semantic.isEmpty()) throw RuntimeFailure("control.semantic_tree_unavailable", SEMANTIC_TREE_UNAVAILABLE)
        return semantic.filter { it.contains(x, y) }.minWithOrNull(compareBy<AndroidControlSnapshot> { it.area }.thenByDescending { it.path.size })
            ?: throw RuntimeFailure("control.not_at_point", "当前位置没有可识别控件；请重新取点，或使用图像、OCR 或坐标")
    }

    /**
     * Returns the selectable control chain from the deepest semantic node to
     * its structural parents. Parents are deliberately included even when
     * they have no label of their own: their stable tree path still makes
     * them useful container targets, and a single parent action is predictable
     * on a touch screen in a way that choosing among many children is not.
     */
    fun candidatesAt(nodes: List<AndroidControlSnapshot>, x: Int, y: Int): List<AndroidControlSnapshot> {
        val deepest = atPoint(nodes, x, y)
        return nodes.asSequence()
            .filter { it.area > 0L && it.contains(x, y) }
            .filter { candidate ->
                candidate.path.size <= deepest.path.size &&
                    deepest.path.take(candidate.path.size) == candidate.path
            }
            .distinctBy { it.path }
            .sortedWith(compareByDescending<AndroidControlSnapshot> { it.path.size }.thenBy { it.area })
            .toList()
    }

    fun find(nodes: List<AndroidControlSnapshot>, raw: Any?, targetId: String): AndroidControlSnapshot? {
        val selector = raw as? Map<*, *>
            ?: throw RuntimeFailure("control.selector_invalid", "需要强类型控件选择器")
        val provider = selector["${PREFIX}provider"]?.toString().orEmpty()
        if (provider.isNotBlank() && provider != ANDROID_CONTROL_PROVIDER) {
            throw RuntimeFailure("control.selector_provider_mismatch", "控件选择器不属于 Android 本机适配器")
        }
        val sourceTarget = selector["${PREFIX}target_id"]?.toString().orEmpty()
        if (sourceTarget.isNotBlank() && sourceTarget != targetId) {
            throw RuntimeFailure("control.reference_invalid", "控件选择器不属于当前目标")
        }
        val expected = linkedMapOf(
            "package" to selector["${PREFIX}package_name"]?.toString().orEmpty(),
            "resource" to selector["${PREFIX}resource_id"]?.toString().orEmpty(),
            "text" to selector["${PREFIX}text"]?.toString().orEmpty(),
            "description" to selector["${PREFIX}content_description"]?.toString().orEmpty(),
            "class" to selector["${PREFIX}class_name"]?.toString().orEmpty(),
        )
        val path = (selector["${PREFIX}path"] as? List<*>)?.mapNotNull { (it as? Number)?.toInt() }.orEmpty()
        if (expected.values.none(String::isNotBlank) && path.isEmpty()) {
            throw RuntimeFailure("control.selector_invalid", "控件选择器缺少可重新定位的稳定字段")
        }
        val semantic = if (path.isNotEmpty()) nodes.filter { it.area > 0L } else meaningful(nodes)
        if (semantic.isEmpty()) throw RuntimeFailure("control.semantic_tree_unavailable", SEMANTIC_TREE_UNAVAILABLE)
        val candidates = semantic.filter { node ->
            (expected.getValue("package").isBlank() || node.packageName == expected.getValue("package")) &&
                (expected.getValue("resource").isBlank() || node.resourceId == expected.getValue("resource")) &&
                (expected.getValue("text").isBlank() || node.text == expected.getValue("text")) &&
                (expected.getValue("description").isBlank() || node.contentDescription == expected.getValue("description")) &&
                (expected.getValue("class").isBlank() || node.className == expected.getValue("class"))
        }
        if (path.isNotEmpty()) candidates.firstOrNull { it.path == path }?.let { return it }
        val index = (selector["${PREFIX}index"] as? Number)?.toInt()?.coerceAtLeast(0) ?: 0
        return candidates.getOrNull(index)
    }
}
