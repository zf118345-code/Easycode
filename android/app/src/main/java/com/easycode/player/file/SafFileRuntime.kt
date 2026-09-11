package com.easycode.player.file

import android.content.ContentResolver
import android.content.Context
import android.net.Uri
import android.os.Build
import android.system.Os
import android.provider.DocumentsContract
import com.easycode.player.runtime.RuntimeControl
import com.easycode.player.runtime.DangerousRunConfirmation
import com.easycode.player.runtime.RuntimeFailure
import com.easycode.player.util.AtomicFiles
import com.easycode.player.util.JsonSupport
import com.google.gson.JsonParser
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.InputStream
import java.nio.charset.Charset
import java.nio.charset.StandardCharsets
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.Locale
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

private fun isTreeUriCompat(uri: Uri): Boolean =
    uri.pathSegments.firstOrNull() == "tree"

internal data class AndroidReadableFile(
    val reference: Map<String, Any?>,
    val displayName: String,
    val declaredSize: Long?,
    val open: () -> InputStream,
)

internal class AndroidAtomicDownload internal constructor(
    val reference: Map<String, Any?>,
    val temporary: File,
    private val commitAction: () -> Unit,
) : AutoCloseable {
    fun commit() = commitAction()
    override fun close() {
        temporary.delete()
    }
}

internal data class DeferredSafChild(
    val name: String,
    val directory: Boolean,
    val uri: String,
)

internal data class DeferredSafResolution(
    val documentUri: String? = null,
    val pendingParentUri: String? = null,
    val pendingName: String? = null,
)

/** Resolve a deferred SAF child path one provider directory at a time.
 *
 * The pure value operation intentionally keeps only the authorized root URI
 * plus portable segments.  This function is the I/O-boundary resolver used by
 * the real ContentResolver path and by deterministic JVM fakes.
 */
internal fun resolveDeferredSafPath(
    rootDocumentUri: String,
    relativeSegments: List<String>,
    expectedKind: String,
    allowMissing: Boolean,
    listChildren: (String) -> List<DeferredSafChild>,
): DeferredSafResolution {
    var current = rootDocumentUri
    relativeSegments.forEachIndexed { index, segment ->
        val matches = listChildren(current).filter { it.name == segment }
        if (matches.size > 1) {
            throw RuntimeFailure("directory.boundary_unproven", "Provider 返回重复同名子项，无法唯一解析授权路径")
        }
        val child = matches.singleOrNull()
        val last = index == relativeSegments.lastIndex
        if (child == null) {
            if (last && allowMissing && expectedKind == "file_ref") {
                return DeferredSafResolution(pendingParentUri = current, pendingName = segment)
            }
            throw RuntimeFailure("file.not_found", "相对文件或目录不存在：$segment")
        }
        if (!last && !child.directory) {
            throw RuntimeFailure("directory.path_conflict", "相对位置包含同名文件：$segment")
        }
        if (last && expectedKind == "file_ref" && child.directory) {
            throw RuntimeFailure("file.type_conflict", "相对文件位置实际是目录：$segment")
        }
        if (last && expectedKind == "directory_ref" && !child.directory) {
            throw RuntimeFailure("directory.path_conflict", "相对目录位置实际是文件：$segment")
        }
        current = child.uri
    }
    return DeferredSafResolution(documentUri = current)
}

