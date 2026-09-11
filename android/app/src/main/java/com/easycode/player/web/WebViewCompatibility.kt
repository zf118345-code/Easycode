package com.easycode.player.web

data class WebViewCompatibility(
    val compatible: Boolean,
    val detectedMajor: Int?,
    val reason: String,
)

private val CHROME_MAJOR = Regex("(?:^|\\s)Chrome/(\\d+)(?:\\.|\\s|$)", RegexOption.IGNORE_CASE)

fun webViewCompatibility(userAgent: String, minimumMajor: Int): WebViewCompatibility {
    val detected = CHROME_MAJOR.find(userAgent)?.groupValues?.getOrNull(1)?.toIntOrNull()
    if (detected == null) {
        return WebViewCompatibility(false, null, "无法识别 Android System WebView 版本")
    }
    if (detected < minimumMajor) {
        return WebViewCompatibility(
            false,
            detected,
            "当前 Android System WebView 为 $detected，Player 至少需要 $minimumMajor",
        )
    }
    return WebViewCompatibility(true, detected, "")
}
