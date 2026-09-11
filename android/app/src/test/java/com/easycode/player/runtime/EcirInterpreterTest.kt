package com.easycode.player.runtime

import android.content.ContextWrapper
import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.profile.PlayerProfile
import com.easycode.player.profile.ProfileStore
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.io.File
import java.nio.file.Files
import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class EcirInterpreterTest {
    @Test
    fun projectVariablesLocalsCallsAndControlFlowShareOneRuntimeState() {
        val root = Files.createTempDirectory("easycode-android-ecir-test").toFile()
        try {
            val context = object : ContextWrapper(null) {
                override fun getFilesDir(): File = root
                override fun getApplicationContext() = this
            }
            val ecir = json(
                """
                {
                  "project_variables": [
                    {
                      "variable_id": "project.counter",
                      "default_value": 1
                    }
                  ],
                  "project_variable_overrides": {
                    "project.counter": 3
                  },
                  "function_arguments": {
                    "function.entry": {
                      "parameter.delta": 2
                    }
                  },
                  "functions": [
                    {
                      "function_id": "function.entry",
                      "return_type": "int64",
                      "parameter_definitions": [
                        {
                          "parameter_id": "parameter.delta",
                          "name": "local.delta",
                          "display_name": "增量",
                          "value_type": "int64",
                          "required": true
                        }
                      ],
                      "instructions": [
                        {
                          "instruction_id": "statement.repeat",
                          "opcode": "control.repeat",
                          "arguments": {
                            "source": 2,
                            "body": [
                              {
                                "instruction_id": "statement.call-helper",
                                "opcode": "call.project",
                                "callee_function_id": "function.helper",
                                "arguments": {
                                  "parameter.helper.delta": {
                                    "kind": "reference",
                                    "scope": "local",
                                    "symbol_id": "local.delta"
                                  }
                                }
                              }
                            ]
                          }
                        },
                        {
                          "instruction_id": "statement.if",
                          "opcode": "control.if",
                          "arguments": {
                            "condition": {
                              "kind": "compare",
                              "operator": "equal",
                              "left": {
                                "kind": "reference",
                                "scope": "project",
                                "variable_id": "project.counter"
                              },
                              "right": 7
                            },
                            "additional_branches": [],
                            "then": [
                              {
                                "instruction_id": "statement.log",
                                "opcode": "log.write",
                                "arguments": {
                                  "official.log.output.parameter.level": "info",
                                  "official.log.output.parameter.category": "test",
                                  "official.log.output.parameter.content": {
                                    "kind": "reference",
                                    "scope": "project",
                                    "variable_id": "project.counter"
                                  }
                                }
                              },
                              {
                                "instruction_id": "statement.return-success",
                                "opcode": "control.return",
                                "arguments": {
                                  "value": {
                                    "kind": "reference",
                                    "scope": "project",
                                    "variable_id": "project.counter"
                                  }
                                }
                              }
                            ],
                            "otherwise": [
                              {
                                "instruction_id": "statement.return-failure",
                                "opcode": "control.return",
                                "arguments": {"value": 0}
                              }
                            ]
                          }
                        }
                      ]
                    },
                    {
                      "function_id": "function.helper",
                      "return_type": "unit",
                      "parameter_definitions": [
                        {
                          "parameter_id": "parameter.helper.delta",
                          "name": "local.helper.delta",
                          "display_name": "增量",
                          "value_type": "int64",
                          "required": true
                        }
                      ],
                      "instructions": [
                        {
                          "instruction_id": "statement.increment-project",
                          "opcode": "data.assign_project",
                          "arguments": {
                            "target": {"variable_id": "project.counter"},
                            "value": {
                              "kind": "operation",
                              "operation_id": "core.number_add.v1",
                              "inputs": {
                                "core.number_add.v1.input.left": {
                                  "kind": "reference",
                                  "scope": "project",
                                  "variable_id": "project.counter"
                                },
                                "core.number_add.v1.input.right": {
                                  "kind": "reference",
                                  "scope": "local",
                                  "symbol_id": "local.helper.delta"
                                }
                              }
                            }
                          }
                        }
                      ]
                    }
                  ]
                }
                """.trimIndent(),
            )
            val bundle = VerifiedBundle(
                file = File(root, "fixture.ecplayer"),
                manifest = json("""{"project_id":"product.test","release_id":"release.test","name":"Test"}"""),
                ecir = ecir,
                project = json("""{"targets":[],"default_target_id":"target.local"}"""),
                form = json("""{"schema_version":3,"pages":[]}"""),
                publishReport = JsonObject(),
                lock = json("""{"extensions":[]}"""),
                trustRoot = JsonObject(),
                keyId = "test-key",
                integritySha256 = "0".repeat(64),
            )
            val profile = PlayerProfile(
                profileId = "profile_fixture",
                name = "测试",
                targetId = "target.local",
                values = JsonObject(),
                revision = 1,
                createdAt = "2026-09-01T00:00:00Z",
                updatedAt = "2026-09-01T00:00:00Z",
            )
            val checkpoints = mutableListOf<String>()
            val messages = mutableListOf<String>()
            EcirInterpreter(
                context = context,
                bundle = bundle,
                profile = profile,
                bound = BoundRun(ecir, "function.entry", "target.local"),
                runId = "run_fixture",
                profileStore = ProfileStore(context),
                control = RuntimeControl(),
                dangerousConfirmations = emptySet(),
                onCheckpoint = { _, instruction -> checkpoints += instruction },
                onEvent = { _, _, message, _, _ -> messages += message },
            ).use { interpreter ->
                assertEquals(7L, interpreter.run())
            }

            assertEquals(2, checkpoints.count { it == "statement.call-helper" })
            assertEquals(2, checkpoints.count { it == "statement.increment-project" })
            assertTrue("7" in messages)
        } finally {
            root.deleteRecursively()
        }
    }

    @Test
    fun explicitFailureKeepsStableIdentityAndStructuredDetails() {
        val root = Files.createTempDirectory("easycode-android-fail-test").toFile()
        try {
            val context = object : ContextWrapper(null) {
                override fun getFilesDir(): File = root
                override fun getApplicationContext() = this
            }
            val ecir = json(
                """
                {
                  "project_variables": [],
                  "functions": [{
                    "function_id": "function.entry",
                    "return_type": "unit",
                    "parameter_definitions": [],
                    "instructions": [{
                      "instruction_id": "statement.fail",
                      "opcode": "control.fail",
                      "arguments": {
                        "error_id": "project.login_failed",
                        "message": "登录条件不满足",
                        "details": {"kind":"json","value":{"attempt":2}}
                      }
                    }]
                  }]
                }
                """.trimIndent(),
            )
            val bundle = VerifiedBundle(
                file = File(root, "fixture.ecplayer"),
                manifest = json("""{"project_id":"product.test","release_id":"release.test","name":"Test"}"""),
                ecir = ecir,
                project = json("""{"targets":[],"default_target_id":"target.local"}"""),
                form = json("""{"schema_version":3,"pages":[]}"""),
                publishReport = JsonObject(),
                lock = json("""{"extensions":[]}"""),
                trustRoot = JsonObject(),
                keyId = "test-key",
                integritySha256 = "0".repeat(64),
            )
            val profile = PlayerProfile(
                profileId = "profile_fixture",
                name = "测试",
                targetId = "target.local",
                values = JsonObject(),
                revision = 1,
                createdAt = "2026-09-01T00:00:00Z",
                updatedAt = "2026-09-01T00:00:00Z",
            )
            val error = assertFailsWith<RuntimeFailure> {
                EcirInterpreter(
                    context = context,
                    bundle = bundle,
                    profile = profile,
                    bound = BoundRun(ecir, "function.entry", "target.local"),
                    runId = "run_fixture",
                    profileStore = ProfileStore(context),
                    control = RuntimeControl(),
                    dangerousConfirmations = emptySet(),
                    onCheckpoint = { _, _ -> },
                    onEvent = { _, _, _, _, _ -> },
                ).use(EcirInterpreter::run)
            }
            assertEquals("project.login_failed", error.errorId)
            assertEquals("登录条件不满足", error.message)
            assertEquals(2, ((error.details as Map<*, *>)["attempt"] as Number).toInt())
        } finally {
            root.deleteRecursively()
        }
    }

    private fun json(value: String): JsonObject = JsonParser.parseString(value).asJsonObject
}