internal class SafFileRuntime(
    private val context: Context,
    private val dataRoot: File,
    private val control: RuntimeControl,
    private val profileRevision: Int,
    private val dangerousConfirmations: Set<DangerousRunConfirmation>,
    private val atomicReplace: (source: File, destination: File) -> Unit = { source, destination ->
        Os.rename(source.path, destination.path)
    },
) {
    private val resolver: ContentResolver get() = context.contentResolver

    fun execute(
        opcode: String,
        instructionId: String,
        arguments: Map<String, Any?>,
        contractFingerprint: String = "",
    ): Any? = when (opcode) {
        "file.exists" -> exists(file(arguments, "file", "read", allowMissing = true))
        "file.read_text" -> readText(file(arguments, "file", "read"), encoding(arguments))
        "file.write_text" -> writeText(file(arguments, "file", "write", allowMissing = true), text(arguments, "content"), encoding(arguments))
        "file.append_text" -> appendText(file(arguments, "file", "write", allowMissing = true), text(arguments, "content"), encoding(arguments))
        "file.replace_text" -> replaceText(
            file(arguments, "file", "write"),
            text(arguments, "search"),
            text(arguments, "replacement"),
            text(arguments, "scope", "all"),
            encoding(arguments),
        )
        "file.read_json" -> JsonSupport.toAny(JsonParser.parseString(readText(file(arguments, "file", "read"), StandardCharsets.UTF_8)))
        "file.write_json" -> {
            val content = JsonSupport.canonical(JsonSupport.fromAny(argument(arguments, "data"))) + "\n"
            writeText(file(arguments, "file", "write", allowMissing = true), content, StandardCharsets.UTF_8)
        }
        "file.delete" -> deleteFile(file(arguments, "file", "delete"))
        "file.copy" -> copyFile(
            file(arguments, "source", "read"),
            file(arguments, "destination", "write", allowMissing = true),
            text(arguments, "conflict", "error"),
        )
        "file.move" -> {
            val source = file(arguments, "source", "delete")
            val destination = file(arguments, "destination", "write", allowMissing = true)
            copyFile(source, destination, text(arguments, "conflict", "error"))
            if (!deleteFile(source)) throw RuntimeFailure("file.move_partial", "文件已复制但来源删除失败")
            destination.raw
        }
        "directory.exists" -> exists(directory(arguments, "directory", "read", allowMissing = true))
        "directory.create" -> createDirectory(
            directory(arguments, "parent", "create"),
            text(arguments, "relative_path"),
            text(arguments, "existing", "return_existing"),
        )
        "directory.list" -> listDirectory(
            directory(arguments, "directory", "list"),
            boolean(arguments, "recursive", false),
            argument(arguments, "filter"),
        )
        "directory.copy" -> copyDirectory(
            directory(arguments, "source", "read"),
            directory(arguments, "destination_parent", "create"),
            text(arguments, "name"),
            text(arguments, "conflict", "error"),
            move = false,
        )
        "directory.move" -> copyDirectory(
            directory(arguments, "source", "move"),
            directory(arguments, "destination_parent", "create"),
            text(arguments, "name"),
            text(arguments, "conflict", "error"),
            move = true,
        )
        "directory.delete" -> deleteEmpty(directory(arguments, "directory", "delete_empty"))
        "directory.delete_tree" -> deleteTree(
            directory(arguments, "directory", ""),
            instructionId,
            contractFingerprint,
        )
        else -> throw RuntimeFailure("file.operation_unsupported", "Android SAF 不支持指令：$opcode")
    }

    fun projectDataReference(): Map<String, Any?> = mapOf(
        "kind" to "directory_ref",
        "platform" to "android",
        "source" to "project_data",
        "display_name" to "项目数据目录",
        "private_path" to dataRoot.canonicalPath,
        "authorization_root_id" to "project-data:${JsonSupport.sha256(dataRoot.canonicalPath.toByteArray())}",
        "access" to listOf("read", "list", "create", "write", "delete_empty"),
    )

    fun writeBinary(value: Any?, content: ByteArray): Map<String, Any?> {
        if (content.size > 128 * 1024 * 1024) {
            throw RuntimeFailure("file.too_large", "单次二进制写入超过 128MB 限制")
        }
        var reference = resolveReference(
            Reference.from(value, dataRoot, "file_ref", "write"),
            "file_ref",
            allowMissing = true,
        )
        control.checkpoint()
        if (reference.privateFile != null) {
            AtomicFiles.write(reference.privateFile, content)
            return reference.raw
        }
        reference = materializePendingFile(reference)
        val uri = reference.uri ?: invalid("文件 URI 缺失")
        try {
            resolver.openOutputStream(uri, "wt")?.use { output ->
                output.write(content)
                output.flush()
            } ?: throw RuntimeFailure("file.write_failed", "文档提供者拒绝写入图片")
        } catch (error: RuntimeFailure) {
            throw error
        } catch (error: Exception) {
            throw RuntimeFailure("file.write_failed", "图片文件写入失败：${error.message}", true, error)
        }
        return reference.raw
    }

    /** Resolve and validate an upload source before any network connection is opened. */
    fun prepareNetworkUpload(value: Any?, maximumBytes: Long): AndroidReadableFile {
        val reference = resolveReference(
            Reference.from(value, dataRoot, "file_ref", "read"),
            "file_ref",
            allowMissing = false,
        )
        val privateFile = reference.privateFile
        val size = if (privateFile != null) privateFile.length() else {
            val uri = reference.uri ?: invalid("上传文件 URI 缺失")
            try {
                resolver.openAssetFileDescriptor(uri, "r")?.use { descriptor ->
                    descriptor.length.takeIf { it >= 0L }
                }
            } catch (error: Exception) {
                throw RuntimeFailure("file.read_failed", "上传文件不可读取：${error.message}", true, error)
            }
        }
        if (size != null && size > maximumBytes) {
            throw RuntimeFailure("network.upload_too_large", "上传文件超过允许大小")
        }
        val safUri = if (privateFile == null) reference.uri ?: invalid("上传文件 URI 缺失") else null
        val opener: () -> InputStream = if (privateFile != null) {
            { FileInputStream(privateFile) }
        } else {
            ({
                try {
                    resolver.openInputStream(safUri!!)
                        ?: throw RuntimeFailure("file.read_failed", "文档提供者拒绝读取上传文件")
                } catch (error: RuntimeFailure) {
                    throw error
                } catch (error: Exception) {
                    throw RuntimeFailure("file.read_failed", "上传文件不可读取：${error.message}", true, error)
                }
            })
        }
        return AndroidReadableFile(
            reference = reference.raw,
            displayName = reference.raw["display_name"]?.toString().orEmpty()
                .ifBlank { privateFile?.name ?: "upload" },
            declaredSize = size,
            open = opener,
        )
    }

    /**
     * Prepare a same-directory private temporary file before networking.
     *
     * A generic SAF document does not expose a portable atomic replace
     * transaction, so it is deliberately rejected before the request starts.
     */
    fun prepareNetworkDownload(value: Any?): AndroidAtomicDownload {
        val raw = (value as? Map<*, *>)?.entries?.associate { it.key.toString() to it.value }
            ?: throw RuntimeFailure("file.invalid_reference", "下载位置必须是强类型文件引用")
        if (raw["private_path"]?.toString().isNullOrBlank()) {
            throw RuntimeFailure(
                "file.atomic_commit_unsupported",
                "此 Android 文档提供者无法证明原子替换；未建立网络连接",
            )
        }
        val resolved = resolveReference(
            Reference.from(raw, dataRoot, "file_ref", "write"),
            "file_ref",
            allowMissing = true,
        )
        val destination = resolved.privateFile
            ?: throw RuntimeFailure(
                "file.atomic_commit_unsupported",
                "此 Android 文档提供者无法证明原子替换；未建立网络连接",
            )
        if (destination.exists() && destination.isDirectory) {
            throw RuntimeFailure("file.type_conflict", "下载目标实际是目录")
        }
        val parent = destination.parentFile
            ?: throw RuntimeFailure("file.atomic_commit_unsupported", "下载位置没有可用父目录")
        if (!parent.exists() && !parent.mkdirs()) {
            throw RuntimeFailure("file.atomic_commit_unsupported", "无法创建下载目标目录")
        }
        val temporary = try {
            File(parent, ".easycode-download-${UUID.randomUUID()}.tmp").also {
                if (!it.createNewFile()) throw IllegalStateException("temporary file exists")
            }
        } catch (error: Exception) {
            throw RuntimeFailure("file.atomic_commit_unsupported", "下载位置不支持受控临时文件", cause = error)
        }
        val canonicalDestination = destination.canonicalFile
        return AndroidAtomicDownload(raw, temporary) {
            val lock = downloadLocks.computeIfAbsent(canonicalDestination.path) { Any() }
            synchronized(lock) {
                control.checkpoint()
                val checked = resolveReference(
                    Reference.from(raw, dataRoot, "file_ref", "write"),
                    "file_ref",
                    allowMissing = true,
                ).privateFile?.canonicalFile
                    ?: throw RuntimeFailure("file.reference_changed", "下载目标引用在传输期间发生变化")
                if (checked != canonicalDestination) {
                    throw RuntimeFailure("file.reference_changed", "下载目标引用在传输期间发生变化")
                }
                try {
                    // POSIX rename within the same private directory is the
                    // Android atomic replacement primitive.
                    atomicReplace(temporary, canonicalDestination)
                } catch (error: Exception) {
                    throw RuntimeFailure("file.atomic_commit_failed", "下载文件原子提交失败", cause = error)
                }
            }
        }
    }

    private fun readText(reference: Reference, charset: Charset): String =
        readBytes(reference, 64L * 1024L * 1024L).toString(charset)

    private fun writeText(reference: Reference, content: String, charset: Charset) {
        val bytes = content.toByteArray(charset)
        if (bytes.size > 64 * 1024 * 1024) throw RuntimeFailure("file.too_large", "单次文本写入超过 64MB 限制")
        if (reference.privateFile != null) {
            AtomicFiles.write(reference.privateFile, bytes)
            return
        }
        // The file contract promises atomic replacement.  A bare SAF document
        // URI has no portable sibling-temp/rename transaction; truncating it
        // would falsely claim the contract.  Providers without that proof are
        // rejected before modifying the old content.
        throw RuntimeFailure(
            "file.atomic_write_unsupported",
            "此 SAF 文档提供者无法证明暂存后原子替换；旧文件保持不变",
        )
    }

    private fun appendText(reference: Reference, content: String, charset: Charset) {
        val bytes = content.toByteArray(charset)
        control.checkpoint()
        if (reference.privateFile != null) {
            reference.privateFile.parentFile?.mkdirs()
            reference.privateFile.appendBytes(bytes)
            return
        }
        val resolved = materializePendingFile(reference)
        val uri = resolved.uri ?: invalid("文件 URI 缺失")
        try {
            resolver.openOutputStream(uri, "wa")?.use { it.write(bytes) }
                ?: throw RuntimeFailure("file.write_failed", "文档提供者拒绝追加文件")
        } catch (error: RuntimeFailure) {
            throw error
        } catch (error: Exception) {
            throw RuntimeFailure("file.write_failed", "追加文件失败：${error.message}", true, error)
        }
    }

    private fun replaceText(
        reference: Reference,
        search: String,
        replacement: String,
        scope: String,
        charset: Charset,
    ): Long {
        if (search.isEmpty()) throw RuntimeFailure("file.search_empty", "替换查找内容不能为空")
        val original = readText(reference, charset)
        val count = if (scope in setOf("first", "one")) {
            if (search in original) 1 else 0
        } else {
            Regex.escape(search).toRegex().findAll(original).count()
        }
        val updated = if (scope in setOf("first", "one")) original.replaceFirst(search, replacement)
        else if (scope in setOf("all", "every")) original.replace(search, replacement)
        else throw RuntimeFailure("file.replace_scope_invalid", "替换范围必须是 first 或 all")
        if (count > 0) writeText(reference, updated, charset)
        return count.toLong()
    }

    private fun readBytes(reference: Reference, limit: Long): ByteArray {
        control.checkpoint()
        val stream = if (reference.privateFile != null) reference.privateFile.inputStream()
        else resolver.openInputStream(reference.uri ?: invalid("文件 URI 缺失"))
            ?: throw RuntimeFailure("file.read_failed", "文档提供者拒绝读取文件")
        return try {
            stream.use { input ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                var size = 0L
                while (true) {
                    control.checkpoint()
                    val read = input.read(buffer)
                    if (read < 0) break
                    size += read
                    if (size > limit) throw RuntimeFailure("file.too_large", "文件超过读取上限")
                    output.write(buffer, 0, read)
                }
                output.toByteArray()
            }
        } catch (error: RuntimeFailure) {
            throw error
        } catch (error: Exception) {
            throw RuntimeFailure("file.read_failed", "读取文件失败：${error.message}", true, error)
        }
    }

    private fun copyFile(source: Reference, destination: Reference, conflict: String): Map<String, Any?> {
        if (conflict !in setOf("error", "skip")) {
            throw RuntimeFailure("file.conflict_unsupported", "固定文件目标只支持 error 或 skip 冲突策略")
        }
        if (exists(destination)) {
            if (conflict == "skip") return destination.raw
            throw RuntimeFailure("file.exists", "目标文件已存在")
        }
        val bytes = readBytes(source, 512L * 1024L * 1024L)
        if (destination.privateFile != null) AtomicFiles.write(destination.privateFile, bytes)
        else {
            val uri = materializePendingFile(destination).uri ?: invalid("目标文件 URI 缺失")
            resolver.openOutputStream(uri, "w")?.use { it.write(bytes) }
                ?: throw RuntimeFailure("file.write_failed", "文档提供者拒绝写入目标文件")
        }
        return destination.raw
    }

    private fun deleteFile(reference: Reference): Boolean {
        control.checkpoint()
        if (reference.privateFile != null) return !reference.privateFile.exists() || reference.privateFile.delete()
        return runCatching { DocumentsContract.deleteDocument(resolver, reference.uri ?: invalid("文件 URI 缺失")) }
            .getOrElse { throw RuntimeFailure("file.delete_failed", "删除文件失败：${it.message}", true, it) }
    }

    private fun createDirectory(parent: Reference, relative: String, existing: String): Map<String, Any?> {
        val parts = relative.replace('\\', '/').split('/').filter(String::isNotBlank)
        if (parts.isEmpty() || parts.any { it in setOf(".", "..") || it.contains('\u0000') }) {
            throw RuntimeFailure("file.relative_path_invalid", "目录相对位置无效")
        }
        if (parent.privateFile != null) {
            var current = parent.privateFile
            for (part in parts) current = File(current, part)
            val existed = current.exists()
            if (existed && existing == "error") throw RuntimeFailure("directory.exists", "目标目录已存在")
            if (!existed && !current.mkdirs()) throw RuntimeFailure("directory.create_failed", "无法创建项目数据子目录")
            return derived(parent, current.toURI().toString(), current.name, current).raw
        }
        var current = parent.documentUri()
        for (part in parts) {
            control.checkpoint()
            val found = children(parent, current).firstOrNull { it.name == part }
            if (found != null) {
                if (!found.directory) throw RuntimeFailure("directory.path_conflict", "相对位置包含同名文件：$part")
                if (part == parts.last() && existing == "error") throw RuntimeFailure("directory.exists", "目标目录已存在")
                current = Uri.parse(found.uri)
            } else {
                current = DocumentsContract.createDocument(resolver, current, DocumentsContract.Document.MIME_TYPE_DIR, part)
                    ?: throw RuntimeFailure("directory.create_failed", "文档提供者拒绝创建目录：$part")
            }
        }
        return derived(parent, current.toString(), parts.last()).raw
    }

    private fun listDirectory(reference: Reference, recursive: Boolean, filter: Any?): List<Map<String, Any?>> {
        val filterMap = filter as? Map<*, *>
            ?: if (filter == null) emptyMap<Any?, Any?>() else throw RuntimeFailure(
                "directory.filter_invalid", "目录筛选必须是结构化值",
            )
        val patternValue = filterMap["filesystem_filter.field.pattern"] ?: filterMap["pattern"]
        val pattern = patternValue?.toString()?.takeIf { it.isNotEmpty() } ?: "*"
        val limitValue = filterMap["filesystem_filter.field.limit"] ?: filterMap["limit"]
        val limit = if (limitValue == null) 100_000 else exactPositiveInt(limitValue, "目录最大条数")
        if (limit !in 1..100_000) throw RuntimeFailure(
            "directory.filter_invalid", "目录最大条数必须是 1 至 100000 的整数",
        )
        val output = mutableListOf<Map<String, Any?>>()
        fun visit(directory: Reference, depth: Int) {
            if (depth > 64) throw RuntimeFailure("directory.limit", "目录枚举超过深度上限")
            val entries = if (directory.privateFile != null) {
                directory.privateFile.listFiles()?.sortedBy { it.name }?.map {
                    Child(it.name, it.isDirectory, it.length(), it.toURI().toString(), privateFile = it)
                }.orEmpty()
            } else children(directory, directory.documentUri())
            for (entry in entries) {
                control.checkpoint()
                if (globMatches(entry.name, pattern)) {
                    val child = derived(
                        directory,
                        entry.uri.toString(),
                        entry.name,
                        entry.privateFile,
                        kind = if (entry.directory) "directory_ref" else "file_ref",
                    ).raw
                    output += mapOf(
                        "filesystem_entry.field.name" to entry.name,
                        "filesystem_entry.field.entry_type" to if (entry.directory) "directory" else "file",
                        "filesystem_entry.field.size" to if (entry.directory) null else entry.size,
                        "filesystem_entry.field.file" to if (entry.directory) null else child,
                        "filesystem_entry.field.directory" to if (entry.directory) child else null,
                    )
                    if (output.size >= limit) return
                }
                if (recursive && entry.directory) visit(derived(directory, entry.uri.toString(), entry.name, entry.privateFile), depth + 1)
                if (output.size >= limit) return
            }
        }
        visit(reference, 0)
        return output
    }

    private fun exactPositiveInt(value: Any?, label: String): Int {
        val number = value as? Number ?: throw RuntimeFailure("directory.filter_invalid", "$label 必须是整数")
        val decimal = number.toDouble()
        if (!decimal.isFinite() || decimal % 1.0 != 0.0 || decimal < 1 || decimal > Int.MAX_VALUE) {
            throw RuntimeFailure("directory.filter_invalid", "$label 必须是正整数")
        }
        return decimal.toInt()
    }

    private fun globMatches(name: String, pattern: String): Boolean {
        val regex = StringBuilder("^")
        for (character in pattern) {
            when (character) {
                '*' -> regex.append(".*")
                '?' -> regex.append('.')
                else -> regex.append(Regex.escape(character.toString()))
            }
        }
        regex.append('$')
        return Regex(regex.toString()).matches(name)
    }

    private fun copyDirectory(
        source: Reference,
        destinationParent: Reference,
        requestedName: String,
        conflict: String,
        move: Boolean,
    ): Map<String, Any?> {
        if (conflict !in setOf("error", "skip", "auto_rename")) {
            throw RuntimeFailure("directory.conflict_invalid", "目录冲突策略无效")
        }
        if (move && "move" !in source.access) invalid("目录引用缺少 move 能力")
        var name = requestedName.trim()
        if (name.isBlank() || '/' in name || '\\' in name || name in setOf(".", "..")) {
            throw RuntimeFailure("file.relative_path_invalid", "目标目录名称无效")
        }
        val existingNames = listDirectory(destinationParent, false, null)
            .map { it["filesystem_entry.field.name"].toString() }
            .toSet()
        if (name in existingNames) {
            if (conflict == "skip") return treeOperationReport(0, 0, listOf(name), emptyList(), true, null)
            if (conflict == "error") throw RuntimeFailure("directory.exists", "目标目录已存在")
            val base = name
            var index = 2
            while (name in existingNames) name = "$base ($index)".also { index++ }
        }
        if (move) return movePrivateDirectory(source, destinationParent, name)
        val targetRaw = createDirectory(destinationParent, name, "error")
        val target = Reference.from(targetRaw, dataRoot, "directory_ref", "create")
        var files = 0
        var directories = 1
        val failures = mutableListOf<String>()
        fun copyTree(from: Reference, to: Reference, depth: Int) {
            if (depth > 64 || files + directories > 100_000) throw RuntimeFailure("directory.limit", "目录树超过安全上限")
            val entries = listChildren(from)
            for (entry in entries) {
                control.checkpoint()
                try {
                    if (entry.directory) {
                        val nextRaw = createDirectory(to, entry.name, "error")
                        directories++
                        copyTree(derived(from, entry.uri.toString(), entry.name, entry.privateFile), Reference.from(nextRaw, dataRoot, "directory_ref", "create"), depth + 1)
                    } else {
                        val destination = createFile(to, entry.name)
                        copyFile(
                            derived(from, entry.uri.toString(), entry.name, entry.privateFile, kind = "file_ref"),
                            destination,
                            "error",
                        )
                        files++
                    }
                } catch (error: Exception) {
                    failures += "${entry.name}: ${error.message}"
                    break
                }
            }
        }
        copyTree(source, target, 0)
        return treeOperationReport(files, directories, emptyList(), failures, failures.isEmpty(), target.raw)
    }

    private fun movePrivateDirectory(
        source: Reference,
        destinationParent: Reference,
        name: String,
    ): Map<String, Any?> {
        val from = source.privateFile?.canonicalFile
        val parent = destinationParent.privateFile?.canonicalFile
        if (from == null || parent == null) {
            throw RuntimeFailure(
                "directory.move_unsupported",
                "SAF Provider 引用缺少可证明的来源父目录，未创建或删除任何项目",
            )
        }
        val protectedRoot = dataRoot.canonicalFile
        if (
            from == protectedRoot || protectedRoot !in ancestors(from) ||
            (parent != protectedRoot && protectedRoot !in ancestors(parent))
        ) {
            throw RuntimeFailure("directory.protected_root", "Player 数据根或授权树外目录不能移动")
        }
        val target = File(parent, name).canonicalFile
        if (target.exists()) throw RuntimeFailure("directory.exists", "目标目录已存在")
        if (from == target || from in ancestors(target)) {
            throw RuntimeFailure("directory.boundary_escape", "目录不能移动到自身后代")
        }
        var files = 0
        var directories = 0
        fun preflight(current: File, depth: Int) {
            if (depth > 64 || files + directories > 100_000) {
                throw RuntimeFailure("directory.limit", "目录树超过安全上限；尚未移动")
            }
            control.checkpoint()
            if (Files.isSymbolicLink(current.toPath())) {
                throw RuntimeFailure("directory.boundary_unproven", "目录树包含符号链接；尚未移动")
            }
            val canonical = current.canonicalFile
            if (canonical != from && from !in ancestors(canonical)) {
                throw RuntimeFailure("directory.boundary_escape", "目录后代越出来源树；尚未移动")
            }
            if (canonical.isDirectory) {
                directories++
                val children = canonical.listFiles()
                    ?: throw RuntimeFailure("directory.list_failed", "移动前无法枚举全部后代；尚未移动")
                children.sortedBy { it.name }.forEach { preflight(it, depth + 1) }
            } else {
                files++
            }
        }
        preflight(from, 0)
        try {
            Files.move(from.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE)
        } catch (_: AtomicMoveNotSupportedException) {
            try {
                Files.move(from.toPath(), target.toPath())
            } catch (error: Exception) {
                throw RuntimeFailure("directory.move_failed", "目录移动失败：${error.message}", cause = error)
            }
        } catch (error: Exception) {
            throw RuntimeFailure("directory.move_failed", "目录移动失败：${error.message}", cause = error)
        }
        return treeOperationReport(
            files, directories, emptyList(), emptyList(), true,
            derived(destinationParent, target.toURI().toString(), name, target).raw,
        )
    }

    private fun deleteEmpty(reference: Reference): Boolean {
        if (listChildren(reference).isNotEmpty()) throw RuntimeFailure("directory.not_empty", "目录非空，不能使用普通删除")
        if (reference.privateFile != null) return reference.privateFile.delete()
        return DocumentsContract.deleteDocument(resolver, reference.documentUri())
    }

    private fun deleteTree(
        reference: Reference,
        instructionId: String,
        contractFingerprint: String,
    ): Map<String, Any?> {
        if ("delete_tree" !in reference.access) {
            throw RuntimeFailure(
                "directory.delete_tree_not_authorized",
                "普通 SAF 目录授权不包含递归删除危险能力；未删除任何项目",
            )
        }
        val confirmed = dangerousConfirmations.any {
            it.statementId == instructionId &&
                it.authorizationRootId == reference.authorizationRootId &&
                it.profileRevision == profileRevision &&
                it.contractFingerprint == contractFingerprint &&
                contractFingerprint.isNotBlank()
        }
        if (!confirmed) {
            throw RuntimeFailure(
                "directory.confirmation_required",
                "递归删除缺少绑定当前调用、授权根和方案 revision 的当次执行确认；未删除任何项目",
            )
        }
        if (reference.privateFile != null) return deletePrivateTree(reference)
        return deleteSafTree(reference)
    }

    private fun deleteSafTree(reference: Reference): Map<String, Any?> {
        val root = reference.documentUri()
        val files = mutableListOf<Child>()
        val directories = mutableListOf<Child>()
        val seen = mutableSetOf(root.toString())

        fun requireDelete(uri: Uri, flags: Int) {
            if (flags and DocumentsContract.Document.FLAG_SUPPORTS_DELETE == 0) {
                throw RuntimeFailure(
                    "directory.provider_proof_unavailable",
                    "文档提供者未声明全部目标支持删除；未删除任何项目",
                )
            }
            if (uri.authority != root.authority) {
                throw RuntimeFailure("directory.boundary_escape", "Provider 子项越出授权 authority；未删除任何项目")
            }
        }

        fun preflight(directory: Reference, depth: Int) {
            if (depth > 64 || files.size + directories.size > 100_000) {
                throw RuntimeFailure("directory.limit", "递归删除目录树超过安全上限；未删除任何项目")
            }
            for (child in children(directory, directory.documentUri())) {
                control.checkpoint()
                val uri = Uri.parse(child.uri)
                if (!seen.add(child.uri)) {
                    throw RuntimeFailure("directory.boundary_unproven", "Provider 返回重复或循环子项；未删除任何项目")
                }
                if (Build.VERSION.SDK_INT < 29) {
                    throw RuntimeFailure(
                        "directory.provider_proof_unavailable",
                        "Android 10 以下无法通过公开 API 证明 Provider 子项仍在授权根内；未删除任何项目",
                    )
                }
                val contained = try {
                    DocumentsContract.isChildDocument(resolver, root, uri)
                } catch (error: Exception) {
                    throw RuntimeFailure(
                        "directory.provider_proof_unavailable",
                        "Provider 无法证明后代仍在授权根内；未删除任何项目",
                        cause = error,
                    )
                }
                if (!contained) {
                    throw RuntimeFailure("directory.boundary_escape", "Provider 子项不属于已确认授权根；未删除任何项目")
                }
                requireDelete(uri, child.flags)
                if (child.directory) {
                    preflight(derived(directory, child.uri, child.name), depth + 1)
                    directories += child
                } else {
                    files += child
                }
            }
        }

        requireDelete(root, documentFlags(root))
        preflight(reference, 0)
        var deletedFiles = 0
        var deletedDirectories = 0
        val failures = mutableListOf<String>()
        fun delete(child: Child): Boolean = try {
            if (DocumentsContract.deleteDocument(resolver, Uri.parse(child.uri))) true
            else {
                failures += child.name
                false
            }
        } catch (error: Exception) {
            failures += "${child.name}: ${error.message ?: error.javaClass.simpleName}"
            false
        }
        for (child in files) {
            control.checkpoint()
            if (!delete(child)) break
            deletedFiles++
        }
        if (failures.isEmpty()) {
            // Directories were appended after their descendants during the
            // complete preflight, so this order is already leaf-to-root.
            for (child in directories) {
                control.checkpoint()
                if (!delete(child)) break
                deletedDirectories++
            }
        }
        if (failures.isEmpty()) {
            val rootChild = Child(
                name = reference.raw["display_name"]?.toString().orEmpty().ifBlank { "授权根" },
                directory = true,
                size = 0L,
                uri = root.toString(),
                flags = DocumentsContract.Document.FLAG_SUPPORTS_DELETE,
            )
            if (delete(rootChild)) deletedDirectories++
        }
        return treeDeleteReport(
            deletedFiles,
            deletedDirectories,
            emptyList(),
            failures,
            complete = failures.isEmpty(),
        )
    }

    private fun documentFlags(uri: Uri): Int = try {
        resolver.query(
            uri,
            arrayOf(DocumentsContract.Document.COLUMN_FLAGS),
            null,
            null,
            null,
        )?.use { cursor ->
            if (!cursor.moveToFirst()) null else cursor.getInt(0)
        } ?: throw RuntimeFailure(
            "directory.provider_proof_unavailable",
            "Provider 无法报告删除能力；未删除任何项目",
        )
    } catch (error: RuntimeFailure) {
        throw error
    } catch (error: Exception) {
        throw RuntimeFailure(
            "directory.provider_proof_unavailable",
            "Provider 无法报告删除能力；未删除任何项目",
            cause = error,
        )
    }

    private fun deletePrivateTree(reference: Reference): Map<String, Any?> {
        val protectedRoot = dataRoot.canonicalFile
        val target = reference.privateFile?.canonicalFile
            ?: throw RuntimeFailure("file.invalid_reference", "项目私有目录引用缺少路径")
        if (target == protectedRoot || protectedRoot !in ancestors(target)) {
            throw RuntimeFailure(
                "directory.protected_root",
                "Player 数据根或授权树外目录不能递归删除；未删除任何项目",
            )
        }
        val files = mutableListOf<File>()
        val directories = mutableListOf<File>()
        fun preflight(current: File, depth: Int) {
            if (depth > 64 || files.size + directories.size > 100_000) {
                throw RuntimeFailure("directory.limit", "递归删除目录树超过安全上限；未删除任何项目")
            }
            control.checkpoint()
            if (Files.isSymbolicLink(current.toPath())) {
                throw RuntimeFailure(
                    "directory.boundary_unproven",
                    "递归删除目录树包含符号链接，无法证明边界；未删除任何项目",
                )
            }
            val canonical = current.canonicalFile
            if (canonical != target && target !in ancestors(canonical)) {
                throw RuntimeFailure(
                    "directory.boundary_escape",
                    "递归删除后代越出已确认授权树；未删除任何项目",
                )
            }
            if (canonical.isDirectory) {
                val children = canonical.listFiles()
                    ?: throw RuntimeFailure("directory.list_failed", "无法在删除前枚举全部后代；未删除任何项目")
                children.sortedBy { it.name }.forEach { preflight(it, depth + 1) }
                directories += canonical
            } else {
                files += canonical
            }
        }
        preflight(target, 0)
        var deletedFiles = 0
        var deletedDirectories = 0
        val failures = mutableListOf<String>()
        for (item in files) {
            control.checkpoint()
            if (!item.delete()) {
                failures += item.name
                break
            }
            deletedFiles++
        }
        if (failures.isEmpty()) {
            for (item in directories) {
                control.checkpoint()
                if (!item.delete()) {
                    failures += item.name
                    break
                }
                deletedDirectories++
            }
        }
        return treeDeleteReport(
            deletedFiles,
            deletedDirectories,
            emptyList(),
            failures,
            complete = failures.isEmpty(),
        )
    }

    private fun ancestors(file: File): Set<File> =
        generateSequence(file.parentFile) { it.parentFile }.map { it.canonicalFile }.toSet()

    private fun listChildren(reference: Reference): List<Child> = if (reference.privateFile != null) {
        reference.privateFile.listFiles()?.map {
            Child(it.name, it.isDirectory, it.length(), it.toURI().toString(), privateFile = it)
        }.orEmpty()
    } else children(reference, reference.documentUri())

    private fun createFile(parent: Reference, name: String): Reference {
        if (parent.privateFile != null) {
            val target = File(parent.privateFile, name)
            val access = setOf("read", "write", "delete")
            return Reference(
                raw = mapOf(
                    "kind" to "file_ref", "platform" to "android", "source" to "derived",
                    "display_name" to name, "uri" to target.toURI().toString(),
                    "private_path" to target.canonicalPath,
                    "authorization_root_id" to parent.authorizationRootId,
                    "access" to access.sorted(),
                ),
                uri = null,
                privateFile = target,
                access = access,
                authorizationRootId = parent.authorizationRootId,
            )
        }
        val uri = DocumentsContract.createDocument(resolver, parent.documentUri(), "application/octet-stream", name)
            ?: throw RuntimeFailure("file.create_failed", "文档提供者拒绝创建文件：$name")
        val access = setOf("read", "write", "delete")
        return Reference(
            raw = mapOf(
                "kind" to "file_ref", "platform" to "android", "source" to "derived",
                "display_name" to name, "uri" to uri.toString(),
                "authorization_root_id" to parent.authorizationRootId,
                "access" to access.sorted(),
            ),
            uri = uri,
            privateFile = null,
            access = access,
            authorizationRootId = parent.authorizationRootId,
            treeUri = parent.treeUri ?: parent.uri,
        )
    }

    private fun materializePendingFile(reference: Reference): Reference {
        if (reference.pendingName == null) return reference
        val parent = reference.pendingParentUri
            ?: throw RuntimeFailure("file.invalid_reference", "延迟文件引用缺少父目录 URI")
        val uri = DocumentsContract.createDocument(
            resolver,
            parent,
            "application/octet-stream",
            reference.pendingName,
        ) ?: throw RuntimeFailure("file.create_failed", "文档提供者拒绝创建文件：${reference.pendingName}")
        return reference.copy(uri = uri, pendingParentUri = null, pendingName = null)
    }

    private fun children(reference: Reference, directoryDocument: Uri): List<Child> {
        val tree = reference.treeUri ?: reference.uri ?: invalid("SAF 目录 URI 缺失")
        if (!isTreeUriCompat(tree)) invalid("目录引用必须来自 SAF 文档树")
        val documentId = DocumentsContract.getDocumentId(directoryDocument)
        val childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(tree, documentId)
        val projection = arrayOf(
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE,
            DocumentsContract.Document.COLUMN_SIZE,
            DocumentsContract.Document.COLUMN_FLAGS,
        )
        return try {
            resolver.query(childrenUri, projection, null, null, null)?.use { cursor ->
                buildList {
                    while (cursor.moveToNext()) {
                        control.checkpoint()
                        val childId = cursor.getString(0) ?: invalid("Provider 返回空 document_id")
                        val childUri = DocumentsContract.buildDocumentUriUsingTree(tree, childId)
                        if (childUri.authority != tree.authority) invalid("Provider 子项越出授权 authority")
                        add(Child(
                            name = cursor.getString(1).orEmpty(),
                            directory = cursor.getString(2) == DocumentsContract.Document.MIME_TYPE_DIR,
                            size = if (cursor.isNull(3)) 0L else cursor.getLong(3),
                            uri = childUri.toString(),
                            flags = if (cursor.isNull(4)) 0 else cursor.getInt(4),
                        ))
                    }
                }
            } ?: throw RuntimeFailure("directory.list_failed", "文档提供者拒绝枚举目录")
        } catch (error: RuntimeFailure) {
            throw error
        } catch (error: Exception) {
            throw RuntimeFailure("directory.list_failed", "枚举 SAF 目录失败：${error.message}", true, error)
        }
    }

    private fun exists(reference: Reference): Boolean {
        return try {
            if (reference.pendingName != null) return false
            if (reference.privateFile != null) reference.privateFile.exists()
            else resolver.query(reference.documentUri(), arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID), null, null, null)
                ?.use { it.moveToFirst() } == true
        } catch (_: Exception) {
            false
        }
    }

    private fun derived(
        parent: Reference,
        uri: String,
        name: String,
        privateFile: File? = null,
        kind: String = "directory_ref",
    ): Reference {
        val narrowed = parent.access.filterTo(mutableSetOf()) { permission ->
            if (kind == "file_ref") permission in setOf("read", "write", "delete")
            else permission != "delete_tree"
        }
        val raw = mapOf(
            "kind" to kind,
            "platform" to "android",
            "source" to "derived",
            "display_name" to name,
            "uri" to uri,
            "private_path" to privateFile?.canonicalPath,
            "authorization_root_id" to parent.authorizationRootId,
            "access" to narrowed.sorted(),
        ).filterValues { it != null }
        return Reference(
            raw,
            Uri.parse(uri).takeIf { privateFile == null },
            privateFile,
            narrowed,
            parent.authorizationRootId,
            treeUri = if (privateFile == null) parent.treeUri ?: parent.uri else null,
        )
    }

    private fun file(arguments: Map<String, Any?>, suffix: String, access: String, allowMissing: Boolean = false): Reference =
        resolveReference(
            Reference.from(argument(arguments, suffix), dataRoot, "file_ref", access),
            "file_ref",
            allowMissing,
        )

    private fun directory(arguments: Map<String, Any?>, suffix: String, access: String, allowMissing: Boolean = false): Reference =
        resolveReference(
            Reference.from(argument(arguments, suffix), dataRoot, "directory_ref", access),
            "directory_ref",
            allowMissing,
        )

    private fun resolveReference(reference: Reference, expectedKind: String, allowMissing: Boolean): Reference {
        val segments = reference.relativeSegments
        if (reference.privateFile != null) {
            val base = reference.privateFile.canonicalFile
            var current = base
            if (segments.isNotEmpty()) {
                if (!base.exists()) throw RuntimeFailure("file.not_found", "项目私有授权根不存在")
                if (!base.isDirectory) throw RuntimeFailure("directory.path_conflict", "相对位置的授权根不是目录")
                for ((index, segment) in segments.withIndex()) {
                    control.checkpoint()
                    val child = File(current, segment).canonicalFile
                    if (child != base && base !in ancestors(child)) {
                        throw RuntimeFailure("file.path_escape", "项目私有相对位置越出授权根")
                    }
                    val last = index == segments.lastIndex
                    if (!last) {
                        if (!child.exists()) throw RuntimeFailure("file.not_found", "相对目录不存在：$segment")
                        if (!child.isDirectory) {
                            throw RuntimeFailure("directory.path_conflict", "相对位置包含同名文件：$segment")
                        }
                    }
                    current = child
                }
            }
            validateResolvedKind(current, expectedKind, allowMissing)
            return reference.copy(privateFile = current, relativeSegments = emptyList())
        }
        if (segments.isEmpty()) return reference
        val rootDocument = reference.documentUri()
        val resolution = resolveDeferredSafPath(
            rootDocument.toString(),
            segments,
            expectedKind,
            allowMissing,
        ) { directoryUri ->
            children(reference, Uri.parse(directoryUri)).map {
                DeferredSafChild(it.name, it.directory, it.uri)
            }
        }
        return reference.copy(
            uri = resolution.documentUri?.let(Uri::parse),
            treeUri = reference.treeUri ?: reference.uri,
            relativeSegments = emptyList(),
            pendingParentUri = resolution.pendingParentUri?.let(Uri::parse),
            pendingName = resolution.pendingName,
        )
    }

    private fun validateResolvedKind(file: File, expectedKind: String, allowMissing: Boolean) {
        if (!file.exists()) {
            if (allowMissing) return
            throw RuntimeFailure("file.not_found", "项目私有文件或目录不存在")
        }
        if (expectedKind == "file_ref" && file.isDirectory) {
            throw RuntimeFailure("file.type_conflict", "文件引用实际指向目录")
        }
        if (expectedKind == "directory_ref" && !file.isDirectory) {
            throw RuntimeFailure("directory.path_conflict", "目录引用实际指向文件")
        }
    }

    private fun argument(arguments: Map<String, Any?>, suffix: String): Any? =
        arguments.entries.firstOrNull { it.key.endsWith(".parameter.$suffix") }?.value

    private fun text(arguments: Map<String, Any?>, suffix: String, default: String = ""): String =
        argument(arguments, suffix)?.toString() ?: default

    private fun boolean(arguments: Map<String, Any?>, suffix: String, default: Boolean): Boolean =
        argument(arguments, suffix) as? Boolean ?: default

    private fun encoding(arguments: Map<String, Any?>): Charset = when (text(arguments, "encoding", "utf-8").lowercase()) {
        "utf-8", "utf8" -> StandardCharsets.UTF_8
        "utf-16", "utf16" -> StandardCharsets.UTF_16
        "utf-16le", "utf16le" -> StandardCharsets.UTF_16LE
        "utf-16be", "utf16be" -> StandardCharsets.UTF_16BE
        else -> throw RuntimeFailure("file.encoding_invalid", "Android Runtime 不支持此文本编码")
    }

    private fun treeOperationReport(
        files: Int,
        directories: Int,
        skipped: List<String>,
        failures: List<String>,
        complete: Boolean,
        destination: Map<String, Any?>?,
    ): Map<String, Any?> = mapOf(
        "tree_operation_report.field.processed_files" to files,
        "tree_operation_report.field.processed_directories" to directories,
        "tree_operation_report.field.skipped" to skipped,
        "tree_operation_report.field.failures" to failures,
        "tree_operation_report.field.complete" to complete,
        "tree_operation_report.field.destination" to destination,
    )

    private fun treeDeleteReport(
        files: Int,
        directories: Int,
        @Suppress("UNUSED_PARAMETER") skipped: List<String>,
        failures: List<String>,
        complete: Boolean,
    ): Map<String, Any?> = mapOf(
        "tree_delete_report.field.files_deleted" to files,
        "tree_delete_report.field.directories_deleted" to directories,
        "tree_delete_report.field.failures" to failures,
        "tree_delete_report.field.complete" to complete,
    )

    private fun invalid(message: String): Nothing = throw RuntimeFailure("file.invalid_reference", message)

    private data class Child(
        val name: String,
        val directory: Boolean,
        val size: Long,
        val uri: String,
        val privateFile: File? = null,
        val flags: Int = DocumentsContract.Document.FLAG_SUPPORTS_DELETE,
    )

    private data class Reference(
        val raw: Map<String, Any?>,
        val uri: Uri?,
        val privateFile: File?,
        val access: Set<String>,
        val authorizationRootId: String,
        val treeUri: Uri? = null,
        val relativeSegments: List<String> = emptyList(),
        val pendingParentUri: Uri? = null,
        val pendingName: String? = null,
    ) {
        fun documentUri(): Uri {
            val original = uri ?: return privateFile?.toURI()?.toString()?.let(Uri::parse)
                ?: throw RuntimeFailure("file.invalid_reference", "引用缺少 URI")
            return if ("document" !in original.pathSegments && isTreeUriCompat(original)) {
                DocumentsContract.buildDocumentUriUsingTree(original, DocumentsContract.getTreeDocumentId(original))
            } else original
        }

        companion object {
            fun from(
                value: Any?,
                dataRoot: File,
                expectedKind: String,
                requiredAccess: String,
            ): Reference {
                val raw = (value as? Map<*, *>)?.entries?.associate { it.key.toString() to it.value }
                    ?: throw RuntimeFailure("file.invalid_reference", "文件/目录参数必须是强类型引用")
                if (raw["kind"] != expectedKind || raw["platform"] != "android") {
                    throw RuntimeFailure("file.invalid_reference", "文件/目录引用类型或平台无效")
                }
                val access = (raw["access"] as? List<*>)?.mapTo(mutableSetOf()) { it.toString() }.orEmpty()
                if (requiredAccess.isNotBlank() && requiredAccess !in access) {
                    throw RuntimeFailure("file.permission_denied", "引用缺少 $requiredAccess 能力")
                }
                val rootId = raw["authorization_root_id"]?.toString().orEmpty()
                if (rootId.isBlank()) throw RuntimeFailure("file.invalid_reference", "引用缺少 authorization_root_id")
                val segments = validatedDeferredSegments(raw["relative_segments"])
                val privatePath = raw["private_path"]?.toString().orEmpty()
                if (privatePath.isNotBlank()) {
                    val root = dataRoot.canonicalFile
                    val file = File(privatePath).canonicalFile
                    if (file != root && root !in generateSequence(file.parentFile) { it.parentFile }.toSet()) {
                        throw RuntimeFailure("file.path_escape", "项目私有引用越出数据根")
                    }
                    return Reference(raw, null, file, access, rootId, relativeSegments = segments)
                }
                val uri = runCatching { Uri.parse(raw["uri"]?.toString().orEmpty()) }.getOrNull()
                    ?: throw RuntimeFailure("file.invalid_reference", "SAF 引用 URI 无效")
                if (uri.scheme != ContentResolver.SCHEME_CONTENT) {
                    throw RuntimeFailure("file.invalid_reference", "外部 Android 引用必须使用 content://")
                }
                return Reference(raw, uri, null, access, rootId, treeUri = uri, relativeSegments = segments)
            }

            private fun validatedDeferredSegments(value: Any?): List<String> {
                if (value == null) return emptyList()
                val raw = value as? List<*>
                    ?: throw RuntimeFailure("file.relative_path_invalid", "延迟相对位置必须是分段列表")
                if (raw.size > 128) {
                    throw RuntimeFailure("file.relative_path_invalid", "相对位置层级无效或超过 128 层")
                }
                val segments = raw.map {
                    it as? String
                        ?: throw RuntimeFailure("file.relative_path_invalid", "延迟相对位置段必须是文本")
                }
                if (segments.isNotEmpty() && segments.joinToString("/").toByteArray(StandardCharsets.UTF_8).size > 4096) {
                    throw RuntimeFailure("file.relative_path_invalid", "相对位置不能为空或超过 4096 字节")
                }
                val reservedNames = setOf("CON", "PRN", "AUX", "NUL") +
                    (1..9).flatMap { listOf("COM$it", "LPT$it") }
                val forbidden = setOf('<', '>', ':', '"', '\\', '|', '?', '*', '/')
                for (segment in segments) {
                    val invalid = segment.isEmpty() ||
                        segment in setOf(".", "..") ||
                        segment.lastOrNull() in setOf(' ', '.') ||
                        segment.toByteArray(StandardCharsets.UTF_8).size > 255 ||
                        segment.any { it.code < 32 || it.code == 127 } ||
                        segment.any { it in forbidden } ||
                        segment.substringBefore('.').uppercase(Locale.ROOT) in reservedNames
                    if (invalid) {
                        throw RuntimeFailure("file.relative_path_invalid", "延迟相对位置包含不安全名称")
                    }
                }
                return segments
            }
        }
    }

    companion object {
        private val downloadLocks = ConcurrentHashMap<String, Any>()
    }
}
