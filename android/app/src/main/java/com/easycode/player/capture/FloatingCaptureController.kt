package com.easycode.player.capture

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Region
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import com.easycode.player.R
import com.easycode.player.input.AndroidControlSelectors
import com.easycode.player.input.AndroidControlSnapshot
import com.easycode.player.profile.PlayerControlDestination
import com.easycode.player.util.JsonSupport
import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

data class FrozenCaptureSelection(
    val actionId: String,
    val value: JsonElement? = null,
    val imageRect: IntArray? = null,
    val source: Bitmap? = null,
)

/** Owns the Android overlay UI. Pixels and controls never share a bitmap. */
class FloatingCaptureController(private val context: Context) {
    private val windows = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private var root: View? = null
    private var sourceBitmap: Bitmap? = null
    private var frozen = false
    private var bubbleX = dp(12)
    private var bubbleY = dp(96)

    fun isActive(): Boolean = root != null

    fun isFrozen(): Boolean = frozen

    fun showBubble(
        destination: PlayerControlDestination,
        message: String? = null,
        retry: Boolean = false,
        onCapture: () -> Unit,
        onCancel: () -> Unit,
    ) {
        dismiss(recycleBitmap = true)
        frozen = false

        val panel = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(5), dp(5), dp(5), dp(5))
            background = rounded(R.color.ec_surface, 28, R.color.ec_border)
            elevation = dp(10).toFloat()
        }
        val logo = ImageButton(context).apply {
            setImageResource(R.drawable.ic_launcher)
            contentDescription = "展开 EasyCode 采集控制"
            scaleType = ImageView.ScaleType.CENTER_CROP
            setPadding(dp(7), dp(7), dp(7), dp(7))
            background = rounded(R.color.ec_accent, 22)
        }
        panel.addView(logo, LinearLayout.LayoutParams(dp(46), dp(46)))

        val actions = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            // The first surface is already actionable: opening capture must not
            // require discovering that the logo expands.
            visibility = View.VISIBLE
            setPadding(dp(8), 0, 0, 0)
        }
        if (message != null) {
            actions.addView(TextView(context).apply {
                text = message
                setTextColor(context.resources.getColor(if (retry) R.color.ec_error else R.color.ec_text_muted))
                textSize = 12f
                maxWidth = dp(220)
                maxLines = 2
            }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                bottomMargin = dp(5)
            })
        }
        val actionRow = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        actionRow.addView(actionButton(if (retry) "重试" else captureLabel(destination.actionId), primary = true) {
            onCapture()
        })
        actionRow.addView(actionButton("取消") { onCancel() })
        actions.addView(actionRow)
        panel.addView(actions)

        var downRawX = 0f
        var downRawY = 0f
        var downX = 0
        var downY = 0
        var moved = false
        val slop = ViewConfiguration.get(context).scaledTouchSlop
        logo.setOnTouchListener { _, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downRawX = event.rawX
                    downRawY = event.rawY
                    downX = bubbleX
                    downY = bubbleY
                    moved = false
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = event.rawX - downRawX
                    val dy = event.rawY - downRawY
                    if (abs(dx) > slop || abs(dy) > slop) moved = true
                    if (moved) {
                        val bounds = screenBounds()
                        bubbleX = (downX + dx.roundToInt()).coerceIn(0, max(0, bounds.first - panel.width))
                        bubbleY = (downY + dy.roundToInt()).coerceIn(0, max(0, bounds.second - panel.height))
                        updateBubblePosition(panel)
                    }
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    if (!moved && event.actionMasked == MotionEvent.ACTION_UP) {
                        actions.visibility = if (actions.visibility == View.VISIBLE) View.GONE else View.VISIBLE
                        panel.post { updateBubblePosition(panel) }
                    } else if (moved) {
                        snapBubble(panel)
                    }
                    true
                }
                else -> false
            }
        }

        root = panel
        windows.addView(panel, bubbleParams())
    }

    fun hideBubbleForCapture() {
        val current = root ?: return
        runCatching { windows.removeViewImmediate(current) }
        root = null
        frozen = false
    }

    fun showFrozen(
        bitmap: Bitmap,
        destination: PlayerControlDestination,
        controlSnapshot: List<AndroidControlSnapshot>? = null,
        onConfirm: (FrozenCaptureSelection) -> Unit,
        onCancel: () -> Unit,
    ) {
        dismiss(recycleBitmap = true)
        frozen = true
        sourceBitmap = bitmap

        val container = FrameLayout(context).apply {
            isFocusableInTouchMode = true
            setOnKeyListener { _, keyCode, event ->
                if (keyCode == KeyEvent.KEYCODE_BACK && event.action == KeyEvent.ACTION_UP) {
                    onCancel()
                    true
                } else false
            }
        }
        val selection = FrozenSelectionView(
            context,
            bitmap,
            destination.actionId,
            destination.targetId,
            controlSnapshot.orEmpty(),
        )
        container.addView(selection, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT,
        ))

        val topActions = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(4), dp(4), dp(4), dp(4))
            background = rounded(R.color.ec_surface, 22, R.color.ec_border)
            elevation = dp(8).toFloat()
        }
        val fineButton = actionButton("微调") { selection.toggleFineTune() }
        val clearButton = actionButton("清空") { selection.clearSelection() }
        val parentButton = actionButton("父级") { selection.selectParent() }
        val cancelButton = actionButton("取消") { onCancel() }
        if (destination.actionId == "capture-control") {
            topActions.addView(clearButton)
            topActions.addView(parentButton)
        } else {
            topActions.addView(fineButton)
        }
        topActions.addView(cancelButton)
        container.addView(topActions, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            dp(52),
            Gravity.TOP or Gravity.END,
        ).apply {
            topMargin = dp(14)
            marginEnd = dp(12)
        })

        lateinit var confirm: Button
        confirm = actionButton("确认", primary = true) {
            val output = selection.captureSelection()
            if (output != null) {
                confirm.isEnabled = false
                confirm.text = "保存中"
                onConfirm(output)
            }
        }.apply {
            visibility = View.INVISIBLE
            minWidth = dp(92)
        }
        container.addView(confirm, FrameLayout.LayoutParams(dp(96), dp(48)))

        val finePanel = buildFinePanel(selection)
        finePanel.visibility = View.GONE
        container.addView(finePanel, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            dp(54),
            Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL,
        ).apply { bottomMargin = dp(18) })
        selection.bindFinePanel(finePanel)

        val error = TextView(context).apply {
            visibility = View.GONE
            setTextColor(context.resources.getColor(R.color.ec_text))
            textSize = 12f
            setPadding(dp(12), dp(8), dp(12), dp(8))
            background = rounded(R.color.ec_error, 8)
            elevation = dp(9).toFloat()
        }
        container.addView(error, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
            Gravity.TOP or Gravity.CENTER_HORIZONTAL,
        ).apply { topMargin = dp(76) })

        selection.onSelectionChanged = { bounds ->
            confirm.visibility = if (bounds == null) View.INVISIBLE else View.VISIBLE
            if (bounds != null) positionConfirm(container, confirm, bounds)
        }
        container.tag = FrozenUi(confirm, error)
        root = container
        windows.addView(container, frozenParams())
        container.requestFocus()
        selection.startFreezeFlash()
    }

    fun showFrozenError(message: String) {
        val current = root ?: return
        val ui = current.tag as? FrozenUi ?: return
        ui.confirm.isEnabled = true
        ui.confirm.text = "确认"
        ui.error.text = message
        ui.error.visibility = View.VISIBLE
        ui.error.postDelayed({ ui.error.visibility = View.GONE }, 4_000L)
    }

    fun onDisplayChanged(onInvalidated: () -> Unit) {
        if (frozen) onInvalidated() else root?.let { updateBubblePosition(it) }
    }

    fun dismiss(recycleBitmap: Boolean = true) {
        root?.let { runCatching { windows.removeViewImmediate(it) } }
        root = null
        frozen = false
        if (recycleBitmap) {
            sourceBitmap?.takeIf { !it.isRecycled }?.recycle()
            sourceBitmap = null
        }
    }

    private fun buildFinePanel(selection: FrozenSelectionView): LinearLayout = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER
        setPadding(dp(5), dp(4), dp(5), dp(4))
        background = rounded(R.color.ec_surface, 24, R.color.ec_border)
        elevation = dp(8).toFloat()
        addView(actionButton("左") { selection.nudge(-1, 0) })
        addView(actionButton("上") { selection.nudge(0, -1) })
        addView(actionButton("下") { selection.nudge(0, 1) })
        addView(actionButton("右") { selection.nudge(1, 0) })
        if (selection.supportsResize()) {
            addView(actionButton("缩小") { selection.resize(-1) })
            addView(actionButton("放大") { selection.resize(1) })
        }
    }

    private fun positionConfirm(container: View, confirm: View, bounds: RectF) {
        confirm.post {
            val margin = dp(10)
            val maxX = max(margin, container.width - confirm.width - margin)
            val maxY = max(dp(70), container.height - confirm.height - dp(74))
            val x = (bounds.centerX() - confirm.width / 2f).roundToInt().coerceIn(margin, maxX)
            val below = bounds.bottom.roundToInt() + margin
            val y = if (below <= maxY) below else {
                (bounds.top.roundToInt() - confirm.height - margin).coerceAtLeast(dp(70))
            }
            confirm.x = x.toFloat()
            confirm.y = y.toFloat()
        }
    }

    private fun captureLabel(actionId: String): String = when (actionId) {
        "pick-point" -> "开始取点"
        "pick-color" -> "开始取色"
        "capture-control" -> "选择控件"
        "pick-region" -> "开始框选"
        "capture-image" -> "开始录图"
        "capture-path" -> "开始录制"
        else -> "开始采集"
    }

    private fun actionButton(label: String, primary: Boolean = false, action: () -> Unit): Button =
        Button(context).apply {
            text = label
            contentDescription = label
            isAllCaps = false
            minWidth = dp(72)
            minHeight = dp(44)
            textSize = 13f
            setTextColor(context.resources.getColor(if (primary) R.color.ec_on_accent else R.color.ec_text))
            background = rounded(if (primary) R.color.ec_accent else R.color.ec_surface_muted, 20,
                if (primary) null else R.color.ec_border)
            setPadding(dp(12), 0, dp(12), 0)
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(44)).apply {
                marginStart = dp(4)
            }
            setOnClickListener { action() }
        }

    private fun rounded(fill: Int, radiusDp: Int, stroke: Int? = null): GradientDrawable =
        GradientDrawable().apply {
            cornerRadius = dp(radiusDp).toFloat()
            setColor(context.resources.getColor(fill))
            if (stroke != null) setStroke(dp(1), context.resources.getColor(stroke))
        }

    private fun bubbleParams(): WindowManager.LayoutParams = WindowManager.LayoutParams(
        ViewGroup.LayoutParams.WRAP_CONTENT,
        ViewGroup.LayoutParams.WRAP_CONTENT,
        overlayWindowType(),
        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
            WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
        PixelFormat.TRANSLUCENT,
    ).apply {
        gravity = Gravity.TOP or Gravity.START
        x = bubbleX
        y = bubbleY
    }

    private fun frozenParams(): WindowManager.LayoutParams = WindowManager.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.MATCH_PARENT,
        overlayWindowType(),
        WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
        PixelFormat.TRANSLUCENT,
    ).apply {
        gravity = Gravity.TOP or Gravity.START
        if (Build.VERSION.SDK_INT >= 28) {
            layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
        }
    }

    private fun updateBubblePosition(view: View) {
        val params = view.layoutParams as? WindowManager.LayoutParams ?: return
        val bounds = screenBounds()
        bubbleX = bubbleX.coerceIn(0, max(0, bounds.first - max(view.width, dp(46))))
        bubbleY = bubbleY.coerceIn(0, max(0, bounds.second - max(view.height, dp(46))))
        params.x = bubbleX
        params.y = bubbleY
        runCatching { windows.updateViewLayout(view, params) }
    }

    @Suppress("DEPRECATION")
    private fun overlayWindowType(): Int =
        if (Build.VERSION.SDK_INT >= 26) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        else WindowManager.LayoutParams.TYPE_PHONE

    private fun snapBubble(view: View) {
        val bounds = screenBounds()
        bubbleX = if (bubbleX + view.width / 2 < bounds.first / 2) dp(6)
        else max(dp(6), bounds.first - view.width - dp(6))
        updateBubblePosition(view)
    }

    private fun screenBounds(): Pair<Int, Int> = if (Build.VERSION.SDK_INT >= 30) {
        windows.maximumWindowMetrics.bounds.let { Pair(it.width(), it.height()) }
    } else {
        @Suppress("DEPRECATION")
        context.resources.displayMetrics.let { Pair(it.widthPixels, it.heightPixels) }
    }

    private fun dp(value: Int): Int =
        (value * context.resources.displayMetrics.density + 0.5f).toInt()

    private data class FrozenUi(val confirm: Button, val error: TextView)
}

