package com.easycode.player.bundle

import android.os.Build
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.int
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonObject

object AndroidPackagePreflight {
    private val valueControlTypes = setOf(
        "text", "number", "slider-number", "toggle", "select", "duration", "time",
        "color", "coordinate", "region", "resource", "control-selector", "gesture-path", "list",
        "key-value", "expression", "file", "directory",
    )
    private val terminalCapabilities = mapOf(
        "pick-point" to "player.capture.point",
        "pick-region" to "player.capture.region",
        "pick-color" to "player.capture.color",
        "capture-image" to "player.capture.image",
        "choose-resource" to "player.image.choose",
        "capture-control" to "player.capture.control",
        "capture-path" to "player.capture.path",
        "choose-file-read" to "player.file.choose_read",
        "choose-file-save" to "player.file.choose_write",
        "choose-directory" to "player.directory.choose",
    )
    private val androidActions = setOf(
        "pick-point", "pick-region", "pick-color", "capture-image", "choose-resource", "capture-control", "capture-path",
        "choose-file-read", "choose-file-save", "choose-directory",
    )
    private val supportedOpcodes = setOf(
        "log.write", "wait.duration", "wait.until", "random.integer", "time.now", "time.today",
        "project.data_directory", "data.assign", "data.assign_local", "data.assign_project",
        "call.project", "call.extension", "control.if", "control.repeat", "control.while", "control.for_each",
        "control.for_each_map", "control.break", "control.continue", "control.fail", "control.try",
        "control.return", "control.target_scope", "control.listen",
        "target.wait_online", "target.status", "target.capture_frame", "frame.save", "host.app.start",
        "clipboard.read_text", "clipboard.write_text",
        "color.read", "color.find", "vision.find", "vision.find_all", "text.recognize", "standard.image.wait_visible",
        "standard.image.wait_hidden", "standard.image.click_once", "standard.image.click_until_hidden",
        "standard.image.click_position_until_visible", "standard.image.click_position_until_hidden",
        "standard.text.match", "standard.text.wait_visible",
        "standard.control.wait_visible", "standard.control.wait_hidden",
        "input.click", "input.text", "input.scroll", "input.drag", "input.key",
        "control.find", "control.click", "control.click_selector", "control.read_text", "control.input_text",
        "control.read_status", "control.focus", "control.set_value", "control.select",
        "control.toggle", "control.scroll_into_view",
        "file.exists", "file.read_text", "file.write_text", "file.append_text",
        "file.replace_text", "file.read_json", "file.write_json", "file.delete", "file.copy",
        "file.move", "directory.exists", "directory.create", "directory.list", "directory.copy",
        "directory.move", "directory.delete", "directory.delete_tree",
        "message.send", "message.wait_receive", "message.wait_read", "message.cancel",
        "network.request", "network.upload_file", "network.download_file",
    )

