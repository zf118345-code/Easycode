package com.easycode.player.file

import android.content.ContextWrapper
import com.easycode.player.runtime.DangerousRunConfirmation
import com.easycode.player.runtime.RuntimeControl
import com.easycode.player.runtime.RuntimeFailure
import java.io.File
import java.nio.file.Files
import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SafFileRuntimeTest {
    @Test
    fun directoryListReturnsTypedCapabilityNarrowedReferences() {
        withRoot { root, target ->
            target.resolve("nested").mkdirs()
            val runtime = SafFileRuntime(ContextWrapper(null), root, RuntimeControl(), 7, emptySet())

            val entries = runtime.execute(
                "directory.list",
                "statement.list",
                mapOf(
                    "official.directory.list.parameter.directory" to reference(
                        target,
                        "root-a",
                        setOf("read", "list", "create", "write", "delete_empty"),
                    ),
                    "official.directory.list.parameter.filter" to mapOf(
                        "filesystem_filter.field.pattern" to "*.txt",
                        "filesystem_filter.field.limit" to 10,
                    ),
                    "official.directory.list.parameter.recursive" to false,
                ),
            ) as List<*>
            val indexed = entries.map { it as Map<*, *> }.associateBy { it["filesystem_entry.field.name"] }
            val file = indexed.getValue("keep.txt")
            val fileReference = file["filesystem_entry.field.file"] as Map<*, *>

            assertEquals("file", file["filesystem_entry.field.entry_type"])
            assertEquals(4L, file["filesystem_entry.field.size"])
            assertEquals("file_ref", fileReference["kind"])
            assertEquals(listOf("read", "write"), fileReference["access"])
            assertEquals(setOf("keep.txt"), indexed.keys)
        }
    }

    @Test
    fun ordinarySafAuthorityCannotBeUpgradedToRecursiveDelete() {
        withRoot { root, target ->
            val runtime = SafFileRuntime(ContextWrapper(null), root, RuntimeControl(), 7, emptySet())
            val failure = assertFailsWith<RuntimeFailure> {
                runtime.execute(
                    "directory.delete_tree",
                    "statement.delete",
                    arguments(reference(target, "root-a", setOf("read", "list"))),
                    "sha256:contract-a",
                )
            }

            assertEquals("directory.delete_tree_not_authorized", failure.errorId)
            assertTrue(target.resolve("keep.txt").isFile)
        }
    }

    @Test
    fun confirmationIsReusableOnlyInsideOneMatchingExecutionScope() {
        withRoot { root, target ->
            val confirmation = DangerousRunConfirmation(
                statementId = "statement.delete",
                authorizationRootId = "root-a",
                profileRevision = 7,
                contractFingerprint = "sha256:contract-a",
            )
            val arguments = arguments(reference(root, "root-a", setOf("read", "list", "delete_tree")))
            val currentRun = SafFileRuntime(
                ContextWrapper(null), root, RuntimeControl(), 7, setOf(confirmation),
            )

            repeat(2) {
                val failure = assertFailsWith<RuntimeFailure> {
                    currentRun.execute(
                        "directory.delete_tree", "statement.delete", arguments,
                        "sha256:contract-a",
                    )
                }
                // The in-memory confirmation passed. The separate protected
                // Player-data-root boundary then rejects before entry 1.
                assertEquals("directory.protected_root", failure.errorId)
            }

            val nextRun = SafFileRuntime(ContextWrapper(null), root, RuntimeControl(), 7, emptySet())
            val crossRunFailure = assertFailsWith<RuntimeFailure> {
                nextRun.execute(
                    "directory.delete_tree", "statement.delete", arguments,
                    "sha256:contract-a",
                )
            }
            assertEquals("directory.confirmation_required", crossRunFailure.errorId)
            assertTrue(target.resolve("keep.txt").isFile)
        }
    }

    @Test
    fun anyConfirmationBindingChangeRejectsBeforeModification() {
        withRoot { root, target ->
            val approval = DangerousRunConfirmation(
                "statement.delete", "root-a", 7, "sha256:contract-a",
            )
            val runtime = SafFileRuntime(ContextWrapper(null), root, RuntimeControl(), 8, setOf(approval))
            val failure = assertFailsWith<RuntimeFailure> {
                runtime.execute(
                    "directory.delete_tree",
                    "statement.delete",
                    arguments(reference(root, "root-a", setOf("read", "delete_tree"))),
                    "sha256:contract-a",
                )
            }
            assertEquals("directory.confirmation_required", failure.errorId)
            assertTrue(target.resolve("keep.txt").isFile)
        }
    }

    @Test
    fun confirmedPrivateChildTreeDeletesOnlyAfterCompletePreflight() {
        withRoot { root, target ->
            target.resolve("nested").mkdirs()
            target.resolve("nested/second.txt").writeText("second")
            val confirmation = DangerousRunConfirmation(
                "statement.delete", "root-a", 7, "sha256:contract-a",
            )
            val runtime = SafFileRuntime(
                ContextWrapper(null), root, RuntimeControl(), 7, setOf(confirmation),
            )

            val result = runtime.execute(
                "directory.delete_tree",
                "statement.delete",
                arguments(reference(target, "root-a", setOf("read", "delete_tree"))),
                "sha256:contract-a",
            ) as Map<*, *>

            assertEquals(true, result["tree_delete_report.field.complete"])
            assertEquals(2, result["tree_delete_report.field.files_deleted"])
            assertEquals(2, result["tree_delete_report.field.directories_deleted"])
            assertTrue(!target.exists())
            assertTrue(root.exists())
        }
    }

    @Test
    fun privateDirectoryMovePreflightsThenMovesWithinProtectedDataRoot() {
        withRoot { root, target ->
            target.resolve("nested").mkdirs()
            target.resolve("nested/second.txt").writeText("second")
            val runtime = SafFileRuntime(ContextWrapper(null), root, RuntimeControl(), 7, emptySet())

            val result = runtime.execute(
                "directory.move",
                "statement.move",
                mapOf(
                    "official.directory.move.parameter.source" to reference(
                        target, "root-source", setOf("read", "move"),
                    ),
                    "official.directory.move.parameter.destination_parent" to reference(
                        root, "root-destination", setOf("create"),
                    ),
                    "official.directory.move.parameter.name" to "moved",
                    "official.directory.move.parameter.conflict" to "error",
                ),
            ) as Map<*, *>

            assertEquals(true, result["tree_operation_report.field.complete"])
            assertEquals(2, result["tree_operation_report.field.processed_files"])
            assertEquals(2, result["tree_operation_report.field.processed_directories"])
            assertEquals("directory_ref", (result["tree_operation_report.field.destination"] as Map<*, *>)["kind"])
            assertTrue(!target.exists())
            assertTrue(root.resolve("moved/keep.txt").isFile)
            assertTrue(root.resolve("moved/nested/second.txt").isFile)
        }
    }

    @Test
    fun privateDeferredFileResolvesAtIoAndCanCreateWriteTarget() {
        withRoot { root, target ->
            target.resolve("nested").mkdirs()
            target.resolve("nested/read.txt").writeText("resolved")
            val runtime = SafFileRuntime(ContextWrapper(null), root, RuntimeControl(), 7, emptySet())

            val read = runtime.execute(
                "file.read_text",
                "statement.read",
                fileArguments(
                    "file",
                    deferredPrivateFile(target, listOf("nested", "read.txt"), setOf("read")),
                ),
            )
            runtime.execute(
                "file.write_text",
                "statement.write",
                fileArguments(
                    "file",
                    deferredPrivateFile(target, listOf("nested", "created.txt"), setOf("write")),
                    "content" to "created",
                ),
            )

            assertEquals("resolved", read)
            assertEquals("created", target.resolve("nested/created.txt").readText())
        }
    }

    @Test
    fun privateDeferredFileRejectsTraversalMissingAndDirectoryConflict() {
        withRoot { root, target ->
            target.resolve("folder").mkdirs()
            val runtime = SafFileRuntime(ContextWrapper(null), root, RuntimeControl(), 7, emptySet())

            assertEquals(
                "file.relative_path_invalid",
                assertFailsWith<RuntimeFailure> {
                    runtime.execute(
                        "file.read_text",
                        "statement.traversal",
                        fileArguments(
                            "file",
                            deferredPrivateFile(target, listOf("..", "escape.txt"), setOf("read")),
                        ),
                    )
                }.errorId,
            )
            assertEquals(
                "file.not_found",
                assertFailsWith<RuntimeFailure> {
                    runtime.execute(
                        "file.read_text",
                        "statement.missing",
                        fileArguments(
                            "file",
                            deferredPrivateFile(target, listOf("missing.txt"), setOf("read")),
                        ),
                    )
                }.errorId,
            )
            assertEquals(
                "file.type_conflict",
                assertFailsWith<RuntimeFailure> {
                    runtime.execute(
                        "file.read_text",
                        "statement.conflict",
                        fileArguments(
                            "file",
                            deferredPrivateFile(target, listOf("folder"), setOf("read")),
                        ),
                    )
                }.errorId,
            )
            assertTrue(root.resolve("target/keep.txt").isFile)
            assertFalse(root.resolve("escape.txt").exists())
        }
    }

    @Test
    fun safDeferredPathWalksOneDirectoryAtATime() {
        val calls = mutableListOf<String>()
        val result = resolveDeferredSafPath(
            rootDocumentUri = "content://fixture/tree/root/document/root",
            relativeSegments = listOf("reports", "result.json"),
            expectedKind = "file_ref",
            allowMissing = false,
        ) { current ->
            calls += current
            when (current) {
                "content://fixture/tree/root/document/root" -> listOf(
                    DeferredSafChild("reports", true, "content://fixture/tree/root/document/reports"),
                )
                "content://fixture/tree/root/document/reports" -> listOf(
                    DeferredSafChild("result.json", false, "content://fixture/tree/root/document/result"),
                )
                else -> emptyList()
            }
        }

        assertEquals("content://fixture/tree/root/document/result", result.documentUri)
        assertEquals(
            listOf(
                "content://fixture/tree/root/document/root",
                "content://fixture/tree/root/document/reports",
            ),
            calls,
        )
    }

    @Test
    fun safDeferredPathRejectsMissingAndFolderConflictsBeforeIo() {
        val rootUri = "content://fixture/tree/root/document/root"
        val missing = assertFailsWith<RuntimeFailure> {
            resolveDeferredSafPath(rootUri, listOf("missing.txt"), "file_ref", false) { emptyList() }
        }
        val intermediateFile = assertFailsWith<RuntimeFailure> {
            resolveDeferredSafPath(rootUri, listOf("file", "child.txt"), "file_ref", false) {
                listOf(DeferredSafChild("file", false, "$rootUri/file"))
            }
        }
        val folderAtFile = assertFailsWith<RuntimeFailure> {
            resolveDeferredSafPath(rootUri, listOf("folder"), "file_ref", false) {
                listOf(DeferredSafChild("folder", true, "$rootUri/folder"))
            }
        }
        val pending = resolveDeferredSafPath(rootUri, listOf("new.txt"), "file_ref", true) { emptyList() }

        assertEquals("file.not_found", missing.errorId)
        assertEquals("directory.path_conflict", intermediateFile.errorId)
        assertEquals("file.type_conflict", folderAtFile.errorId)
        assertEquals(rootUri, pending.pendingParentUri)
        assertEquals("new.txt", pending.pendingName)
        assertEquals(null, pending.documentUri)
    }

    private fun withRoot(block: (File, File) -> Unit) {
        val root = Files.createTempDirectory("easycode-android-file-test").toFile()
        try {
            val target = root.resolve("target").apply { mkdirs() }
            target.resolve("keep.txt").writeText("keep")
            block(root, target)
        } finally {
            root.deleteRecursively()
        }
    }

    private fun arguments(reference: Map<String, Any?>): Map<String, Any?> = mapOf(
        "official.directory.delete_tree.parameter.directory" to reference,
    )

    private fun fileArguments(
        referenceSlot: String,
        reference: Map<String, Any?>,
        vararg extras: Pair<String, Any?>,
    ): Map<String, Any?> = buildMap {
        put("official.file.test.parameter.$referenceSlot", reference)
        extras.forEach { (name, value) -> put("official.file.test.parameter.$name", value) }
    }

    private fun deferredPrivateFile(
        root: File,
        relativeSegments: List<String>,
        access: Set<String>,
    ): Map<String, Any?> = mapOf(
        "kind" to "file_ref",
        "platform" to "android",
        "source" to "derived_relative",
        "display_name" to relativeSegments.lastOrNull().orEmpty(),
        "private_path" to root.canonicalPath,
        "relative_segments" to relativeSegments,
        "authorization_root_id" to "root-private",
        "access" to access.sorted(),
    )

    private fun reference(
        target: File,
        rootId: String,
        access: Set<String>,
    ): Map<String, Any?> = mapOf(
        "kind" to "directory_ref",
        "platform" to "android",
        "source" to "test",
        "display_name" to target.name,
        "private_path" to target.canonicalPath,
        "authorization_root_id" to rootId,
        "access" to access.sorted(),
    )

}
