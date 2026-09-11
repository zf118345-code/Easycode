package com.easycode.player.runtime

import com.easycode.player.util.JsonSupport
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import org.junit.Test

class PureOperationsFileReferenceTest {
    private val evaluator = EcirValueEvaluator(RuntimeControl())
    private val scope = EvaluationScope(mutableMapOf(), mutableMapOf())

    @Test
    fun androidChildReferenceNarrowsCapabilityWithoutResolvingProvider() {
        val directory = mapOf(
            "kind" to "directory_ref",
            "platform" to "android",
            "source" to "saf_tree",
            "display_name" to "Documents",
            "uri" to "content://fixture/tree/root",
            "authorization_root_id" to "root-a",
            "access" to listOf("read", "list", "create", "write"),
            "relative_segments" to listOf("already"),
        )

        val result = evaluate("file_ref<write>", directory, "reports/result.json")

        assertEquals("file_ref", result["kind"])
        assertEquals("derived_relative", result["source"])
        assertEquals(listOf("write"), result["access"])
        assertEquals("content://fixture/tree/root", result["uri"])
        assertEquals(listOf("already", "reports", "result.json"), result["relative_segments"])
        assertEquals("result.json", result["display_name"])
        assertFalse("private_path" in result)
    }

    @Test
    fun readAndWriteDerivationRequireMatchingRuntimeAuthority() {
        val readOnly = privateDirectory(setOf("read", "list"))
        val createOnly = privateDirectory(setOf("create"))

        assertEquals(listOf("read"), evaluate("file_ref<read>", readOnly, "one.txt")["access"])
        assertEquals(listOf("write"), evaluate("file_ref<write>", createOnly, "two.txt")["access"])
        assertEquals(
            "file.access_denied",
            failure("file_ref<write>", readOnly, "blocked.txt").errorId,
        )
        assertEquals(
            "file.access_denied",
            failure("file_ref<read>", createOnly, "blocked.txt").errorId,
        )
    }

    @Test
    fun portableRelativePathRejectsTraversalEmptySegmentsAndWindowsNames() {
        val directory = privateDirectory(setOf("read", "write"))
        val rejected = listOf(
            "", "/rooted", "\\rooted", "one\\two", ".", "..", "one/../two",
            "one//two", "one/./two", "CON", "con.txt", "LPT9.log", "bad:name",
            "bad*name", "trailing.", "trailing ", "control\u0001name",
        )

        rejected.forEach { relative ->
            assertEquals(
                "file.relative_path_invalid",
                failure("file_ref<read>", directory, relative).errorId,
                relative,
            )
        }
    }

    @Test
    fun operationUsesOnlyStableDirectoryAndRelativePathSlots() {
        val value = operation(
            "file_ref<read>",
            mapOf(
                "core.file_ref_child.v1.input.reference" to privateDirectory(setOf("read")),
                "core.file_ref_child.v1.input.relative_path" to "one.txt",
            ),
        )

        val failure = assertFailsWith<RuntimeFailure> { evaluator.evaluate(value, scope) }
        assertEquals("runtime.operation_input", failure.errorId)
    }

    @Suppress("UNCHECKED_CAST")
    private fun evaluate(
        resultType: String,
        directory: Map<String, Any?>,
        relative: Any?,
    ): Map<String, Any?> = evaluator.evaluate(
        operation(
            resultType,
            mapOf(
                "core.file_ref_child.v1.input.directory" to directory,
                "core.file_ref_child.v1.input.relative_path" to relative,
            ),
        ),
        scope,
    ) as Map<String, Any?>

    private fun failure(
        resultType: String,
        directory: Map<String, Any?>,
        relative: Any?,
    ): RuntimeFailure = assertFailsWith {
        evaluate(resultType, directory, relative)
    }

    private fun operation(resultType: String, inputs: Map<String, Any?>) = JsonSupport.fromAny(
        mapOf(
            "kind" to "operation",
            "operation_id" to "core.file_ref_child.v1",
            "result_type" to resultType,
            "inputs" to inputs,
        ),
    )

    private fun privateDirectory(access: Set<String>): Map<String, Any?> = mapOf(
        "kind" to "directory_ref",
        "platform" to "android",
        "source" to "project_data",
        "display_name" to "data",
        "private_path" to "D:/fixture/data",
        "authorization_root_id" to "root-private",
        "access" to access.sorted(),
    )
}
