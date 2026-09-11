package com.easycode.player.input

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView

/** Debug-only real-host fixture for Accessibility control execution. */
class SemanticControlHarnessActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val density = resources.displayMetrics.density
        fun dp(value: Int): Int = (value * density).toInt()

        val input = EditText(this).apply {
            hint = "请输入测试内容"
            contentDescription = "EasyCode 测试输入框"
            setText("初始文本")
            setSingleLine(true)
        }
        val markerBitmap = Bitmap.createBitmap(64, 64, Bitmap.Config.ARGB_8888).apply {
            for (y in 0 until height) for (x in 0 until width) {
                setPixel(x, y, when {
                    x in 27..36 || y in 27..36 -> Color.rgb(255, 255, 255)
                    x < 32 && y < 32 -> Color.rgb(230, 70, 50)
                    x >= 32 && y < 32 -> Color.rgb(40, 180, 90)
                    x < 32 -> Color.rgb(50, 100, 220)
                    else -> Color.rgb(245, 195, 40)
                })
            }
        }
        val visionMarker = ImageView(this).apply {
            contentDescription = "EasyCode 图像测试标记"
            setImageBitmap(markerBitmap)
            scaleType = ImageView.ScaleType.CENTER
        }
        val status = TextView(this).apply {
            text = "尚未确认"
            contentDescription = "EasyCode 测试结果"
            textSize = 18f
            setPadding(0, dp(24), 0, dp(24))
        }
        val confirm = Button(this).apply {
            text = "确认测试"
            contentDescription = "EasyCode 测试确认"
            setOnClickListener { status.text = "已确认：${input.text}" }
        }
        val coordinateConfirm = Button(this).apply {
            text = "坐标点击测试"
            contentDescription = "EasyCode 坐标测试"
            setOnClickListener { status.text = "坐标点击已验证" }
        }
        var gestureStartX = 0f
        var gestureStartY = 0f
        val gestureSurface = View(this).apply {
            contentDescription = "EasyCode 手势测试区"
            setBackgroundColor(0xff30465c.toInt())
            minimumHeight = dp(180)
            isFocusable = true
            setOnTouchListener { _, event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN -> {
                        gestureStartX = event.x
                        gestureStartY = event.y
                    }
                    MotionEvent.ACTION_UP -> {
                        val dx = event.x - gestureStartX
                        val dy = event.y - gestureStartY
                        status.text = if (kotlin.math.abs(dx) > kotlin.math.abs(dy)) {
                            "拖拽已验证"
                        } else {
                            "滚动已验证"
                        }
                    }
                }
                true
            }
        }
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(32), dp(72), dp(32), dp(32))
            addView(TextView(context).apply {
                text = "EasyCode Android 控件运行 Harness"
                textSize = 24f
            }, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            addView(visionMarker, 64, 64)
            addView(input, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            addView(confirm, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            addView(coordinateConfirm, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            addView(gestureSurface, ViewGroup.LayoutParams.MATCH_PARENT, dp(180))
            addView(status, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        }
        setContentView(layout)
    }
}
