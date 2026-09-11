package com.easycode.player.web

import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AndroidPlayerWebBridgeTest {
    @Test
    fun `routes a versioned request through the fixed host boundary`() {
        val bridge = AndroidPlayerWebBridge { method, url, _ ->
            JsonObject().apply { addProperty("route", "$method $url") }
        }

        val response = JsonSupport.parseObject(
            bridge.request("""{"schema_version":1,"method":"get","url":"/api/vnext/player/runtime/bootstrap"}""").toByteArray(),
            "bridge response",
        )

        assertTrue(response.get("ok").asBoolean)
        assertEquals("GET /api/vnext/player/runtime/bootstrap", response.getAsJsonObject("payload").string("route"))
    }

    @Test
    fun `allows patch for explicit host update routes`() {
        val bridge = AndroidPlayerWebBridge { method, url, _ ->
            JsonObject().apply { addProperty("route", "$method $url") }
        }

        val response = JsonSupport.parseObject(
            bridge.request("""{"schema_version":1,"method":"PATCH","url":"/api/vnext/player/runtime/lan/peers/host_1/permissions","body":{}}""").toByteArray(),
            "bridge response",
        )

        assertTrue(response.get("ok").asBoolean)
        assertEquals("PATCH /api/vnext/player/runtime/lan/peers/host_1/permissions", response.getAsJsonObject("payload").string("route"))
    }

    @Test
    fun `rejects unknown schema and non api navigation without invoking host`() {
        var invocations = 0
        val bridge = AndroidPlayerWebBridge { _, _, _ ->
            invocations += 1
            JsonObject()
        }

        for (request in listOf(
            """{"schema_version":2,"method":"GET","url":"/api/vnext/player/runtime/bootstrap"}""",
            """{"schema_version":1,"method":"GET","url":"https://example.com"}""",
        )) {
            val response = JsonSupport.parseObject(bridge.request(request).toByteArray(), "bridge response")
            assertFalse(response.get("ok").asBoolean)
            assertEquals(400, response.get("status").asInt)
            assertEquals("android.host.request_failed", response.getAsJsonObject("error").string("code"))
            assertTrue(response.getAsJsonObject("error").string("request_id").startsWith("android_"))
        }
        assertEquals(0, invocations)
    }
}
