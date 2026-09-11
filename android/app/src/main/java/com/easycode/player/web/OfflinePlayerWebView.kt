package com.easycode.player.web

import android.annotation.SuppressLint
import android.graphics.Color
import android.net.Uri
import android.webkit.MimeTypeMap
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import java.io.ByteArrayInputStream
import kotlin.math.roundToInt

private const val PLAYER_ORIGIN = "https://player.easycode.local"
private const val PLAYER_ASSET_PREFIX = "player-web/"

/** Loads only APK-owned Player assets and blocks external navigation/network. */
@SuppressLint("SetJavaScriptEnabled")
fun WebView.configureOfflinePlayer(bridge: AndroidPlayerWebBridge) {
    setBackgroundColor(Color.TRANSPARENT)
    settings.javaScriptEnabled = true
    settings.domStorageEnabled = true
    settings.allowFileAccess = false
    settings.allowContentAccess = false
    settings.javaScriptCanOpenWindowsAutomatically = false
    settings.setSupportMultipleWindows(false)
    settings.blockNetworkLoads = true
    settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
    applySystemFontScale(resources.configuration.fontScale)
    addJavascriptInterface(bridge, "EasyCodeAndroid")
    webViewClient = object : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
            request.url.host != "player.easycode.local"

        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse {
            val uri = request.url
            if (uri.scheme != "https" || uri.host != "player.easycode.local") return denied()
            val relative = uri.path.orEmpty().removePrefix("/")
            if (relative.isBlank() || relative.contains("..") || relative.contains('\\')) return denied()
            return try {
                val bytes = context.assets.open(PLAYER_ASSET_PREFIX + relative).use { it.readBytes() }
                WebResourceResponse(mimeType(relative), "UTF-8", 200, "OK", securityHeaders(), ByteArrayInputStream(bytes))
            } catch (_: Exception) {
                WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", securityHeaders(), ByteArrayInputStream(ByteArray(0)))
            }
        }
    }
    loadUrl("$PLAYER_ORIGIN/player.html")
}

/** Keep CSS layout shared while respecting the Android user's text-size setting. */
fun WebView.applySystemFontScale(fontScale: Float) {
    settings.textZoom = (fontScale * 100f).roundToInt().coerceIn(85, 200)
}

private fun denied() = WebResourceResponse(
    "text/plain", "UTF-8", 403, "Forbidden", securityHeaders(), ByteArrayInputStream(ByteArray(0)),
)

private fun securityHeaders() = mapOf(
    "Content-Security-Policy" to "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options" to "nosniff",
    "Cache-Control" to "no-store",
)

private fun mimeType(path: String): String = when (path.substringAfterLast('.', "").lowercase()) {
    "html" -> "text/html"
    "js" -> "application/javascript"
    "css" -> "text/css"
    "json" -> "application/json"
    "svg" -> "image/svg+xml"
    "png" -> "image/png"
    "jpg", "jpeg" -> "image/jpeg"
    "webp" -> "image/webp"
    "woff2" -> "font/woff2"
    else -> MimeTypeMap.getSingleton().getMimeTypeFromExtension(path.substringAfterLast('.', "")) ?: "application/octet-stream"
}