    fun validate(
        ecir: JsonObject,
        project: JsonObject,
        form: JsonObject,
        report: JsonObject,
        lock: JsonObject = JsonObject(),
        deviceApi: Int = Build.VERSION.SDK_INT,
    ) {
        if (ecir.int("ecir_version") != 1 || ecir.int("program_model_version") != 1) {
            fail("AND-ECIR-001", "Android Runtime 只接受 ECIR v1 / Program Model v1")
        }
        val minimumAndroidApi = ecir.int("minimum_android_api")
        if (minimumAndroidApi !in 21..37 || report.int("minimum_android_api") != minimumAndroidApi) {
            fail("AND-API-001", "项目与发布报告没有声明一致且有效的 Android 最低版本")
        }
        val requirements = ecir.array("android_api_requirements")
        if (report.array("android_api_requirements") != requirements) {
            fail("AND-API-001", "Android 最低版本依据与发布报告不一致")
        }
        val highestRequirement = requirements.fold(21) { current, item ->
            if (!item.isJsonObject) fail("AND-API-001", "Android 最低版本依据格式无效")
            val floor = item.asJsonObject.int("minimum_android_api")
            if (floor !in 22..37) fail("AND-API-001", "Android 最低版本依据包含无效能力要求")
            maxOf(current, floor)
        }
        if (highestRequirement != minimumAndroidApi) {
            fail("AND-API-001", "Android 最低版本没有与项目所用能力的最高要求一致")
        }
        validateExtensionApiRequirements(lock, requirements)
        if (deviceApi < minimumAndroidApi) {
            fail(
                "AND-API-002",
                "此项目要求 Android API $minimumAndroidApi，当前设备为 API $deviceApi",
            )
        }
        val targetPlatform = ecir.get("target_platform")
            ?.takeUnless { it.isJsonNull }
            ?.asString
            .orEmpty()
        if (targetPlatform !in setOf("", "android_local", "no_target")) {
            fail("AND-TARGET-001", "APK 不能执行非本机目标平台：$targetPlatform")
        }
        val targets = project.array("targets").mapNotNull { item ->
            item.takeIf { it.isJsonObject }?.asJsonObject
        }
        val targetTypes = targets.associate { it.string("target_id") to it.string("type") }
        val invalidTarget = targetTypes.entries.firstOrNull { it.key.isBlank() || it.value != "android_local" }
        if (invalidTarget != null) {
            fail("AND-TARGET-002", "Android 本机实例不能切换到目标 ${invalidTarget.key}:${invalidTarget.value}")
        }
        val defaultTarget = project.get("default_target_id")?.takeUnless { it.isJsonNull }?.asString.orEmpty()
        if (defaultTarget.isNotBlank() && defaultTarget !in targetTypes) {
            fail("AND-TARGET-003", "Android 默认目标不在签名目标闭包中：$defaultTarget")
        }
        if (project.int("targets_schema_version") != 1) {
            fail("AND-TARGET-004", "Android 目标配置版本不受支持")
        }

        val functions = ecir.array("functions")
        if (functions.size() == 0 || ecir.string("entry_function_id").isBlank()) {
            fail("AND-ECIR-002", "ECIR 缺少入口函数或函数闭包")
        }
        val functionIds = mutableSetOf<String>()
        val unsupported = mutableListOf<String>()
        for (functionValue in functions) {
            if (!functionValue.isJsonObject) fail("AND-ECIR-002", "ECIR 函数记录格式无效")
            val function = functionValue.asJsonObject
            val functionId = function.string("function_id")
            if (functionId.isBlank() || !functionIds.add(functionId)) {
                fail("AND-ECIR-002", "ECIR 函数稳定 ID 缺失或重复")
            }
            walkInstructions(function.array("instructions")) { instruction ->
                val opcode = instruction.string("opcode")
                if (opcode !in supportedOpcodes) {
                    unsupported += "${instruction.string("instruction_id")}:$opcode"
                }
                if (opcode == "call.project") {
                    val callee = instruction.string("callee_function_id")
                    if (callee.isBlank()) unsupported += "${instruction.string("instruction_id")}:missing-callee"
                }
                if (opcode.startsWith("network.")) {
                    val authorization = instruction.get("network_authorization")
                    if (authorization == null || !authorization.isJsonObject) {
                        unsupported += "${instruction.string("instruction_id")}:missing-network-authorization"
                    }
                }
                if (opcode == "directory.delete_tree") {
                    val review = instruction.obj("dangerous_author_review")
                    if (
                        review.string("fingerprint").isBlank() ||
                        review.string("contract_fingerprint").isBlank()
                    ) {
                        unsupported += "${instruction.string("instruction_id")}:missing-dangerous-review"
                    }
                }
            }
        }
        if (ecir.string("entry_function_id") !in functionIds) {
            fail("AND-ECIR-003", "ECIR 入口函数没有进入链接闭包")
        }
        if (unsupported.isNotEmpty()) {
            fail("AND-ECIR-004", "当前 Android Runtime 不支持指令：${unsupported.sorted().joinToString(", ")}")
        }

        validateForm(form, report)
    }