private class FrozenSelectionView(
    context: Context,
    private val source: Bitmap,
    private val mode: String,
    private val targetId: String,
    private val controlSnapshot: List<AndroidControlSnapshot>,
) : View(context) {
    var onSelectionChanged: (RectF?) -> Unit = {}
    private val bitmapPaint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val shadePaint = Paint().apply { color = Color.argb(142, 5, 13, 10) }
    private val selectionPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = context.resources.getColor(R.color.ec_accent)
        style = Paint.Style.STROKE
        strokeWidth = dp(2).toFloat()
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val handlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = context.resources.getColor(R.color.ec_on_accent)
        style = Paint.Style.FILL
    }
    private val flashPaint = Paint().apply { color = Color.rgb(90, 225, 168) }
    private val sourceRect = Rect(0, 0, source.width, source.height)
    private val shown = RectF()
    private val start = FloatArray(2)
    private val end = FloatArray(2)
    private val path = mutableListOf<Pair<Float, Float>>()
    private var hasSelection = false
    private var gesture = Gesture.CREATE
    private var flashAlpha = 0
    private var finePanel: View? = null
    private var controlCandidates = emptyList<AndroidControlSnapshot>()
    private var controlCandidateIndex = 0

    init {
        contentDescription = "EasyCode 冻结画面采集"
        importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_YES
    }

    fun bindFinePanel(panel: View) {
        finePanel = panel
    }

    fun toggleFineTune() {
        if (!hasSelection || mode == "capture-path") return
        finePanel?.let { it.visibility = if (it.visibility == View.VISIBLE) View.GONE else View.VISIBLE }
    }

    fun clearSelection() {
        hasSelection = false
        controlCandidates = emptyList()
        controlCandidateIndex = 0
        notifySelection()
        invalidate()
    }

    fun selectParent() {
        if (mode != "capture-control" || controlCandidates.isEmpty()) return
        if (controlCandidateIndex + 1 < controlCandidates.size) {
            controlCandidateIndex += 1
            notifySelection()
            invalidate()
        }
    }

    fun supportsResize(): Boolean = mode == "pick-region" || mode == "capture-image"

    fun startFreezeFlash() {
        ValueAnimator.ofInt(92, 0).apply {
            duration = 150L
            addUpdateListener {
                flashAlpha = it.animatedValue as Int
                invalidate()
            }
            start()
        }
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        calculateShownBounds()
        canvas.drawColor(Color.BLACK)
        canvas.drawBitmap(source, sourceRect, shown, bitmapPaint)
        if (hasSelection) {
            when (mode) {
                "pick-point" -> drawPoint(canvas)
                "pick-color" -> drawColor(canvas)
                "capture-control" -> drawControl(canvas)
                "capture-path" -> drawPath(canvas)
                else -> drawRegion(canvas)
            }
        }
        if (flashAlpha > 0) {
            flashPaint.alpha = flashAlpha
            canvas.drawRect(shown, flashPaint)
            flashPaint.style = Paint.Style.STROKE
            flashPaint.strokeWidth = dp(4).toFloat()
            canvas.drawRect(shown.left + dp(2), shown.top + dp(2), shown.right - dp(2), shown.bottom - dp(2), flashPaint)
            flashPaint.style = Paint.Style.FILL
        }
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        val point = viewToBitmap(event.x, event.y) ?: return true
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                when (mode) {
                    "pick-point", "pick-color", "capture-control" -> {
                        start[0] = point.first
                        start[1] = point.second
                        end[0] = point.first
                        end[1] = point.second
                        hasSelection = true
                        if (mode == "capture-control") selectControlAt(point)
                    }
                    "capture-path" -> {
                        path.clear()
                        path += point
                        start[0] = point.first
                        start[1] = point.second
                        end[0] = point.first
                        end[1] = point.second
                        hasSelection = true
                    }
                    else -> beginRegionGesture(point)
                }
                notifySelection()
                invalidate()
            }
            MotionEvent.ACTION_MOVE -> {
                when (mode) {
                    "pick-point", "pick-color", "capture-control" -> {
                        end[0] = point.first
                        end[1] = point.second
                        if (mode == "capture-control") selectControlAt(point)
                    }
                    "capture-path" -> {
                        end[0] = point.first
                        end[1] = point.second
                        if (path.isEmpty() || distance(path.last(), point) >= 2f) path += point
                    }
                    else -> updateRegionGesture(point)
                }
                notifySelection()
                invalidate()
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                if (mode == "capture-path" && path.size < 2) path += point
                if (mode == "pick-point" || mode == "pick-color" || mode == "capture-control") {
                    end[0] = point.first
                    end[1] = point.second
                    if (mode == "capture-control") selectControlAt(point)
                }
                notifySelection()
                invalidate()
                performClick()
            }
        }
        return true
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }

    fun nudge(dx: Int, dy: Int) {
        if (!hasSelection) return
        val bounds = bitmapSelectionBounds() ?: return
        val nextDx = dx.coerceIn((-bounds.left).toInt(), (source.width - bounds.right).toInt())
        val nextDy = dy.coerceIn((-bounds.top).toInt(), (source.height - bounds.bottom).toInt())
        start[0] += nextDx
        end[0] += nextDx
        start[1] += nextDy
        end[1] += nextDy
        if (mode == "capture-path") {
            for (index in path.indices) path[index] = Pair(path[index].first + nextDx, path[index].second + nextDy)
        }
        notifySelection()
        invalidate()
    }

    fun resize(delta: Int) {
        if (!hasSelection || !supportsResize()) return
        val amount = delta * 2f
        val left = min(start[0], end[0]) - amount
        val top = min(start[1], end[1]) - amount
        val right = max(start[0], end[0]) + amount
        val bottom = max(start[1], end[1]) + amount
        if (right - left < 2 || bottom - top < 2) return
        start[0] = left.coerceIn(0f, source.width - 2f)
        start[1] = top.coerceIn(0f, source.height - 2f)
        end[0] = right.coerceIn(start[0] + 2f, source.width.toFloat())
        end[1] = bottom.coerceIn(start[1] + 2f, source.height.toFloat())
        notifySelection()
        invalidate()
    }

    fun captureSelection(): FrozenCaptureSelection? {
        if (!hasSelection) return null
        return when (mode) {
            "pick-point" -> FrozenCaptureSelection(mode, JsonObject().apply {
                addProperty("x", end[0].roundToInt().coerceIn(0, source.width - 1))
                addProperty("y", end[1].roundToInt().coerceIn(0, source.height - 1))
            })
            "pick-color" -> FrozenCaptureSelection(mode, colorJson())
            "capture-control" -> controlCandidates.getOrNull(controlCandidateIndex)?.let { candidate ->
                FrozenCaptureSelection(mode, JsonSupport.fromAny(candidate.selector(targetId)))
            }
            "pick-region" -> FrozenCaptureSelection(mode, regionJson())
            "capture-path" -> {
                if (path.size < 2 || path.size > 100_000) return null
                FrozenCaptureSelection(mode, JsonArray().also { output ->
                    path.forEach { point ->
                        output.add(JsonObject().apply {
                            addProperty("x", point.first.roundToInt().coerceIn(0, source.width - 1))
                            addProperty("y", point.second.roundToInt().coerceIn(0, source.height - 1))
                        })
                    }
                })
            }
            "capture-image" -> FrozenCaptureSelection(mode, imageRect = regionPixels(), source = source)
            else -> null
        }
    }

    private fun beginRegionGesture(point: Pair<Float, Float>) {
        val bounds = bitmapSelectionBounds()
        gesture = when {
            bounds == null -> Gesture.CREATE
            nearCorner(point, bounds) -> Gesture.RESIZE
            bounds.contains(point.first, point.second) -> Gesture.MOVE
            else -> Gesture.CREATE
        }
        if (gesture == Gesture.CREATE) {
            start[0] = point.first
            start[1] = point.second
            end[0] = point.first
            end[1] = point.second
            hasSelection = true
        } else {
            path.clear()
            path += point
        }
    }

    private fun updateRegionGesture(point: Pair<Float, Float>) {
        when (gesture) {
            Gesture.CREATE, Gesture.RESIZE -> {
                end[0] = point.first
                end[1] = point.second
            }
            Gesture.MOVE -> {
                val previous = path.lastOrNull() ?: point
                nudge((point.first - previous.first).roundToInt(), (point.second - previous.second).roundToInt())
                path.clear()
                path += point
            }
        }
    }

    private fun drawRegion(canvas: Canvas) {
        val rect = bitmapRectToView(bitmapSelectionBounds() ?: return)
        canvas.save()
        if (Build.VERSION.SDK_INT >= 26) canvas.clipOutRect(rect) else {
            @Suppress("DEPRECATION")
            canvas.clipRect(rect, Region.Op.DIFFERENCE)
        }
        canvas.drawRect(shown, shadePaint)
        canvas.restore()
        canvas.drawRect(rect, selectionPaint)
        val handle = dp(5).toFloat()
        listOf(
            Pair(rect.left, rect.top), Pair(rect.right, rect.top),
            Pair(rect.left, rect.bottom), Pair(rect.right, rect.bottom),
        ).forEach { canvas.drawCircle(it.first, it.second, handle, handlePaint) }
    }

    private fun drawPoint(canvas: Canvas) {
        canvas.drawRect(shown, shadePaint)
        val point = bitmapToView(end[0], end[1])
        selectionPaint.strokeWidth = dp(2).toFloat()
        canvas.drawCircle(point.first, point.second, dp(11).toFloat(), selectionPaint)
        canvas.drawLine(point.first - dp(18), point.second, point.first + dp(18), point.second, selectionPaint)
        canvas.drawLine(point.first, point.second - dp(18), point.first, point.second + dp(18), selectionPaint)
        drawMagnifier(canvas, point)
    }

    private fun drawColor(canvas: Canvas) {
        drawPoint(canvas)
        val x = end[0].roundToInt().coerceIn(0, source.width - 1)
        val y = end[1].roundToInt().coerceIn(0, source.height - 1)
        val sampled = source.getPixel(x, y)
        val hex = String.format("#%02X%02X%02X", Color.red(sampled), Color.green(sampled), Color.blue(sampled))
        val labelPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = dp(13).toFloat()
        }
        val swatchSize = dp(20).toFloat()
        val padding = dp(8).toFloat()
        val textWidth = labelPaint.measureText(hex)
        val anchor = bitmapToView(end[0], end[1])
        val width = padding * 3 + swatchSize + textWidth
        val height = dp(36).toFloat()
        val left = (anchor.first + dp(16)).coerceIn(shown.left + dp(4), max(shown.left + dp(4), shown.right - width - dp(4)))
        val preferredTop = anchor.second + dp(16)
        val top = if (preferredTop + height <= shown.bottom - dp(4)) preferredTop else anchor.second - height - dp(16)
        val chip = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.argb(242, 27, 32, 40) }
        canvas.drawRoundRect(left, top, left + width, top + height, dp(6).toFloat(), dp(6).toFloat(), chip)
        val swatch = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = sampled }
        canvas.drawRoundRect(left + padding, top + dp(8), left + padding + swatchSize, top + dp(28), dp(3).toFloat(), dp(3).toFloat(), swatch)
        canvas.drawText(hex, left + padding * 2 + swatchSize, top + dp(23), labelPaint)
    }

    private fun drawControl(canvas: Canvas) {
        val candidate = controlCandidates.getOrNull(controlCandidateIndex) ?: return
        val bitmapBounds = RectF(
            candidate.bounds[0].toFloat(), candidate.bounds[1].toFloat(),
            candidate.bounds[2].toFloat(), candidate.bounds[3].toFloat(),
        )
        val rect = bitmapRectToView(bitmapBounds)
        canvas.save()
        if (Build.VERSION.SDK_INT >= 26) canvas.clipOutRect(rect) else {
            @Suppress("DEPRECATION")
            canvas.clipRect(rect, Region.Op.DIFFERENCE)
        }
        canvas.drawRect(shown, shadePaint)
        canvas.restore()
        selectionPaint.strokeWidth = dp(3).toFloat()
        canvas.drawRect(rect, selectionPaint)

        val label = "${candidate.className.substringAfterLast('.')} · ${candidate.displayName}  ${controlCandidateIndex + 1}/${controlCandidates.size}"
        val labelPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = dp(13).toFloat()
        }
        val padding = dp(9).toFloat()
        val textWidth = labelPaint.measureText(label)
        val labelLeft = rect.left.coerceIn(shown.left, max(shown.left, shown.right - textWidth - padding * 2))
        val toolbarSafeTop = max(shown.top, dp(72).toFloat())
        val preferredAbove = rect.top - dp(36)
        val labelTop = if (preferredAbove >= toolbarSafeTop) {
            preferredAbove
        } else {
            (rect.top + dp(6)).coerceIn(toolbarSafeTop, max(toolbarSafeTop, shown.bottom - dp(32)))
        }
        val background = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.argb(230, 27, 32, 30) }
        canvas.drawRoundRect(
            labelLeft,
            labelTop,
            (labelLeft + textWidth + padding * 2).coerceAtMost(shown.right),
            labelTop + dp(32),
            dp(12).toFloat(),
            dp(12).toFloat(),
            background,
        )
        canvas.drawText(label, labelLeft + padding, labelTop + dp(21), labelPaint)
    }

    private fun selectControlAt(point: Pair<Float, Float>) {
        controlCandidates = try {
            AndroidControlSelectors.candidatesAt(
                controlSnapshot,
                point.first.roundToInt(),
                point.second.roundToInt(),
            )
        } catch (_: RuntimeException) {
            emptyList()
        }
        controlCandidateIndex = 0
        hasSelection = controlCandidates.isNotEmpty()
    }

    private fun drawMagnifier(canvas: Canvas, point: Pair<Float, Float>) {
        val radius = dp(48).toFloat()
        val centerX = if (point.first < width / 2f) width - radius - dp(16) else radius + dp(16)
        val centerY = max(radius + dp(76), shown.top + radius + dp(12))
        val sourceRadius = 30f
        val src = Rect(
            (end[0] - sourceRadius).roundToInt().coerceIn(0, source.width - 1),
            (end[1] - sourceRadius).roundToInt().coerceIn(0, source.height - 1),
            (end[0] + sourceRadius).roundToInt().coerceIn(1, source.width),
            (end[1] + sourceRadius).roundToInt().coerceIn(1, source.height),
        )
        val dst = RectF(centerX - radius, centerY - radius, centerX + radius, centerY + radius)
        canvas.save()
        canvas.clipPath(Path().apply { addCircle(centerX, centerY, radius, Path.Direction.CW) })
        canvas.drawBitmap(source, src, dst, bitmapPaint)
        canvas.restore()
        canvas.drawCircle(centerX, centerY, radius, selectionPaint)
        canvas.drawLine(centerX - dp(10), centerY, centerX + dp(10), centerY, selectionPaint)
        canvas.drawLine(centerX, centerY - dp(10), centerX, centerY + dp(10), selectionPaint)
    }

    private fun drawPath(canvas: Canvas) {
        canvas.drawRect(shown, shadePaint)
        if (path.size < 2) return
        val traced = Path()
        path.map(::bitmapToView).forEachIndexed { index, point ->
            if (index == 0) traced.moveTo(point.first, point.second) else traced.lineTo(point.first, point.second)
        }
        selectionPaint.strokeWidth = dp(3).toFloat()
        canvas.drawPath(traced, selectionPaint)
    }

    private fun notifySelection() {
        onSelectionChanged(selectionBoundsView())
    }

    private fun selectionBoundsView(): RectF? {
        if (!hasSelection) return null
        val bitmapBounds = bitmapSelectionBounds() ?: return null
        return bitmapRectToView(bitmapBounds)
    }

    private fun bitmapSelectionBounds(): RectF? {
        if (!hasSelection) return null
        return when (mode) {
            "capture-path" -> if (path.isEmpty()) null else RectF(
                path.minOf { it.first }, path.minOf { it.second },
                path.maxOf { it.first }, path.maxOf { it.second },
            )
            "pick-point", "pick-color" -> RectF(end[0] - 1, end[1] - 1, end[0] + 1, end[1] + 1)
            "capture-control" -> controlCandidates.getOrNull(controlCandidateIndex)?.let { candidate ->
                RectF(
                    candidate.bounds[0].toFloat(), candidate.bounds[1].toFloat(),
                    candidate.bounds[2].toFloat(), candidate.bounds[3].toFloat(),
                )
            }
            else -> RectF(
                min(start[0], end[0]), min(start[1], end[1]),
                max(start[0], end[0]), max(start[1], end[1]),
            )
        }
    }

    private fun regionJson(): JsonObject {
        val rect = regionPixels()
        return JsonObject().apply {
            addProperty("x", rect[0])
            addProperty("y", rect[1])
            addProperty("width", rect[2])
            addProperty("height", rect[3])
        }
    }

    private fun colorJson(): JsonObject {
        val x = end[0].roundToInt().coerceIn(0, source.width - 1)
        val y = end[1].roundToInt().coerceIn(0, source.height - 1)
        val sampled = source.getPixel(x, y)
        return JsonObject().apply {
            addProperty("color.field.red", Color.red(sampled))
            addProperty("color.field.green", Color.green(sampled))
            addProperty("color.field.blue", Color.blue(sampled))
            addProperty("color.field.alpha", Color.alpha(sampled))
        }
    }

    private fun regionPixels(): IntArray {
        val bounds = bitmapSelectionBounds() ?: error("请先完成框选")
        val left = bounds.left.roundToInt().coerceIn(0, source.width - 1)
        val top = bounds.top.roundToInt().coerceIn(0, source.height - 1)
        val right = bounds.right.roundToInt().coerceIn(left + 1, source.width)
        val bottom = bounds.bottom.roundToInt().coerceIn(top + 1, source.height)
        if (right - left < 2 || bottom - top < 2) error("框选区域过小")
        return intArrayOf(left, top, right - left, bottom - top)
    }

    private fun calculateShownBounds() {
        if (width == 0 || height == 0) return
        val scale = min(width.toFloat() / source.width, height.toFloat() / source.height)
        val shownWidth = source.width * scale
        val shownHeight = source.height * scale
        val left = (width - shownWidth) / 2f
        val top = (height - shownHeight) / 2f
        shown.set(left, top, left + shownWidth, top + shownHeight)
    }

    private fun viewToBitmap(x: Float, y: Float): Pair<Float, Float>? {
        calculateShownBounds()
        if (!shown.contains(x, y)) return null
        return Pair(
            ((x - shown.left) / shown.width() * source.width).coerceIn(0f, source.width - 1f),
            ((y - shown.top) / shown.height() * source.height).coerceIn(0f, source.height - 1f),
        )
    }

    private fun bitmapToView(point: Pair<Float, Float>): Pair<Float, Float> =
        bitmapToView(point.first, point.second)

    private fun bitmapToView(x: Float, y: Float): Pair<Float, Float> = Pair(
        shown.left + x / source.width * shown.width(),
        shown.top + y / source.height * shown.height(),
    )

    private fun bitmapRectToView(rect: RectF): RectF {
        val first = bitmapToView(rect.left, rect.top)
        val second = bitmapToView(rect.right, rect.bottom)
        return RectF(first.first, first.second, second.first, second.second)
    }

    private fun nearCorner(point: Pair<Float, Float>, rect: RectF): Boolean {
        val threshold = 28f * source.width / max(1f, shown.width())
        return listOf(
            Pair(rect.left, rect.top), Pair(rect.right, rect.top),
            Pair(rect.left, rect.bottom), Pair(rect.right, rect.bottom),
        ).any { abs(it.first - point.first) <= threshold && abs(it.second - point.second) <= threshold }
    }

    private fun distance(a: Pair<Float, Float>, b: Pair<Float, Float>): Float =
        abs(a.first - b.first) + abs(a.second - b.second)

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density + 0.5f).toInt()

    private enum class Gesture { CREATE, MOVE, RESIZE }
}
