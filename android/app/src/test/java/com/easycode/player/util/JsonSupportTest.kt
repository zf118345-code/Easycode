package com.easycode.player.util

import com.google.gson.JsonParser
import org.junit.Test
import kotlin.test.assertEquals

class JsonSupportTest {
    @Test
    fun canonicalJsonOrdersObjectKeysWithoutChangingArrayOrder() {
        val value = JsonParser.parseString("""{"z":1,"a":{"b":2,"a":3},"items":[2,1]}""")
        assertEquals(
            """{"a":{"a":3,"b":2},"items":[2,1],"z":1}""",
            JsonSupport.canonical(value),
        )
    }
}