    private fun validateExtensionApiRequirements(lock: JsonObject, requirements: JsonArray) {
        val lockedFloors = linkedMapOf<String, Int>()
        for (rawExtension in lock.array("extensions")) {
            if (!rawExtension.isJsonObject) fail("AND-API-001", "Android 扩展锁定记录格式无效")
            val extension = rawExtension.asJsonObject
            val packageId = extension.string("package_id")
            var floor: Int? = null
            for (rawVariant in extension.array("selected_variants")) {
                if (!rawVariant.isJsonObject) fail("AND-API-001", "Android 扩展锁定变体格式无效")
                val variant = rawVariant.asJsonObject
                if (variant.string("host") != "android_native") continue
                val value = variant.int("minimum_android_api")
                if (value !in 21..37) fail("AND-API-001", "Android 扩展没有声明有效最低 API")
                floor = maxOf(floor ?: 21, value)
            }
            if (floor != null) {
                if (packageId.isBlank() || lockedFloors.put(packageId, floor) != null) {
                    fail("AND-API-001", "Android 扩展身份缺失或重复")
                }
            }
        }
        val requirementFloors = linkedMapOf<String, Int>()
        for (rawRequirement in requirements) {
            if (!rawRequirement.isJsonObject) continue
            val requirement = rawRequirement.asJsonObject
            if (requirement.string("kind") != "extension") continue
            val packageId = requirement.string("package_id")
            val floor = requirement.int("minimum_android_api")
            if (packageId.isBlank() || requirementFloors.put(packageId, floor) != null) {
                fail("AND-API-001", "Android 扩展最低版本依据格式无效")
            }
        }
        val expected = lockedFloors.filterValues { it > 21 }
        if (requirementFloors != expected) {
            fail("AND-API-001", "Android 扩展变体与项目最低版本依据不一致")
        }
    }

    private fun validateForm(form: JsonObject, report: JsonObject) {
        if (form.int("schema_version") != 3) fail("AND-FORM-001", "Android Player 只接受 Schema 3")
        val pages = form.array("pages")
        val controlIds = mutableSetOf<String>()
        val pageIds = mutableSetOf<String>()
        val closure = JsonArray()
        for (pageValue in pages) {
            if (!pageValue.isJsonObject) fail("AND-FORM-002", "Player 页面记录格式无效")
            val page = pageValue.asJsonObject
            val pageId = page.string("page_id")
            if (pageId.isBlank() || !pageIds.add(pageId)) fail("AND-FORM-002", "Player 页面 ID 缺失或重复")
            for (controlValue in page.array("controls")) {
                if (!controlValue.isJsonObject) fail("AND-FORM-003", "Player 控件记录格式无效")
                val control = controlValue.asJsonObject
                val controlId = control.string("control_id")
                val type = control.string("type")
                if (controlId.isBlank() || !controlIds.add(controlId)) {
                    fail("AND-FORM-003", "Player 控件 ID 缺失或重复")
                }
                if (type != "button" && type !in valueControlTypes) {
                    fail("AND-FORM-003", "Player 控件类型不受支持：$type")
                }
                val bindingKind = control.obj("binding").string("kind")
                if ((type == "button") != (bindingKind == "function_action")) {
                    fail("AND-FORM-004", "Player 按钮和值绑定类型不一致：$controlId")
                }
                for (actionValue in control.array("terminal_actions")) {
                    if (!actionValue.isJsonObject) fail("AND-FORM-005", "Player 字段动作格式无效")
                    val action = actionValue.asJsonObject
                    val actionId = action.string("action_id")
                    val capability = terminalCapabilities[actionId]
                        ?: fail("AND-FORM-005", "Player 字段动作未知：$actionId")
                    val platforms = action.array("platforms").map { it.asString }.sorted()
                    if (platforms.isEmpty() || platforms.size != platforms.toSet().size) {
                        fail("AND-FORM-005", "Player 字段动作平台为空或重复：$controlId/$actionId")
                    }
                    if ("android_local" in platforms && actionId !in androidActions) {
                        fail("AND-FORM-006", "Android 本机没有真实字段动作实现：$actionId")
                    }
                    if ("android_local" in platforms) validateActionType(control, actionId)
                    JsonObject().also { item ->
                        item.addProperty("control_id", controlId)
                        item.addProperty("action_id", actionId)
                        item.add("platforms", JsonArray().also { output -> platforms.forEach(output::add) })
                        item.addProperty("capability", capability)
                        closure.add(item)
                    }
                }
            }
        }
        val sortedClosure = closure.sortedWith(
            compareBy<JsonElement>({ it.asJsonObject.string("control_id") }, { it.asJsonObject.string("action_id") }),
        )
        val expectedClosure = JsonArray().also { array -> sortedClosure.forEach(array::add) }
        if (report.get("player_terminal_actions") != expectedClosure) {
            fail("AND-FORM-007", "Player 字段动作发布闭包与表单不一致")
        }
        val expectedCapabilities = sortedClosure
            .map { it.asJsonObject.string("capability") }
            .toSortedSet()
        val reportedCapabilities = report.array("player_terminal_capabilities").map { it.asString }
        if (reportedCapabilities != expectedCapabilities.toList()) {
            fail("AND-FORM-008", "Player 字段动作能力闭包与发布报告不一致")
        }
    }

