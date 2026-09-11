package com.easycode.player.runtime

import com.easycode.player.file.AndroidReadableFile
import com.easycode.player.file.SafFileRuntime
import com.easycode.player.util.JsonSupport
import java.io.ByteArrayOutputStream
import java.io.FileOutputStream
import java.io.InterruptedIOException
import java.net.IDN
import java.net.Inet6Address
import java.net.InetAddress
import java.net.URI
import java.net.UnknownHostException
import java.nio.charset.Charset
import java.nio.charset.StandardCharsets
import java.util.Locale
import java.util.UUID
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import javax.net.ssl.SSLException
import okhttp3.Call
import okhttp3.Dns
import okhttp3.Headers
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okio.BufferedSink

/** Android implementation of the three official typed HTTP atoms.
 *
 * Every call owns an isolated OkHttp client, has no cookie/session state and
 * performs redirects manually. DNS is resolved and classified before the
 * connection; the approved addresses are then pinned into OkHttp's DNS hook,
 * while the original host remains available for Host/SNI verification.
 */
internal class AndroidNetworkRuntime(
    private val files: SafFileRuntime,
    private val control: RuntimeControl,
    private val onEvent: (level: String, category: String, message: String, instructionId: String, errorId: String) -> Unit,
) {
    fun execute(
        opcode: String,
        functionId: String,
        arguments: Map<String, Any?>,
        authorization: Any?,
        instructionId: String,
    ): Any? {
        if (opcode !in SUPPORTED) {
            throw RuntimeFailure("network.operation_unsupported", "网络运行时不支持：$opcode")
        }
        val normalized = normalizeAuthorization(authorization)
        control.checkpoint()
        return when (opcode) {
            "network.request" -> request(functionId, arguments, normalized, instructionId)
            "network.upload_file" -> upload(functionId, arguments, normalized, instructionId)
            "network.download_file" -> download(functionId, arguments, normalized, instructionId)
            else -> error("unreachable")
        }
    }

    private fun request(
        fid: String,
        args: Map<String, Any?>,
        authorization: Authorization,
        instructionId: String,
    ): Map<String, Any?> {
        val shared = shared(fid, args, 30_000L)
        val method = argument(args, fid, "method")?.toString()?.uppercase(Locale.ROOT) ?: "GET"
        if (method !in METHODS) throw RuntimeFailure("network.method_invalid", "HTTP 方法无效")
        val (body, contentType) = requestBody(argument(args, fid, "body"))
        if (method in setOf("GET", "HEAD") && body != null) {
            throw RuntimeFailure("network.body_not_allowed", "GET 或 HEAD 请求不能携带正文")
        }
        val headers = shared.headers.toMutableList()
        if (body != null && contentType != null && headers.none { it.name.equals("content-type", true) }) {
            headers += PairValue("Content-Type", contentType, false)
        }
        return streamRequest(
            operation = "request",
            initialMethod = method,
            shared = shared,
            authorization = authorization,
            instructionId = instructionId,
            requestBody = { currentMethod ->
                if (body == null || (currentMethod in setOf("GET", "HEAD") && currentMethod != method)) null
                else body.toRequestBody(contentType?.toMediaTypeOrNull())
            },
        ) { response, deadline ->
            val raw = readLimited(response, shared.responseLimit, deadline, "response")
            responseRecord(response, raw)
        }
    }

    private fun upload(
        fid: String,
        args: Map<String, Any?>,
        authorization: Authorization,
        instructionId: String,
    ): Map<String, Any?> {
        val shared = shared(fid, args, 60_000L)
        val maximum = boundedLong(
            argument(args, fid, "max_file_bytes"),
            512L * 1024L * 1024L,
            1L,
            8L * 1024L * 1024L * 1024L,
            "network.upload_limit_invalid",
        )
        val rawFields = argument(args, fid, "fields") as? List<*>
            ?: throw RuntimeFailure("network.multipart_invalid", "multipart 字段必须是非空有序列表")
        if (rawFields.isEmpty() || rawFields.size > 1024) {
            throw RuntimeFailure("network.multipart_invalid", "multipart 字段必须是非空有序列表")
        }
        val fields = rawFields.map { raw ->
            val field = stringMap(raw)
                ?: throw RuntimeFailure("network.multipart_invalid", "multipart 字段无效")
            val kind = recordField(field, "multipart_field", "kind")?.toString()
                ?: field["field_type"]?.toString().orEmpty()
            val name = recordField(field, "multipart_field", "name")?.toString().orEmpty()
            if (name.isBlank() || name.any { it == '\r' || it == '\n' }) {
                throw RuntimeFailure("network.multipart_invalid", "multipart 字段名无效")
            }
            val contentType = recordField(field, "multipart_field", "content_type")?.toString()?.takeIf(String::isNotBlank)
            when (kind) {
                "text" -> {
                    val value = recordField(field, "multipart_field", "value")
                        ?: recordField(field, "multipart_field", "text")
                    if (value !is String) throw RuntimeFailure("network.multipart_invalid", "multipart 文本字段无效")
                    UploadField.Text(name, value, contentType ?: "text/plain; charset=utf-8")
                }
                "file" -> {
                    val reference = recordField(field, "multipart_field", "file") ?: field["reference"]
                    val source = files.prepareNetworkUpload(reference, maximum)
                    val filename = recordField(field, "multipart_field", "filename")?.toString()
                        ?.takeIf(String::isNotBlank) ?: source.displayName
                    UploadField.File(name, filename, contentType ?: "application/octet-stream", source, maximum)
                }
                else -> throw RuntimeFailure("network.multipart_invalid", "multipart 字段类型无效")
            }
        }
        return streamRequest(
            operation = "upload",
            initialMethod = "POST",
            shared = shared,
            authorization = authorization,
            instructionId = instructionId,
            requestBody = { currentMethod ->
                if (currentMethod == "GET") null else MultipartBody.Builder().setType(MultipartBody.FORM).apply {
                    fields.forEach { field ->
                        when (field) {
                            is UploadField.Text -> addFormDataPart(
                                field.name,
                                null,
                                field.value.toRequestBody(field.contentType.toMediaTypeOrNull()),
                            )
                            is UploadField.File -> addFormDataPart(
                                field.name,
                                field.filename,
                                StreamingFileBody(field.source, field.maximum, control, field.contentType),
                            )
                        }
                    }
                }.build()
            },
        ) { response, deadline ->
            val raw = readLimited(response, shared.responseLimit, deadline, "upload_response")
            responseRecord(response, raw)
        }
    }

    private fun download(
        fid: String,
        args: Map<String, Any?>,
        authorization: Authorization,
        instructionId: String,
    ): Map<String, Any?> {
        val shared = shared(fid, args, 60_000L)
        val maximum = boundedLong(
            argument(args, fid, "max_file_bytes"),
            512L * 1024L * 1024L,
            1L,
            8L * 1024L * 1024L * 1024L,
            "network.download_limit_invalid",
        )
        // Validate atomic storage before the first DNS lookup or connection.
        files.prepareNetworkDownload(argument(args, fid, "destination")).use { target ->
            return streamRequest(
                operation = "download",
                initialMethod = "GET",
                shared = shared,
                authorization = authorization,
                instructionId = instructionId,
                requestBody = { null },
            ) { response, deadline ->
                if (response.code !in 200..299) {
                    val raw = readLimited(response, shared.responseLimit, deadline, "download_error_response")
                    return@streamRequest record(
                        "http_download_result",
                        "status" to response.code.toLong(),
                        "headers" to responseHeaders(response.headers),
                        "final_url" to response.request.url.toString(),
                        "content_type" to response.header("Content-Type").orEmpty(),
                        "committed" to false,
                        "file" to null,
                        "bytes_written" to 0L,
                        "error_body" to decodeText(response, raw),
                        "response_bytes" to raw.size.toLong(),
                    )
                }
                val expected = response.body?.contentLength()?.takeIf { it >= 0L }
                if (expected != null && expected > maximum) {
                    throw RuntimeFailure("network.download_too_large", "下载文件超过允许大小")
                }
                var written = 0L
                try {
                    response.body?.byteStream()?.use { input ->
                        FileOutputStream(target.temporary).use { output ->
                            val buffer = ByteArray(256 * 1024)
                            while (true) {
                                checkStopped()
                                if (System.nanoTime() > deadline) throw timeout("下载超过总超时")
                                val count = input.read(buffer)
                                if (count < 0) break
                                written += count
                                if (written > maximum) {
                                    throw RuntimeFailure("network.download_too_large", "下载文件超过允许大小")
                                }
                                output.write(buffer, 0, count)
                            }
                            output.fd.sync()
                        }
                    } ?: throw RuntimeFailure("network.download_interrupted", "下载响应缺少正文", true)
                } catch (error: RuntimeFailure) {
                    throw error
                } catch (error: Exception) {
                    throw mapTransport(error, "network.download_interrupted", "下载响应中断")
                }
                if (expected != null && written != expected) {
                    throw RuntimeFailure("network.download_interrupted", "下载响应在完整接收前中断", true)
                }
                checkStopped()
                target.commit()
                record(
                    "http_download_result",
                    "status" to response.code.toLong(),
                    "headers" to responseHeaders(response.headers),
                    "final_url" to response.request.url.toString(),
                    "content_type" to response.header("Content-Type").orEmpty(),
                    "committed" to true,
                    "file" to target.reference,
                    "bytes_written" to written,
                    "error_body" to "",
                    "response_bytes" to written,
                )
            }
        }
    }

    private fun streamRequest(
        operation: String,
        initialMethod: String,
        shared: Shared,
        authorization: Authorization,
        instructionId: String,
        requestBody: (String) -> RequestBody?,
        consume: (Response, Long) -> Map<String, Any?>,
    ): Map<String, Any?> {
        val requestId = "request_${UUID.randomUUID().toString().replace("-", "")}" 
        val started = System.nanoTime()
        val deadline = started + TimeUnit.MILLISECONDS.toNanos(shared.timeoutMs)
        var currentUrl = shared.url
        var currentMethod = initialMethod
        var currentHeaders = shared.headers
        var redirects = 0
        var status: Int? = null
        var received = 0L
        var errorId = ""
        var level = "unknown"
        try {
            while (true) {
                checkStopped()
                val remainingMs = TimeUnit.NANOSECONDS.toMillis(deadline - System.nanoTime()).coerceAtLeast(1L)
                if (System.nanoTime() >= deadline) throw timeout("网络操作超过总超时")
                val authorized = authorize(currentUrl, authorization)
                level = if ("public" in authorized.scopes) "public" else "lan"
                val client = OkHttpClient.Builder()
                    .dns(PinnedDns(authorized.host, authorized.addresses))
                    .proxy(java.net.Proxy.NO_PROXY)
                    .followRedirects(false)
                    .followSslRedirects(false)
                    .retryOnConnectionFailure(false)
                    .callTimeout(remainingMs, TimeUnit.MILLISECONDS)
                    .connectTimeout(remainingMs, TimeUnit.MILLISECONDS)
                    .readTimeout(remainingMs, TimeUnit.MILLISECONDS)
                    .writeTimeout(remainingMs, TimeUnit.MILLISECONDS)
                    .build()
                val body = requestBody(currentMethod)
                val request = Request.Builder().url(authorized.url).headers(headers(currentHeaders)).method(currentMethod, body).build()
                val call = client.newCall(request)
                try {
                    executeCancelable(call).use { response ->
                        status = response.code
                        val location = response.header("Location")
                        if (response.code in REDIRECTS && !location.isNullOrBlank() && shared.redirect != "none") {
                            if (redirects >= shared.maxRedirects) {
                                throw RuntimeFailure("network.redirect_limit", "HTTP 重定向次数超过上限")
                            }
                            val next = authorized.url.resolve(location)
                                ?: throw RuntimeFailure("network.url_invalid", "重定向网址无效")
                            val nextAuthorized = authorize(next.toString(), authorization)
                            val crossOrigin = nextAuthorized.origin != authorized.origin
                            if (crossOrigin && shared.redirect != "cross_origin") {
                                throw RuntimeFailure("network.redirect_denied", "跨源重定向未获允许")
                            }
                            if (crossOrigin) currentHeaders = currentHeaders.filterNot {
                                it.sensitive || it.name.lowercase(Locale.ROOT) in CROSS_ORIGIN_STRIP
                            }
                            if (response.code == 303 || (response.code in setOf(301, 302) && currentMethod == "POST")) {
                                currentMethod = "GET"
                            }
                            currentUrl = next.toString()
                            redirects++
                            continue
                        }
                        val result = consume(response, deadline)
                        received = (recordField(result, result["record_type"]?.toString().orEmpty(), "response_bytes") as? Number)?.toLong()
                            ?: 0L
                        return result
                    }
                } catch (error: RuntimeStoppedSignal) {
                    throw error
                } catch (error: RuntimeFailure) {
                    throw error
                } catch (error: Exception) {
                    throw mapTransport(error)
                }
            }
        } catch (error: RuntimeFailure) {
            errorId = error.errorId
            throw error
        } finally {
            val elapsed = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started)
            onEvent(
                if (errorId.isBlank()) "info" else "error",
                "network",
                "网络请求完成：request_id=$requestId operation=$operation method=$initialMethod url=${redactedUrl(currentUrl)} network_level=$level elapsed_ms=$elapsed status=${status ?: ""} response_bytes=$received redirects=$redirects",
                instructionId,
                errorId,
            )
        }
    }

    private fun executeCancelable(call: Call): Response {
        val done = AtomicBoolean(false)
        val watcher = Thread({
            while (!done.get()) {
                if (control.isStopped()) {
                    call.cancel()
                    return@Thread
                }
                try {
                    Thread.sleep(25L)
                } catch (_: InterruptedException) {
                    return@Thread
                }
            }
        }, "easycode-network-cancel").apply { isDaemon = true; start() }
        return try {
            call.execute()
        } finally {
            done.set(true)
            watcher.interrupt()
        }
    }

    private fun shared(fid: String, args: Map<String, Any?>, defaultTimeout: Long): Shared {
        val query = pairs(argument(args, fid, "query"), header = false)
        val base = argument(args, fid, "url")?.toString().orEmpty()
        val parsed = parseUrl(base)
        val builder = parsed.newBuilder()
        query.forEach { builder.addQueryParameter(it.name, it.value) }
        val redirect = argument(args, fid, "redirect")?.toString() ?: "same_origin"
        if (redirect !in setOf("none", "same_origin", "cross_origin")) {
            throw RuntimeFailure("network.redirect_policy_invalid", "重定向策略无效")
        }
        return Shared(
            url = builder.build().toString(),
            headers = pairs(argument(args, fid, "headers"), header = true),
            redirect = redirect,
            timeoutMs = duration(argument(args, fid, "timeout"), defaultTimeout),
            responseLimit = boundedLong(argument(args, fid, "max_response_bytes"), 4L * 1024L * 1024L, 1L, 64L * 1024L * 1024L, "network.response_limit_invalid"),
            maxRedirects = boundedLong(argument(args, fid, "max_redirects"), 5L, 0L, 20L, "network.redirect_limit_invalid").toInt(),
        )
    }

    private fun requestBody(value: Any?): Pair<ByteArray?, String?> {
        if (value == null) return null to null
        val body = stringMap(value) ?: throw RuntimeFailure("network.body_invalid", "普通网络请求正文只支持文本或 JSON")
        return when (recordField(body, "http_body", "kind")?.toString() ?: body["body_type"]?.toString()) {
            "text" -> {
                val text = recordField(body, "http_body", "text") ?: recordField(body, "http_body", "value")
                if (text !is String) throw RuntimeFailure("network.body_invalid", "文本请求正文无效")
                text.toByteArray(StandardCharsets.UTF_8) to (
                    recordField(body, "http_body", "content_type")?.toString()?.takeIf(String::isNotBlank)
                        ?: "text/plain; charset=utf-8"
                )
            }
            "json" -> {
                val data = recordField(body, "http_body", "json") ?: recordField(body, "http_body", "value")
                (JsonSupport.canonical(JsonSupport.fromAny(data)).toByteArray(StandardCharsets.UTF_8)) to "application/json; charset=utf-8"
            }
            else -> throw RuntimeFailure("network.body_invalid", "普通网络请求正文只支持文本或 JSON")
        }
    }

    private fun readLimited(response: Response, maximum: Long, deadline: Long, phase: String): ByteArray {
        val expected = response.body?.contentLength()?.takeIf { it >= 0L }
        if (expected != null && expected > maximum) {
            throw RuntimeFailure("network.response_too_large", "响应正文超过允许大小")
        }
        val output = ByteArrayOutputStream()
        try {
            response.body?.byteStream()?.use { input ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    checkStopped()
                    if (System.nanoTime() > deadline) throw timeout("网络操作超过总超时")
                    val count = input.read(buffer)
                    if (count < 0) break
                    if (output.size().toLong() + count > maximum) {
                        throw RuntimeFailure("network.response_too_large", "响应正文超过允许大小")
                    }
                    output.write(buffer, 0, count)
                }
            }
        } catch (error: RuntimeFailure) {
            throw error
        } catch (error: Exception) {
            throw mapTransport(error, "network.response_interrupted", "响应读取中断")
        }
        val bytes = output.toByteArray()
        if (response.request.method != "HEAD" && expected != null && bytes.size.toLong() != expected) {
            throw RuntimeFailure("network.response_interrupted", "响应在完整接收前中断", true)
        }
        return bytes
    }

    private fun responseRecord(response: Response, raw: ByteArray): Map<String, Any?> = record(
        "http_response",
        "status" to response.code.toLong(),
        "headers" to responseHeaders(response.headers),
        "final_url" to response.request.url.toString(),
        "content_type" to response.header("Content-Type").orEmpty(),
        "body" to decodeText(response, raw),
        "response_bytes" to raw.size.toLong(),
    )

    private fun decodeText(response: Response, bytes: ByteArray): String {
        val contentType = response.header("Content-Type").orEmpty()
        val media = contentType.substringBefore(';').trim().lowercase(Locale.ROOT)
        val textual = media.isBlank() || media.startsWith("text/") || media in TEXT_MEDIA || media.endsWith("+json") || media.endsWith("+xml")
        if (bytes.isNotEmpty() && !textual) {
            throw RuntimeFailure("network.binary_response_unsupported", "普通网络请求不接收二进制响应；请使用下载文件")
        }
        val charsetName = Regex("(?:^|;)\\s*charset\\s*=\\s*([^;]+)", RegexOption.IGNORE_CASE)
            .find(contentType)?.groupValues?.get(1)?.trim()?.trim('"') ?: "utf-8"
        return try {
            val charset = Charset.forName(charsetName)
            val decoder = charset.newDecoder()
            decoder.decode(java.nio.ByteBuffer.wrap(bytes)).toString()
        } catch (error: Exception) {
            throw RuntimeFailure("network.response_encoding_failed", "响应正文编码无效", cause = error)
        }
    }

    private fun responseHeaders(headers: Headers): List<Map<String, Any?>> = (0 until headers.size).map { index ->
        record("http_pair", "name" to headers.name(index), "value" to headers.value(index), "sensitive" to false)
    }

    private fun pairs(value: Any?, header: Boolean): List<PairValue> {
        if (value == null || value == emptyList<Any>()) return emptyList()
        val list = value as? List<*> ?: throw RuntimeFailure("network.pairs_invalid", "请求键值字段必须是有序列表且数量受限")
        if (list.size > if (header) 256 else 1024) throw RuntimeFailure("network.pairs_invalid", "请求键值字段必须是有序列表且数量受限")
        return list.map { raw ->
            val item = stringMap(raw) ?: throw RuntimeFailure("network.pairs_invalid", "请求键值项无效")
            val name = recordField(item, "http_pair", "name")?.toString().orEmpty()
            val rawValue = recordField(item, "http_pair", "value")
                ?: throw RuntimeFailure("network.pairs_invalid", "请求键值项缺少名称或值")
            val text = rawValue.toString()
            if (name.isBlank() || name.any { it in "\r\n:" } || text.any { it in "\r\n" }) {
                throw RuntimeFailure("network.pairs_invalid", "请求键值项包含非法控制符")
            }
            val lowered = name.lowercase(Locale.ROOT)
            if (header && lowered in MANAGED_HEADERS) {
                throw RuntimeFailure("network.header_denied", "请求头 $name 由传输层管理")
            }
            PairValue(name, text, recordField(item, "http_pair", "sensitive") as? Boolean == true || (header && lowered in SENSITIVE_HEADERS))
        }
    }

    private fun headers(values: List<PairValue>): Headers = Headers.Builder().apply {
        values.forEach { add(it.name, it.value) }
    }.build()

    private fun authorize(rawUrl: String, authorization: Authorization): AuthorizedUrl {
        val url = parseUrl(rawUrl)
        val host = normalizeHost(url.host)
        val port = url.port
        val rule = authorization.rules.firstOrNull {
            url.scheme in it.schemes && host in it.hosts && port in it.ports
        } ?: throw RuntimeFailure("network.permission_denied", "网络目标不在作者批准的主机和端口范围内")
        val addresses = try {
            InetAddress.getAllByName(host).distinctBy { it.hostAddress }.also {
                if (it.isEmpty()) throw UnknownHostException(host)
            }
        } catch (error: UnknownHostException) {
            throw RuntimeFailure("network.dns_failed", "无法解析网络目标", true, error)
        }
        val scopes = addresses.map(::addressScope).toSet()
        if (!rule.scopes.containsAll(scopes)) {
            throw RuntimeFailure("network.address_scope_denied", "域名解析结果超出作者批准的地址范围")
        }
        return AuthorizedUrl(url, host, "${url.scheme}://$host:$port", addresses, scopes)
    }

    private fun parseUrl(raw: String): HttpUrl {
        if (raw.isBlank() || raw.any { it.code < 32 || it.code == 127 }) throw RuntimeFailure("network.url_invalid", "URL 不能为空或包含控制字符")
        val uri = try { URI(raw.trim()) } catch (error: Exception) {
            throw RuntimeFailure("network.url_invalid", "URL 结构无效", cause = error)
        }
        if (uri.scheme?.lowercase(Locale.ROOT) !in setOf("http", "https")) throw RuntimeFailure("network.scheme_denied", "网络函数只允许 http 或 https URL")
        if (uri.userInfo != null) throw RuntimeFailure("network.credentials_in_url", "URL 不允许内嵌用户名或密码")
        return raw.trim().toHttpUrlOrNull() ?: throw RuntimeFailure("network.url_invalid", "URL 主机或端口无效")
    }

    private fun normalizeAuthorization(value: Any?): Authorization {
        val map = stringMap(value) ?: throw RuntimeFailure("network.permission_denied", "网络调用缺少编译期授权闭包")
        if ((map["schema_version"] as? Number)?.toInt() != 1) throw RuntimeFailure("network.permission_denied", "网络授权闭包版本不受支持")
        val rules = (map["rules"] as? List<*>)?.map { raw ->
            val rule = stringMap(raw) ?: throw RuntimeFailure("network.permission_denied", "网络授权闭包无效")
            val id = rule["rule_id"]?.toString().orEmpty()
            val schemes = stringSet(rule["schemes"])
            val hosts = stringSet(rule["hosts"]).map(::normalizeHost).toSet()
            val ports = (rule["ports"] as? List<*>)?.mapNotNull { (it as? Number)?.toInt() }?.toSet().orEmpty()
            val scopes = stringSet(rule["address_scopes"])
            if (id.isBlank() || schemes.isEmpty() || schemes.any { it !in setOf("http", "https") } || hosts.isEmpty() || ports.isEmpty() || ports.any { it !in 1..65535 } || scopes.isEmpty() || scopes.any { it !in SCOPES }) {
                throw RuntimeFailure("network.permission_denied", "网络授权闭包无效")
            }
            Rule(schemes, hosts, ports, scopes)
        } ?: emptyList()
        if (rules.isEmpty()) throw RuntimeFailure("network.permission_denied", "网络调用没有获批目标")
        return Authorization(rules)
    }

    private fun addressScope(address: InetAddress): String {
        if (address.isLoopbackAddress) return "loopback"
        if (address.isSiteLocalAddress || address.isLinkLocalAddress || isUniqueLocalV6(address)) return "lan"
        if (!address.isAnyLocalAddress && !address.isMulticastAddress) return "public"
        throw RuntimeFailure("network.address_scope_denied", "目标解析到不可路由或保留地址")
    }

    private fun isUniqueLocalV6(address: InetAddress): Boolean =
        address is Inet6Address && address.address.isNotEmpty() && (address.address[0].toInt() and 0xfe) == 0xfc

    private fun normalizeHost(value: String): String = try {
        IDN.toASCII(value.trimEnd('.'), IDN.USE_STD3_ASCII_RULES).lowercase(Locale.ROOT)
    } catch (error: Exception) {
        throw RuntimeFailure("network.url_invalid", "URL 主机名无效", cause = error)
    }

    private fun duration(value: Any?, fallback: Long): Long {
        val raw = if (value == null) fallback else if (value is Map<*, *> && value["kind"] == "duration") value["milliseconds"] else value
        val result = (raw as? Number)?.toDouble()
            ?: throw RuntimeFailure("network.timeout_invalid", "网络超时必须是持续时间")
        if (!result.isFinite() || result <= 0.0 || result > 86_400_000.0) throw RuntimeFailure("network.timeout_invalid", "网络超时必须大于 0 且不超过 24 小时")
        return result.toLong()
    }

    private fun boundedLong(value: Any?, fallback: Long, minimum: Long, maximum: Long, errorId: String): Long {
        val raw = value ?: fallback
        if (raw is Boolean || raw !is Number || raw.toDouble() % 1.0 != 0.0) throw RuntimeFailure(errorId, "数值必须位于 $minimum 到 $maximum 之间")
        val result = raw.toLong()
        if (result !in minimum..maximum) throw RuntimeFailure(errorId, "数值必须位于 $minimum 到 $maximum 之间")
        return result
    }

    private fun argument(arguments: Map<String, Any?>, fid: String, name: String): Any? =
        arguments["$fid.parameter.$name"] ?: arguments.entries.firstOrNull { it.key.endsWith(".parameter.$name") }?.value

    private fun record(owner: String, vararg fields: Pair<String, Any?>): Map<String, Any?> = linkedMapOf<String, Any?>("record_type" to owner).apply {
        fields.forEach { (name, value) -> put("$owner.field.$name", value) }
    }

    private fun recordField(value: Map<String, Any?>, owner: String, name: String): Any? =
        value["$owner.field.$name"] ?: value[name]

    private fun stringMap(value: Any?): Map<String, Any?>? = (value as? Map<*, *>)?.entries?.associate { it.key.toString() to it.value }
    private fun stringSet(value: Any?): Set<String> = (value as? List<*>)?.map { it.toString() }?.toSet().orEmpty()
    private fun checkStopped() { if (control.isStopped()) throw RuntimeStoppedSignal }
    private fun timeout(message: String) = RuntimeFailure("network.timeout", message, true)

    private fun mapTransport(error: Exception, fallbackId: String = "network.transfer_failed", fallbackMessage: String = "网络传输失败"): RuntimeFailure {
        if (control.isStopped()) throw RuntimeStoppedSignal
        return when (error) {
            is java.net.SocketTimeoutException, is InterruptedIOException -> RuntimeFailure("network.timeout", "网络请求超时", true, error)
            is SSLException -> RuntimeFailure("network.tls_failed", "TLS 或主机名验证失败", cause = error)
            is UnknownHostException -> RuntimeFailure("network.dns_failed", "无法解析网络目标", true, error)
            is java.net.ConnectException, is java.net.NoRouteToHostException -> RuntimeFailure("network.unreachable", "无法连接网络目标", true, error)
            else -> RuntimeFailure(fallbackId, fallbackMessage, true, error)
        }
    }

    private fun redactedUrl(raw: String): String = try {
        val url = parseUrl(raw)
        val defaultPort = if (url.scheme == "https") 443 else 80
        val port = if (url.port == defaultPort) "" else ":${url.port}"
        "${url.scheme}://${url.host}$port${url.encodedPath.ifBlank { "/" }}"
    } catch (_: Exception) { "<invalid>" }

    private data class PairValue(val name: String, val value: String, val sensitive: Boolean)
    private data class Rule(val schemes: Set<String>, val hosts: Set<String>, val ports: Set<Int>, val scopes: Set<String>)
    private data class Authorization(val rules: List<Rule>)
    private data class AuthorizedUrl(val url: HttpUrl, val host: String, val origin: String, val addresses: List<InetAddress>, val scopes: Set<String>)
    private data class Shared(val url: String, val headers: List<PairValue>, val redirect: String, val timeoutMs: Long, val responseLimit: Long, val maxRedirects: Int)
    private sealed interface UploadField {
        data class Text(val name: String, val value: String, val contentType: String) : UploadField
        data class File(val name: String, val filename: String, val contentType: String, val source: AndroidReadableFile, val maximum: Long) : UploadField
    }

    private class PinnedDns(private val expectedHost: String, private val addresses: List<InetAddress>) : Dns {
        override fun lookup(hostname: String): List<InetAddress> {
            if (!hostname.equals(expectedHost, true)) throw UnknownHostException("unapproved host")
            return addresses
        }
    }

    private class StreamingFileBody(
        private val source: AndroidReadableFile,
        private val maximum: Long,
        private val control: RuntimeControl,
        contentType: String,
    ) : RequestBody() {
        private val type = contentType.toMediaTypeOrNull()
        override fun contentType() = type
        override fun contentLength(): Long = source.declaredSize ?: -1L
        override fun writeTo(sink: BufferedSink) {
            var written = 0L
            source.open().use { input ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    if (control.isStopped()) throw InterruptedIOException("cancelled")
                    val count = input.read(buffer)
                    if (count < 0) break
                    written += count
                    if (written > maximum) throw RuntimeFailure("network.upload_too_large", "上传文件超过允许大小")
                    sink.write(buffer, 0, count)
                }
            }
        }
    }

    companion object {
        private val SUPPORTED = setOf("network.request", "network.upload_file", "network.download_file")
        private val METHODS = setOf("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE")
        private val REDIRECTS = setOf(301, 302, 303, 307, 308)
        private val SCOPES = setOf("loopback", "lan", "public")
        private val MANAGED_HEADERS = setOf("host", "content-length", "transfer-encoding", "connection")
        private val SENSITIVE_HEADERS = setOf("authorization", "cookie", "proxy-authorization", "x-api-key", "api-key")
        private val CROSS_ORIGIN_STRIP = SENSITIVE_HEADERS + setOf("set-cookie")
        private val TEXT_MEDIA = setOf("application/json", "application/xml", "application/x-www-form-urlencoded", "application/javascript")
    }
}
