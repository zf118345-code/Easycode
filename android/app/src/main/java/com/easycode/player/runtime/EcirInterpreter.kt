package com.easycode.player.runtime

import android.content.Context
import com.easycode.player.EasyCodeApplication
import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.capture.AndroidVisionHost
import com.easycode.player.file.SafFileRuntime
import com.easycode.player.input.AndroidInputHost
import com.easycode.player.input.AndroidControlHost
import com.easycode.player.extension.AndroidExtensionRuntime
import com.easycode.player.profile.PlayerProfile
import com.easycode.player.profile.ProfileStore
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import java.security.SecureRandom
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeParseException

class EcirInterpreter(
    context: Context,
    private val bundle: VerifiedBundle,
    private val profile: PlayerProfile,
    private val bound: BoundRun,
    private val runId: String,
    private val profileStore: ProfileStore,
    private val control: RuntimeControl,
    private val dangerousConfirmations: Set<DangerousRunConfirmation>,
    private val onCheckpoint: (functionId: String, instructionId: String) -> Unit,
    private val onEvent: (level: String, category: String, message: String, instructionId: String, errorId: String) -> Unit,
) : AutoCloseable {
    private val functions = bound.ecir.array("functions").mapNotNull {
        it.takeIf(JsonElement::isJsonObject)?.asJsonObject
    }.associateBy { it.string("function_id") }
    private val evaluator = EcirValueEvaluator(control)
    private val project = linkedMapOf<String, Any?>()
    private val dataRoot = profileStore.dataRoot(bundle)
    private val fileRuntime = SafFileRuntime(
        context,
        dataRoot,
        control,
        profile.revision,
        dangerousConfirmations,
    )
    private val input = AndroidInputHost(context, control)
    private val controls = AndroidControlHost(bound.targetId, control)
    private val targetDefinition = bundle.project.array("targets").mapNotNull {
        it.takeIf(JsonElement::isJsonObject)?.asJsonObject
    }.firstOrNull { it.string("target_id") == bound.targetId }
    private val platform = AndroidPlatformHost(
        context,
        bound.targetId,
        targetDefinition?.string("name").orEmpty(),
        control,
    )
    private val vision = AndroidVisionHost(bundle, profileStore, profile.profileId, bound.targetId, control)
    private val standard = AndroidStandardImageHost(vision, input, controls, control)
    private val network = AndroidNetworkRuntime(fileRuntime, control, onEvent)
    private val extensions = AndroidExtensionRuntime(
        context,
        bundle,
        runId,
        control,
    ) { level, category, message -> onEvent(level, category, message, "", "") }
    private val random = SecureRandom()
    private var currentTargetId = bound.targetId
    private val messages = (context.applicationContext as? EasyCodeApplication)?.messages
    private val listeners = linkedMapOf<String, ListenerRegistration>()
    private var dispatchingListener = false

    init {
        initializeProjectVariables()
    }

    fun run(): Any? {
        val arguments = JsonSupport.toAny(bound.ecir.obj("function_arguments").get(bound.entryFunctionId))
            as? Map<*, *> ?: emptyMap<Any?, Any?>()
        return callFunction(
            bound.entryFunctionId,
            arguments.entries.associate { it.key.toString() to it.value },
            0,
        )
    }

    private fun initializeProjectVariables() {
        val scope = EvaluationScope(linkedMapOf(), project)
        for (raw in bound.ecir.array("project_variables")) {
            if (!raw.isJsonObject) continue
            val definition = raw.asJsonObject
            val id = definition.string("variable_id")
            if (id.isBlank() || id in project) throw RuntimeFailure("runtime.project_variable_invalid", "项目变量稳定 ID 缺失或重复")
            project[id] = evaluator.evaluate(definition.get("default_value"), scope)
        }
        val overrides = bound.ecir.obj("project_variable_overrides")
        for ((id, value) in overrides.entrySet()) {
            if (id !in project) throw RuntimeFailure("runtime.project_variable_unknown", "项目变量不存在：$id")
            project[id] = JsonSupport.toAny(value)
        }
    }

    private fun callFunction(functionId: String, arguments: Map<String, Any?>, depth: Int): Any? {
        control.checkpoint()
        if (depth > 100) throw RuntimeFailure("runtime.call_depth_exceeded", "项目函数调用深度超过 100")
        val definition = functions[functionId] ?: throw RuntimeFailure("runtime.function_missing", "项目函数未链接：$functionId")
        val locals = linkedMapOf<String, Any?>()
        val accepted = mutableSetOf<String>()
        for (raw in definition.array("parameter_definitions")) {
            if (!raw.isJsonObject) throw RuntimeFailure("runtime.function_contract_invalid", "函数参数定义无效")
            val parameter = raw.asJsonObject
            val parameterId = parameter.string("parameter_id")
            val symbolId = parameter.string("name")
            if (parameterId.isBlank() || symbolId.isBlank() || !accepted.add(parameterId)) {
                throw RuntimeFailure("runtime.function_contract_invalid", "函数参数缺少稳定 ID 或局部符号")
            }
            val value = if (parameterId in arguments) arguments[parameterId]
            else if (!parameter.bool("required", true)) evaluator.evaluate(parameter.get("default"), EvaluationScope(locals, project))
            else throw RuntimeFailure("runtime.argument_missing", "函数缺少必填参数：${parameter.string("display_name", symbolId)}")
            if (!conforms(value, parameter.string("value_type", "any"))) {
                throw RuntimeFailure("runtime.argument_type", "函数参数 ${parameter.string("display_name", symbolId)} 类型无效")
            }
            locals[symbolId] = value
        }
        val unknown = arguments.keys - accepted
        if (unknown.isNotEmpty()) throw RuntimeFailure("runtime.argument_unknown", "函数收到未声明参数：${unknown.sorted().first()}")
        val scope = EvaluationScope(locals, project)
        try {
            executeBlock(functionId, definition.array("instructions"), scope, depth)
        } catch (signal: ReturnSignal) {
            val returnType = definition.string("return_type", "any")
            if (!conforms(signal.value, returnType)) throw RuntimeFailure("runtime.return_type", "函数返回值不符合 $returnType")
            return signal.value
        }
        val returnType = definition.string("return_type", "unit")
        if (returnType !in setOf("unit", "null", "any") && !returnType.startsWith("optional<")) {
            throw RuntimeFailure("runtime.return_missing", "函数声明返回 $returnType，但执行路径没有返回值")
        }
        return null
    }

    private fun executeBlock(functionId: String, instructions: JsonArray, scope: EvaluationScope, depth: Int) {
        for (raw in instructions) {
            if (!raw.isJsonObject) throw RuntimeFailure("runtime.instruction_invalid", "ECIR 指令格式无效")
            val instruction = raw.asJsonObject
            val instructionId = instruction.string("instruction_id")
            val opcode = instruction.string("opcode")
            onCheckpoint(functionId, instructionId)
            control.checkpoint()
            dispatchListeners(functionId, depth)
            val arguments = instruction.obj("arguments")
            val result = when (opcode) {
                "log.write" -> log(arguments, scope, instructionId)
                "wait.duration" -> {
                    control.sleep(duration(evaluate(arguments, "official.wait.duration.parameter.duration", scope), 0L))
                    null
                }
                "wait.until" -> waitUntil(arguments, scope, instructionId)
                "random.integer" -> randomInteger(arguments, scope)
                "time.now" -> now(arguments, scope)
                "time.today" -> today(arguments, scope)
                "project.data_directory" -> fileRuntime.projectDataReference()
                "data.assign", "data.assign_local", "data.assign_project" -> assign(opcode, arguments, scope)
                "call.project" -> {
                    val values = arguments.entrySet().associate { it.key to evaluator.evaluate(it.value, scope) }
                    callFunction(instruction.string("callee_function_id"), values, depth + 1)
                }
                "call.extension" -> extensions.execute(
                    instructionId,
                    instruction.string("callee_function_id"),
                    evaluated(arguments, scope),
                    instruction.get("timeout_ms")?.asLong ?: 30_000L,
                )
                "control.if" -> executeIf(functionId, arguments, scope, depth)
                "control.repeat" -> executeRepeat(functionId, arguments, scope, depth)
                "control.while" -> executeWhile(functionId, arguments, scope, depth)
                "control.for_each" -> executeForEach(functionId, arguments, scope, depth)
                "control.for_each_map" -> executeForEachMap(functionId, arguments, scope, depth)
                "control.break" -> throw BreakSignal
                "control.continue" -> throw ContinueSignal
                "control.fail" -> throw RuntimeFailure(
                    arguments.string("error_id", "project.explicit_failure"),
                    evaluator.evaluate(arguments.get("message"), scope)?.toString() ?: "任务失败",
                    transient = false,
                    details = arguments.get("details")?.takeUnless(JsonElement::isJsonNull)?.let {
                        evaluator.evaluate(it, scope)
                    },
                )
                "control.try" -> executeTry(functionId, instructionId, arguments, scope, depth)
                "control.return" -> throw ReturnSignal(
                    arguments.get("value")?.takeUnless(JsonElement::isJsonNull)?.let { evaluator.evaluate(it, scope) },
                )
                "control.target_scope" -> targetScope(functionId, arguments, scope, depth)
                "control.listen" -> registerListener(instructionId, arguments, scope)
                "message.send", "message.wait_receive", "message.wait_read", "message.cancel" ->
                    messageRuntime().execute(bundle, opcode, instruction.string("function_id"), evaluated(arguments, scope), control)
                "network.request", "network.upload_file", "network.download_file" ->
                    network.execute(
                        opcode,
                        instruction.string("function_id"),
                        evaluated(arguments, scope),
                        instruction.get("network_authorization")?.let(JsonSupport::toAny),
                        instructionId,
                    )
                "target.capture_frame", "frame.crop_region", "vision.compare_samples",
                "color.read", "color.find", "vision.find", "vision.find_all", "text.recognize" ->
                    vision.execute(opcode, evaluated(arguments, scope))
                "frame.save" -> vision.saveFrame(evaluated(arguments, scope), fileRuntime)
                "input.click", "input.text", "input.scroll", "input.drag", "input.key" ->
                    input.execute(opcode, evaluated(arguments, scope))
                "control.find", "control.click", "control.read_text", "control.input_text",
                "control.read_status", "control.focus", "control.set_value", "control.select",
                "control.toggle", "control.scroll_into_view" ->
                    controls.execute(opcode, evaluated(arguments, scope))
                "target.wait_online", "target.status", "host.app.start", "host.app.wait_exit",
                "clipboard.read_text", "clipboard.write_text" ->
                    platform.execute(opcode, evaluated(arguments, scope))
                "standard.image.wait_visible", "standard.image.wait_hidden",
                "standard.image.click_once", "standard.image.click_until_hidden",
                "standard.image.click_position_until_visible", "standard.image.click_position_until_hidden",
                "standard.text.match", "standard.text.wait_visible",
                "standard.control.wait_visible", "standard.control.wait_hidden" ->
                    standard.execute(opcode, evaluated(arguments, scope))
                else -> if (opcode.startsWith("file.") || opcode.startsWith("directory.")) {
                    fileRuntime.execute(
                        opcode,
                        instructionId,
                        evaluated(arguments, scope),
                        instruction.obj("dangerous_author_review").string("contract_fingerprint"),
                    )
                } else {
                    throw RuntimeFailure("runtime.operation_unsupported", "Android Runtime 未绑定指令：$opcode")
                }
            }
            val resultType = instruction.string("result_type", "any")
            if (!conforms(result, resultType)) {
                throw RuntimeFailure(
                    "runtime.result_type",
                    "指令 $instructionId 的结果不符合声明类型 $resultType",
                )
            }
            instruction.get("result_slot")?.takeUnless(JsonElement::isJsonNull)?.asString?.takeIf(String::isNotBlank)?.let {
                scope.locals[it] = result
            }
        }
        control.checkpoint()
        dispatchListeners(functionId, depth)
    }

    private fun registerListener(instructionId: String, arguments: JsonObject, scope: EvaluationScope): Any? {
        val messages = messageRuntime()
        val event = arguments.obj("event_source")
        val slot = arguments.string("receive_slot")
        val handler = arguments.string("handler_function_id")
        val dispatch = arguments.obj("dispatch")
        if (
            instructionId.isBlank() || event.string("kind") != "message" || slot.isBlank() ||
            handler.isBlank() || handler !in functions ||
            !dispatch.bool("serial") || !dispatch.bool("fifo") || !dispatch.bool("safe_checkpoint")
        ) throw RuntimeFailure("runtime.listener_contract_invalid", "消息监听运行契约无效")
        val name = evaluator.evaluate(event.get("name"), scope)?.toString().orEmpty()
        val sender = event.get("sender")?.takeUnless(JsonElement::isJsonNull)?.let { evaluator.evaluate(it, scope) }
        // Validate the filter without taking ownership of a message.
        messages.peek(bundle, name, sender)
        listeners[instructionId] = ListenerRegistration(
            listenerId = instructionId,
            name = name,
            sender = sender,
            receiveSlot = slot,
            condition = arguments.get("condition")?.takeUnless(JsonElement::isJsonNull)?.deepCopy(),
            handlerFunctionId = handler,
            handlerArguments = arguments.obj("handler_arguments").deepCopy(),
            declaredScope = scope,
        )
        onEvent("info", "message", "监听器已注册：listener_id=$instructionId", instructionId, "")
        return null
    }

    private fun dispatchListeners(functionId: String, depth: Int) {
        if (dispatchingListener || listeners.isEmpty()) return
        val messages = messageRuntime()
        dispatchingListener = true
        try {
            val snapshot = listeners.values.associateWith { messages.snapshotCandidates(bundle, it.name, it.sender) }
            for ((registration, candidates) in snapshot) {
                for (candidate in candidates) {
                    control.checkpoint()
                    val eventScope = EvaluationScope(LinkedHashMap(registration.declaredScope.locals), project)
                    eventScope.locals[registration.receiveSlot] = JsonSupport.toAny(candidate)
                    if (registration.condition != null && !EcirValueEvaluator.truthy(evaluator.evaluate(registration.condition, eventScope))) break
                    val claimed = messages.claimById(bundle, candidate.string("message_id")) ?: continue
                    eventScope.locals[registration.receiveSlot] = JsonSupport.toAny(claimed)
                    val messageId = claimed.string("message_id")
                    onEvent("info", "message", "监听器接手消息：listener_id=${registration.listenerId} message_id=$messageId", registration.listenerId, "")
                    try {
                        val values = registration.handlerArguments.entrySet().associate { it.key to evaluator.evaluate(it.value, eventScope) }
                        callFunction(registration.handlerFunctionId, values, depth + 1)
                        onEvent("info", "message", "监听处理完成：listener_id=${registration.listenerId} message_id=$messageId", registration.listenerId, "")
                    } catch (error: Throwable) {
                        onEvent("error", "message", "监听处理失败：listener_id=${registration.listenerId} message_id=$messageId", registration.listenerId, (error as? RuntimeFailure)?.errorId ?: "runtime.internal")
                        throw error
                    }
                }
            }
        } finally {
            dispatchingListener = false
            onCheckpoint(functionId, "")
        }
    }

    private fun messageRuntime() = messages
        ?: throw RuntimeFailure("message.transport_unavailable", "当前 Android 测试宿主没有初始化消息服务", transient = true)

    private data class ListenerRegistration(
        val listenerId: String,
        val name: String,
        val sender: Any?,
        val receiveSlot: String,
        val condition: JsonElement?,
        val handlerFunctionId: String,
        val handlerArguments: JsonObject,
        val declaredScope: EvaluationScope,
    )

    private fun log(arguments: JsonObject, scope: EvaluationScope, instructionId: String): Any? {
        val level = evaluate(arguments, "official.log.output.parameter.level", scope)?.toString() ?: "info"
        if (level !in setOf("info", "warning", "error")) throw RuntimeFailure("runtime.argument_type", "日志级别无效")
        val category = evaluate(arguments, "official.log.output.parameter.category", scope)?.toString()?.trim().orEmpty().ifBlank { "script" }
        val content = evaluate(arguments, "official.log.output.parameter.content", scope)?.toString() ?: "null"
        onEvent(level, category, content, instructionId, "")
        return null
    }

    private fun waitUntil(arguments: JsonObject, scope: EvaluationScope, instructionId: String): Any? {
        val raw = evaluate(arguments, "official.wait.until.parameter.time", scope)
        val policy = evaluate(arguments, "official.wait.until.parameter.past_policy", scope)?.toString() ?: "next_day"
        val now = ZonedDateTime.now()
        val target = try {
            when (raw) {
                is Map<*, *> -> LocalTime.parse(raw["value"]?.toString()).atDate(now.toLocalDate()).atZone(now.zone)
                else -> LocalTime.parse(raw?.toString()).atDate(now.toLocalDate()).atZone(now.zone)
            }
        } catch (error: DateTimeParseException) {
            throw RuntimeFailure("time.value_invalid", "等待时间点格式无效", cause = error)
        }.let { value ->
            if (value.isBefore(now)) {
                if (policy == "next_day") value.plusDays(1)
                else if (policy in setOf("immediate", "now")) now
                else throw RuntimeFailure("time.past_policy_invalid", "当日已过策略无效")
            } else value
        }
        onEvent("info", "script", "等待到 ${target.toLocalTime()}", instructionId, "")
        while (true) {
            control.checkpoint()
            val remaining = java.time.Duration.between(ZonedDateTime.now(), target).toMillis()
            if (remaining <= 0L) return null
            control.sleep(remaining.coerceAtMost(100L))
        }
    }

    private fun randomInteger(arguments: JsonObject, scope: EvaluationScope): Long {
        val minimum = (evaluate(arguments, "official.random.integer.parameter.minimum", scope) as? Number)?.toLong() ?: 0L
        val maximum = (evaluate(arguments, "official.random.integer.parameter.maximum", scope) as? Number)?.toLong() ?: 100L
        if (minimum > maximum) throw RuntimeFailure("random.range_invalid", "随机整数最小值不能大于最大值")
        val range = maximum.toBigInteger() - minimum.toBigInteger() + java.math.BigInteger.ONE
        var candidate: java.math.BigInteger
        do candidate = java.math.BigInteger(range.bitLength(), random) while (candidate >= range)
        return minimum.toBigInteger().add(candidate).toLong()
    }

    private fun now(arguments: JsonObject, scope: EvaluationScope): String {
        val zone = zone(evaluate(arguments, "official.time.now.parameter.timezone", scope))
        return OffsetDateTime.now(zone).toString()
    }

    private fun today(arguments: JsonObject, scope: EvaluationScope): String {
        val zone = zone(evaluate(arguments, "official.time.today.parameter.timezone", scope))
        return LocalDate.now(zone).toString()
    }

    private fun zone(value: Any?): ZoneId = try {
        if (value == null || value.toString().isBlank()) ZoneId.systemDefault()
        else ZoneId.of(value.toString())
    } catch (error: Exception) {
        throw RuntimeFailure("time.timezone_invalid", "时区无效：$value", cause = error)
    }

    private fun assign(opcode: String, arguments: JsonObject, scope: EvaluationScope): Any? {
        val value = evaluator.evaluate(arguments.get("value"), scope)
        if (opcode == "data.assign") return value
        val target = arguments.obj("target")
        if (opcode == "data.assign_local") {
            val id = target.string("symbol_id")
            if (id.isBlank()) throw RuntimeFailure("runtime.assignment_invalid", "局部赋值缺少 symbol_id")
            scope.locals[id] = value
        } else {
            val id = target.string("variable_id")
            if (id !in project) throw RuntimeFailure("runtime.project_variable_unknown", "项目变量不存在：$id")
            project[id] = value
        }
        return value
    }

    private fun executeIf(functionId: String, arguments: JsonObject, scope: EvaluationScope, depth: Int): Any? {
        if (EcirValueEvaluator.truthy(evaluator.evaluate(arguments.get("condition"), scope))) {
            executeBlock(functionId, arguments.array("then"), scope, depth)
            return null
        }
        for (raw in arguments.array("additional_branches")) {
            if (!raw.isJsonObject) continue
            val branch = raw.asJsonObject
            if (EcirValueEvaluator.truthy(evaluator.evaluate(branch.get("condition"), scope))) {
                executeBlock(functionId, branch.array("body"), scope, depth)
                return null
            }
        }
        executeBlock(functionId, arguments.array("otherwise"), scope, depth)
        return null
    }

    private fun executeRepeat(functionId: String, arguments: JsonObject, scope: EvaluationScope, depth: Int): Any? {
        val count = evaluator.evaluate(arguments.get("source") ?: arguments.get("count"), scope)
        if (count !is Number || count.toLong() < 0L || count.toLong() > 1_000_000L) throw RuntimeFailure("runtime.loop_limit", "重复次数必须为 0..1000000")
        repeat(count.toInt()) {
            control.checkpoint()
            try { executeBlock(functionId, arguments.array("body"), scope, depth) }
            catch (_: ContinueSignal) { return@repeat }
            catch (_: BreakSignal) { return null }
        }
        return null
    }

    private fun executeWhile(functionId: String, arguments: JsonObject, scope: EvaluationScope, depth: Int): Any? {
        var iterations = 0
        val condition = arguments.get("source") ?: arguments.get("condition")
        while (EcirValueEvaluator.truthy(evaluator.evaluate(condition, scope))) {
            if (++iterations > 1_000_000) throw RuntimeFailure("runtime.loop_limit", "循环超过 1000000 次")
            try { executeBlock(functionId, arguments.array("body"), scope, depth) }
            catch (_: ContinueSignal) { continue }
            catch (_: BreakSignal) { break }
        }
        return null
    }

    private fun executeForEach(functionId: String, arguments: JsonObject, scope: EvaluationScope, depth: Int): Any? {
        val source = evaluator.evaluate(arguments.get("source"), scope) as? Iterable<*>
            ?: throw RuntimeFailure("runtime.argument_type", "逐项循环来源必须是列表")
        val items = if (arguments.bool("snapshot")) source.toList() else source
        val bindings = arguments.obj("bindings")
        val itemId = bindings.obj("item").string("symbol_id")
        val indexId = bindings.obj("index").string("symbol_id")
        if (itemId.isBlank()) throw RuntimeFailure("runtime.loop_binding", "逐项循环缺少项绑定")
        for ((index, item) in items.withIndex()) {
            if (index >= 1_000_000) throw RuntimeFailure("runtime.loop_limit", "逐项循环超过 1000000 项")
            scope.locals[itemId] = item
            if (indexId.isNotBlank()) scope.locals[indexId] = index.toLong()
            try { executeBlock(functionId, arguments.array("body"), scope, depth) }
            catch (_: ContinueSignal) { continue }
            catch (_: BreakSignal) { break }
        }
        return null
    }

    private fun executeForEachMap(functionId: String, arguments: JsonObject, scope: EvaluationScope, depth: Int): Any? {
        val source = evaluator.evaluate(arguments.get("source"), scope) as? Map<*, *>
            ?: throw RuntimeFailure("runtime.argument_type", "字典循环来源必须是字典")
        val entries = source.entries.toList()
        val bindings = arguments.obj("bindings")
        val keyId = bindings.obj("key").string("symbol_id")
        val valueId = bindings.obj("value").string("symbol_id")
        val indexId = bindings.obj("index").string("symbol_id")
        if (keyId.isBlank() || valueId.isBlank()) throw RuntimeFailure("runtime.loop_binding", "字典循环缺少键/值绑定")
        for ((index, entry) in entries.withIndex()) {
            if (index >= 1_000_000) throw RuntimeFailure("runtime.loop_limit", "字典循环超过 1000000 项")
            scope.locals[keyId] = entry.key
            scope.locals[valueId] = entry.value
            if (indexId.isNotBlank()) scope.locals[indexId] = index.toLong()
            try { executeBlock(functionId, arguments.array("body"), scope, depth) }
            catch (_: ContinueSignal) { continue }
            catch (_: BreakSignal) { break }
        }
        return null
    }

    private fun executeTry(
        functionId: String,
        instructionId: String,
        arguments: JsonObject,
        scope: EvaluationScope,
        depth: Int,
    ): Any? {
        val retry = arguments.get("retry_policy")?.takeIf(JsonElement::isJsonObject)?.asJsonObject
        val maxRetries = retry?.let { (evaluator.evaluate(it.get("max_retries"), scope) as? Number)?.toInt() } ?: 0
        val interval = retry?.let { duration(evaluator.evaluate(it.get("interval"), scope), 0L) } ?: 0L
        var attempts = 0
        try {
            while (true) {
                try {
                    executeBlock(functionId, arguments.array("body"), scope, depth)
                    break
                } catch (flow: ReturnSignal) { throw flow }
                catch (flow: BreakSignal) { throw flow }
                catch (flow: ContinueSignal) { throw flow }
                catch (error: RuntimeFailure) {
                    if (attempts >= maxRetries || (retry?.bool("transient_only", true) == true && !error.transient)) throw error
                    attempts++
                    onEvent("warning", "runtime", "执行失败，准备第 $attempts 次重试：${error.message}", instructionId, error.errorId)
                    control.sleep(interval)
                }
            }
        } catch (flow: ReturnSignal) { throw flow }
        catch (flow: BreakSignal) { throw flow }
        catch (flow: ContinueSignal) { throw flow }
        catch (error: RuntimeFailure) {
            val catcher = arguments.array("catches").mapNotNull {
                it.takeIf(JsonElement::isJsonObject)?.asJsonObject
            }.firstOrNull { clause ->
                clause.array("error_ids").size() == 0 || clause.array("error_ids").any { it.asString == error.errorId }
            } ?: throw error
            val slot = catcher.string("error_slot")
            if (slot.isNotBlank()) scope.locals[slot] = mapOf(
                "error_id" to error.errorId,
                "message" to error.message,
                "details" to error.details,
            )
            executeBlock(functionId, catcher.array("body"), scope, depth)
        } finally {
            executeBlock(functionId, arguments.array("finally"), scope, depth)
        }
        return null
    }

    private fun targetScope(functionId: String, arguments: JsonObject, scope: EvaluationScope, depth: Int): Any? {
        val value = evaluator.evaluate(arguments.get("target"), scope) as? Map<*, *>
            ?: throw RuntimeFailure("target.reference_invalid", "目标作用域缺少 target_ref")
        val next = value["target_id"]?.toString().orEmpty()
        if (next != bound.targetId) throw RuntimeFailure("target.scope_unsupported", "APK 不能进入另一设备目标作用域：$next")
        val previous = currentTargetId
        currentTargetId = next
        try { executeBlock(functionId, arguments.array("body"), scope, depth) }
        finally { currentTargetId = previous }
        return null
    }

    private fun evaluated(arguments: JsonObject, scope: EvaluationScope): Map<String, Any?> =
        arguments.entrySet().associate { it.key to evaluator.evaluate(it.value, scope) }

    private fun evaluate(arguments: JsonObject, id: String, scope: EvaluationScope): Any? =
        evaluator.evaluate(arguments.get(id), scope)

    private fun duration(value: Any?, default: Long): Long = when (value) {
        null -> default
        is Number -> value.toLong()
        is Map<*, *> -> (value["milliseconds"] as? Number)?.toLong() ?: default
        else -> throw RuntimeFailure("runtime.argument_type", "持续时间参数无效")
    }.also { if (it < 0L) throw RuntimeFailure("runtime.argument_range", "持续时间不能为负数") }

    private fun conforms(value: Any?, type: String): Boolean {
        if (type == "any") return true
        if (type.startsWith("optional<") && type.endsWith('>')) return value == null || conforms(value, type.substring(9, type.length - 1))
        if (value == null) return type in setOf("unit", "null")
        return when {
            type == "bool" -> value is Boolean
            type == "int64" -> value is Byte || value is Short || value is Int || value is Long
            type in setOf("float64", "percentage", "duration") -> value is Number
            type in setOf("string", "date", "datetime", "time", "time_of_day", "timezone", "relative_path", "url") || type.startsWith("enum<") -> value is String
            type.startsWith("list<") -> value is List<*>
            type.startsWith("map<") || type.startsWith("record<") -> value is Map<*, *>
            type.startsWith("file_ref") -> value is Map<*, *> && value["kind"] == "file_ref"
            type.startsWith("directory_ref") -> value is Map<*, *> && value["kind"] == "directory_ref"
            type.startsWith("asset_ref") -> value is Map<*, *> && value["asset_id"] != null
            else -> true
        }
    }

    override fun close() {
        extensions.close()
        controls.close()
        vision.close()
    }
}
