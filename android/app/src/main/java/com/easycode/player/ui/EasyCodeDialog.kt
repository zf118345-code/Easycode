package com.easycode.player.ui

import android.app.Activity
import android.app.Dialog
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import com.easycode.player.R
import kotlin.math.min

/**
 * EasyCode-owned decision surface.
 *
 * Business confirmations and recoverable explanations use this component so
 * the Player never falls back to the host's default alert presentation. OS
 * permission, picker and installer surfaces remain owned by Android.
 */
object EasyCodeDialog {
    enum class Tone { DEFAULT, WARNING }

    data class Action(
        val label: String,
        val emphasis: Boolean = false,
        val onClick: () -> Unit = {},
    )

    fun show(
        activity: Activity,
        title: String,
        message: String,
        actions: List<Action>,
        tone: Tone = Tone.DEFAULT,
        dismissOnOutside: Boolean = true,
    ): Dialog {
        require(actions.isNotEmpty()) { "EasyCode Dialog 至少需要一个操作" }
        require(actions.count { it.emphasis } <= 1) { "EasyCode Dialog 只能有一个主操作" }

        val dialog = Dialog(activity)
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE)
        dialog.setCanceledOnTouchOutside(dismissOnOutside)
        dialog.setCancelable(true)

        val card = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(activity, 20), dp(activity, 18), dp(activity, 20), dp(activity, 14))
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadius = dp(activity, 10).toFloat()
                setColor(activity.resources.getColor(R.color.ec_surface))
                setStroke(dp(activity, 1), activity.resources.getColor(R.color.ec_border))
            }
        }

        card.addView(TextView(activity).apply {
            text = title
            textSize = 18f
            setTextColor(activity.resources.getColor(if (tone == Tone.WARNING) R.color.ec_warning else R.color.ec_text))
            setLineSpacing(0f, 1.15f)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
        }, matchWrap())

        card.addView(TextView(activity).apply {
            text = message
            textSize = 14f
            setTextColor(activity.resources.getColor(R.color.ec_text_muted))
            setLineSpacing(dp(activity, 3).toFloat(), 1f)
            setPadding(0, dp(activity, 10), 0, dp(activity, 16))
        }, matchWrap())

        val actionArea = LinearLayout(activity).apply {
            orientation = if (actions.size > 2) LinearLayout.VERTICAL else LinearLayout.HORIZONTAL
            gravity = Gravity.END
        }
        val ordered = if (actions.size > 2) actions.reversed() else actions
        ordered.forEachIndexed { index, action ->
            val button = Button(activity).apply {
                text = action.label
                isAllCaps = false
                textSize = 14f
                minHeight = dp(activity, 44)
                minimumHeight = dp(activity, 44)
                setTextColor(
                    activity.resources.getColor(if (action.emphasis) R.color.ec_on_accent else R.color.ec_text),
                )
                backgroundTintList = ColorStateList.valueOf(
                    activity.resources.getColor(
                        when {
                            action.emphasis && tone == Tone.WARNING -> R.color.ec_warning
                            action.emphasis -> R.color.ec_accent
                            else -> R.color.ec_surface_muted
                        },
                    ),
                )
                setOnClickListener {
                    dialog.dismiss()
                    action.onClick()
                }
            }
            val params = if (actions.size > 2) {
                LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                    if (index > 0) topMargin = dp(activity, 8)
                }
            } else {
                LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply {
                    if (index > 0) marginStart = dp(activity, 8)
                }
            }
            actionArea.addView(button, params)
            if (action.emphasis) button.post { button.requestFocus() }
        }
        card.addView(actionArea, matchWrap())

        dialog.setContentView(card)
        dialog.setOnShowListener {
            dialog.window?.apply {
                setBackgroundDrawableResource(android.R.color.transparent)
                addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND)
                attributes = attributes.apply { dimAmount = 0.62f }
                val available = activity.resources.displayMetrics.widthPixels - dp(activity, 32)
                setLayout(min(available, dp(activity, 520)), WindowManager.LayoutParams.WRAP_CONTENT)
            }
        }
        if (Build.VERSION.SDK_INT >= 28) {
            dialog.window?.decorView?.accessibilityPaneTitle = title
        }
        dialog.show()
        return dialog
    }

    private fun matchWrap() = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.WRAP_CONTENT,
    )

    private fun dp(activity: Activity, value: Int): Int =
        (value * activity.resources.displayMetrics.density + 0.5f).toInt()
}
