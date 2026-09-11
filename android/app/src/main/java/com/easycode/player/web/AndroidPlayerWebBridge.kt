package com.easycode.player.web

import android.webkit.JavascriptInterface
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.int
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonElement
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import java.util.UUID

/**
 * A deliberately tiny request bridge for the offline Player render layer.
 * It is not a general Android interface: every method is routed through the
 * host's explicit allowlist and every response uses a versioned envelope.
 */
class AndroidPlayerWebBridge(
    private val handler: (method: String, url: String, body: JsonElement) -> JsonElement,
) {
    @JavascriptInterface
    fun request(rawEnvelope: String): String {
        val requestId = "android_${UUID.randomUUID().toString().replace("-", "")}" 
        return try {
            val envelope = JsonSupport.parseObject(rawEnvelope.toByteArray(), "Android Player Host 请求")
            if (envelope.int("schema_version") != 1) error("Host 请求版本不受支持")
            val method = envelope.string("method").uppercase()
            val url = envelope.string("url")
            if (method !in setOf("GET", "POST", "PUT", "PATCH", "DELETE") || !url.startsWith("/api/")) {
                error("Host 请求不在允许范围内")
            }
            val payload = handler(method, url, envelope.get("body") ?: JsonNull.INSTANCE)
            JsonObject().apply {
                addProperty("ok", true)
                addProperty("status", 200)
                add("payload", payload)
            }.toString()
        } catch (error: Exception) {
            JsonObject().apply {
                addProperty("ok", false)
                addProperty("status", 400)
                add("error", JsonObject().apply {
                    addProperty("code", "android.host.request_failed")
                    addProperty("message", error.message ?: "Android Player Host 操作失败")
                    addProperty("request_id", requestId)
                    addProperty("retryable", false)
                    addProperty("recovery_action", "review_input")
                })
            }.toString()
        }
    }
}