    private fun validateActionType(control: JsonObject, actionId: String) {
        val type = control.string("type")
        val sourceType = control.string("source_type")
        val valid = when (actionId) {
            "pick-point" -> type == "coordinate" && sourceType.removeOptional() == "point"
            "pick-region" -> type == "region" && sourceType.removeOptional() == "rect"
            "pick-color" -> type == "color" && sourceType.removeOptional() == "color"
            "capture-image", "choose-resource" -> type == "resource" && sourceType.removeOptional().startsWith("asset_ref")
            "capture-path" -> type == "gesture-path" && sourceType.removeOptional() in setOf("path", "gesture_path")
            "capture-control" -> type == "control-selector" && sourceType.removeOptional() == "control_selector"
            "choose-file-read", "choose-file-save" -> type == "file" && sourceType.removeOptional().startsWith("file_ref")
            "choose-directory" -> type == "directory" && sourceType.removeOptional().startsWith("directory_ref")
            else -> false
        }
        if (!valid) fail("AND-FORM-009", "Player 字段动作与强类型 Control 不匹配：${control.string("control_id")}/$actionId")
    }

    private fun String.removeOptional(): String {
        var value = this
        while (value.startsWith("optional<") && value.endsWith('>')) {
            value = value.substring(9, value.length - 1)
        }
        return value
    }

    private fun walkInstructions(instructions: JsonArray, visit: (JsonObject) -> Unit) {
        for (value in instructions) {
            if (!value.isJsonObject) fail("AND-ECIR-005", "ECIR 指令格式无效")
            val instruction = value.asJsonObject
            if (instruction.string("instruction_id").isBlank() || instruction.string("opcode").isBlank()) {
                fail("AND-ECIR-005", "ECIR 指令缺少稳定 ID 或 opcode")
            }
            visit(instruction)
            val arguments = instruction.obj("arguments")
            for (name in listOf("then", "otherwise", "body", "finally")) {
                walkInstructions(arguments.array(name), visit)
            }
            for (branch in arguments.array("additional_branches")) {
                if (branch.isJsonObject) walkInstructions(branch.asJsonObject.array("body"), visit)
            }
            for (catcher in arguments.array("catches")) {
                if (catcher.isJsonObject) walkInstructions(catcher.asJsonObject.array("body"), visit)
            }
        }
    }

    private fun fail(code: String, message: String): Nothing =
        throw BundleVerificationException(code, message)
}
