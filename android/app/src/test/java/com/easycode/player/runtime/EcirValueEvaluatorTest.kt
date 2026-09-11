package com.easycode.player.runtime

import com.easycode.player.util.JsonSupport
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import org.junit.Test

class EcirValueEvaluatorTest {
    private val evaluator = EcirValueEvaluator(RuntimeControl())

    @Test
    fun strictOptionalMemberAccessReturnsAFieldOrFailsWithThePortableError() {
        val expression = JsonSupport.gson.toJsonTree(
            mapOf(
                "kind" to "member_access",
                "source" to mapOf("kind" to "reference", "scope" to "local", "symbol_id" to "match"),
                "field_id" to "image_match.field.center",
                "result_type" to "point",
            ),
        )
        val populated = EvaluationScope(
            mutableMapOf("match" to mapOf("image_match.field.center" to mapOf("x" to 12, "y" to 34))),
            mutableMapOf(),
        )
        assertEquals(mapOf("x" to 12, "y" to 34), evaluator.evaluate(expression, populated))

        val empty = EvaluationScope(mutableMapOf("match" to null), mutableMapOf())
        val failure = assertFailsWith<RuntimeFailure> { evaluator.evaluate(expression, empty) }
        assertEquals("runtime.optional_empty", failure.errorId)
        assertEquals(
            "当前语句需要使用的结果为空，无法继续；如果无结果是正常情况，请先判断“有结果”。",
            failure.message,
        )
    }
}
