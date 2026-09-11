package com.easycode.player.runtime

import com.easycode.player.util.JsonSupport
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import org.junit.Test

class PureOperationsCoreTest {
    private val evaluator = EcirValueEvaluator(RuntimeControl())
    private val scope = EvaluationScope(mutableMapOf(), mutableMapOf())

    @Test
    fun conversionsTextAndGeometryMatchThePortableContract() {
        assertEquals("true", evaluate("core.value_to_text.v1", "string", "value" to true))
        assertEquals("100000000000000000000", evaluate("core.value_to_text.v1", "string", "value" to 1e20))
        assertEquals(
            "2500",
            evaluate(
                "core.value_to_text.v1", "string",
                "value" to mapOf("kind" to "duration", "milliseconds" to 2500),
            ),
        )
        assertEquals(2_500L, evaluate("core.duration_from_seconds.v1", "duration", "amount" to 2.5))
        assertEquals(120_000L, evaluate("core.duration_from_minutes.v1", "duration", "amount" to 2))
        assertEquals(-42L, evaluate("core.text_to_int.v1", "optional<int64>", "text" to "  -42  "))
        assertNull(evaluate("core.text_to_float.v1", "optional<float64>", "text" to "12px"))
        assertNull(evaluate("core.text_to_float.v1", "optional<float64>", "text" to "1_000"))
        assertNull(evaluate("core.text_to_int.v1", "optional<int64>", "text" to "１２"))
        assertEquals(
            listOf("a", "", "b", ""),
            evaluate("core.text_split.v1", "list<string>", "text" to "a||b|", "separator" to "|"),
        )
        assertEquals(
            "a||b|",
            evaluate("core.text_join.v1", "string", "list" to listOf("a", "", "b", ""), "separator" to "|"),
        )

        @Suppress("UNCHECKED_CAST")
        val point = evaluate(
            "core.point_scale.v1",
            "point",
            "point" to mapOf(
                "kind" to "point", "x" to 10, "y" to 5,
                "target_id" to "target.fixture", "space_version" to "v1",
            ),
            "scale_x" to 1.5,
            "scale_y" to 2,
        ) as Map<String, Any?>
        assertEquals(15.0, (point["x"] as Number).toDouble())
        assertEquals(10, (point["y"] as Number).toInt())
        assertEquals("target.fixture", point["target_id"])
        assertEquals("v1", point["space_version"])

        @Suppress("UNCHECKED_CAST")
        val rect = evaluate(
            "core.rect_scale.v1",
            "rect",
            "rect" to mapOf(
                "kind" to "rect", "x" to 2, "y" to 3, "width" to 20, "height" to 10,
                "target_id" to "target.fixture", "space_version" to "v1",
            ),
            "scale_x" to 2,
            "scale_y" to 0.5,
        ) as Map<String, Any?>
        assertEquals(4, (rect["x"] as Number).toInt())
        assertEquals(1.5, (rect["y"] as Number).toDouble())
        assertEquals(40, (rect["width"] as Number).toInt())
        assertEquals(5.0, (rect["height"] as Number).toDouble())
        assertEquals("target.fixture", rect["target_id"])
    }

    @Test
    fun splitRejectsAnEmptySeparatorAndJoinRequiresStrings() {
        assertEquals(
            "text.separator_empty",
            failure("core.text_split.v1", "list<string>", "text" to "abc", "separator" to "").errorId,
        )
        assertEquals(
            "runtime.argument_type",
            failure("core.text_join.v1", "string", "list" to listOf("a", 2), "separator" to ",").errorId,
        )
    }

