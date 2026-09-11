package com.easycode.player.bundle

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import org.junit.Test
import kotlin.test.assertFailsWith

class AndroidPackagePreflightTest {
    @Test
    fun `accepts the complete Android message and listener opcode slice`() {
        val instructions = JsonArray().apply {
            listOf(
                "message.send",
                "message.wait_receive",
                "message.wait_read",
                "message.cancel",
                "control.listen",
            ).forEachIndexed { index, opcode ->
                add(JsonObject().apply {
                    addProperty("instruction_id", "message_$index")
                    addProperty("opcode", opcode)
                    add("arguments", JsonObject())
                })
            }
        }
        val ecir = JsonObject().apply {
            addProperty("ecir_version", 1)
            addProperty("program_model_version", 1)
            addProperty("minimum_android_api", 21)
            add("android_api_requirements", JsonArray())
            addProperty("entry_function_id", "main")
            add("functions", JsonArray().apply { add(JsonObject().apply {
                addProperty("function_id", "main")
                add("instructions", instructions)
            }) })
        }
        val project = JsonObject().apply {
            addProperty("targets_schema_version", 1)
            addProperty("default_target_id", "android")
            add("targets", JsonArray().apply { add(JsonObject().apply {
                addProperty("target_id", "android")
                addProperty("type", "android_local")
            }) })
        }
        val form = JsonObject().apply {
            addProperty("schema_version", 3)
            add("pages", JsonArray())
        }
        val report = JsonObject().apply {
            addProperty("minimum_android_api", 21)
            add("android_api_requirements", JsonArray())
            add("player_terminal_actions", JsonArray())
            add("player_terminal_capabilities", JsonArray())
        }

        AndroidPackagePreflight.validate(ecir, project, form, report, deviceApi = 21)
    }

    @Test
    fun `accepts application launch and clipboard but rejects unobservable app exit`() {
        val instructions = JsonArray().apply {
            listOf(
                "host.app.start",
                "clipboard.read_text",
                "clipboard.write_text",
            ).forEachIndexed { index, opcode ->
                add(JsonObject().apply {
                    addProperty("instruction_id", "platform_$index")
                    addProperty("opcode", opcode)
                    add("arguments", JsonObject())
                })
            }
        }
        val ecir = JsonObject().apply {
            addProperty("ecir_version", 1)
            addProperty("program_model_version", 1)
            addProperty("minimum_android_api", 21)
            add("android_api_requirements", JsonArray())
            addProperty("entry_function_id", "main")
            add("functions", JsonArray().apply { add(JsonObject().apply {
                addProperty("function_id", "main")
                add("instructions", instructions)
            }) })
        }
        val project = JsonObject().apply {
            addProperty("targets_schema_version", 1)
            addProperty("default_target_id", "android")
            add("targets", JsonArray().apply { add(JsonObject().apply {
                addProperty("target_id", "android")
                addProperty("type", "android_local")
            }) })
        }
        val form = JsonObject().apply {
            addProperty("schema_version", 3)
            add("pages", JsonArray())
        }
        val report = JsonObject().apply {
            addProperty("minimum_android_api", 21)
            add("android_api_requirements", JsonArray())
            add("player_terminal_actions", JsonArray())
            add("player_terminal_capabilities", JsonArray())
        }

        AndroidPackagePreflight.validate(ecir, project, form, report, deviceApi = 21)
        instructions.add(JsonObject().apply {
            addProperty("instruction_id", "platform_wait_exit")
            addProperty("opcode", "host.app.wait_exit")
            add("arguments", JsonObject())
        })
        assertFailsWith<BundleVerificationException> {
            AndroidPackagePreflight.validate(ecir, project, form, report, deviceApi = 21)
        }
    }

    @Test
    fun `requires Android extension API floor to match signed requirement closure`() {
        val requirement = JsonObject().apply {
            addProperty("kind", "extension")
            addProperty("package_id", "vendor.android")
            addProperty("display_name", "Android 扩展")
            addProperty("minimum_android_api", 28)
            add("statement_ids", JsonArray())
        }
        val ecir = JsonObject().apply {
            addProperty("ecir_version", 1)
            addProperty("program_model_version", 1)
            addProperty("minimum_android_api", 28)
            add("android_api_requirements", JsonArray().apply { add(requirement) })
            addProperty("entry_function_id", "main")
            add("functions", JsonArray().apply { add(JsonObject().apply {
                addProperty("function_id", "main")
                add("instructions", JsonArray())
            }) })
        }
        val project = JsonObject().apply {
            addProperty("targets_schema_version", 1)
            addProperty("default_target_id", "android")
            add("targets", JsonArray().apply { add(JsonObject().apply {
                addProperty("target_id", "android")
                addProperty("type", "android_local")
            }) })
        }
        val form = JsonObject().apply {
            addProperty("schema_version", 3)
            add("pages", JsonArray())
        }
        val report = JsonObject().apply {
            addProperty("minimum_android_api", 28)
            add("android_api_requirements", JsonArray().apply { add(requirement.deepCopy()) })
            add("player_terminal_actions", JsonArray())
            add("player_terminal_capabilities", JsonArray())
        }
        val lock = JsonObject().apply {
            add("extensions", JsonArray().apply { add(JsonObject().apply {
                addProperty("package_id", "vendor.android")
                add("selected_variants", JsonArray().apply { add(JsonObject().apply {
                    addProperty("host", "android_native")
                    addProperty("minimum_android_api", 28)
                }) })
            }) })
        }

        AndroidPackagePreflight.validate(ecir, project, form, report, lock, deviceApi = 28)

        val staleLock = lock.deepCopy().apply {
            getAsJsonArray("extensions")[0].asJsonObject
                .getAsJsonArray("selected_variants")[0].asJsonObject
                .addProperty("minimum_android_api", 29)
        }
        val error = runCatching {
            AndroidPackagePreflight.validate(ecir, project, form, report, staleLock, deviceApi = 29)
        }.exceptionOrNull()
        check(error is BundleVerificationException && error.code == "AND-API-001")
    }
}