    @Test
    fun colorComparisonUsesRgbaAndBoundedTolerance() {
        fun color(red: Int, green: Int, blue: Int, alpha: Int = 255) = mapOf(
            "color.field.red" to red,
            "color.field.green" to green,
            "color.field.blue" to blue,
            "color.field.alpha" to alpha,
        )
        assertEquals(
            true,
            evaluate(
                "core.color_matches.v1", "bool",
                "actual" to color(10, 20, 30),
                "expected" to color(12, 18, 31),
                "tolerance" to 2,
            ),
        )
        assertEquals(
            "runtime.color_tolerance_invalid",
            failure(
                "core.color_matches.v1", "bool",
                "actual" to color(10, 20, 30),
                "expected" to color(10, 20, 30),
                "tolerance" to 256,
            ).errorId,
        )
    }

    @Test
    fun textExtractionAndTemporalOperationsMatchPythonRuntime() {
        assertEquals(-86L, evaluate("core.text_extract_first_int.v1", "optional<int64>", "text" to "体力 -86 / 120"))
        assertEquals(
            "215",
            evaluate(
                "core.text_regex_extract.v1", "optional<string>",
                "text" to "房间码 215", "pattern" to "房间码\\s+([0-9]+)", "group" to 1,
            ),
        )
        assertEquals(
            listOf("2026", "09", "04"),
            evaluate(
                "core.text_regex_groups.v1", "list<string>",
                "text" to "2026-09-04", "pattern" to "([0-9]{4})-([0-9]{2})-([0-9]{2})",
            ),
        )
        assertEquals(
            "2026-09-04T08:30:15",
            evaluate(
                "core.text_parse_datetime.v1", "optional<datetime>",
                "text" to "2026-09-04 08:30:15", "pattern" to "yyyy-MM-dd HH:mm:ss",
            ),
        )
        assertEquals(
            "2026-09-04T08:31:30+08:00",
            evaluate(
                "core.datetime_add_duration.v1", "datetime",
                "datetime" to mapOf("kind" to "datetime", "value" to "2026-09-04T08:30:00+08:00"),
                "duration" to mapOf("kind" to "duration", "milliseconds" to 90_000),
            ),
        )
        assertEquals(
            90_000L,
            evaluate(
                "core.datetime_difference.v1", "duration",
                "later" to mapOf("kind" to "datetime", "value" to "2026-09-04T08:31:30+08:00"),
                "earlier" to mapOf("kind" to "datetime", "value" to "2026-09-04T08:30:00+08:00"),
            ),
        )
        assertEquals(
            "2026/09/04 08:30:15.123 +08:00",
            evaluate(
                "core.datetime_format.v1", "string",
                "datetime" to mapOf("kind" to "datetime", "value" to "2026-09-04T08:30:15.123+08:00"),
                "pattern" to "yyyy/MM/dd HH:mm:ss.SSS XXX",
            ),
        )
        assertEquals("2026-08-30", evaluate("core.date_add_days.v1", "date", "date" to mapOf("kind" to "date", "value" to "2026-09-04"), "days" to -5))
        assertEquals("00:01", evaluate("core.time_add_duration.v1", "time", "time" to mapOf("kind" to "time", "value" to "23:59:30"), "duration" to mapOf("kind" to "duration", "milliseconds" to 90_000)))
        assertEquals("text.regex_invalid", failure("core.text_regex_extract.v1", "optional<string>", "text" to "x", "pattern" to "[", "group" to 0).errorId)
    }

    private fun evaluate(operationId: String, resultType: String, vararg inputs: Pair<String, Any?>): Any? =
        evaluator.evaluate(operation(operationId, resultType, inputs.toMap()), scope)

    private fun failure(operationId: String, resultType: String, vararg inputs: Pair<String, Any?>): RuntimeFailure =
        assertFailsWith { evaluate(operationId, resultType, *inputs) }

    private fun operation(operationId: String, resultType: String, inputs: Map<String, Any?>) = JsonSupport.fromAny(
        mapOf(
            "kind" to "operation",
            "operation_id" to operationId,
            "result_type" to resultType,
            "inputs" to inputs.mapKeys { (name, _) -> "$operationId.input.$name" },
        ),
    )
}
