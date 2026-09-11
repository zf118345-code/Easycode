package com.easycode.player.capture

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import com.easycode.player.bundle.BundleVerificationException
import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.profile.ProfileStore
import com.easycode.player.runtime.RuntimeControl
import com.easycode.player.runtime.RuntimeFailure
import com.easycode.player.file.SafFileRuntime
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.TextRecognizer
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import java.time.Instant
import java.io.ByteArrayOutputStream
import java.util.concurrent.TimeUnit
import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

class AndroidVisionHost(
    private val bundle: VerifiedBundle,
    private val profiles: ProfileStore,
    private val profileId: String,
    private val targetId: String,
    private val control: RuntimeControl,
) : AutoCloseable {
    private val frames = object : LinkedHashMap<String, Frame>(8, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Frame>?): Boolean {
            if (size <= 4) return false
            eldest?.value?.bitmap?.recycle()
            return true
        }
    }
    private val samples = object : LinkedHashMap<String, Sample>(36, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Sample>?): Boolean {
            if (size <= 32) return false
            eldest?.value?.bitmap?.recycle()
            return true
        }
    }
    private var sequence = 0L
    private var sampleSequence = 0L
    private val ocrRecognizerDelegate = lazy {
        TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build())
    }
    private val ocrRecognizer: TextRecognizer by ocrRecognizerDelegate
    private val ocrCache = object : LinkedHashMap<String, Map<String, Any?>>(16, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Map<String, Any?>>?): Boolean =
            size > 16
    }

    fun captureFrame(): Map<String, Any?> {
        control.checkpoint()
        val bitmap = ScreenCaptureService.requireReady().captureBitmap()
        val id = "frame.${++sequence}"
        val space = "${targetId.ifBlank { "android_local" }}:${bitmap.width}x${bitmap.height}"
        val reference = mapOf(
            "kind" to "frame_ref",
            "frame_ref.field.frame_id" to id,
            "frame_ref.field.source_target" to mapOf("kind" to "target_ref", "target_id" to targetId),
            "frame_ref.field.space_version" to space,
            "frame_ref.field.sequence" to sequence,
            "frame_ref.field.captured_at" to Instant.now().toString(),
            "frame_ref.field.width" to bitmap.width,
            "frame_ref.field.height" to bitmap.height,
        )
        frames[id] = Frame(bitmap, reference)
        return reference.toMap()
    }

    fun execute(opcode: String, arguments: Map<String, Any?>): Any? = when (opcode) {
        "target.capture_frame" -> captureFrame()
        "frame.crop_region" -> cropRegion(arguments)
        "vision.compare_samples" -> compareSamples(arguments)
        "color.read" -> readColor(arguments)
        "color.find" -> findColor(arguments)
        "vision.find" -> find(arguments, "official.image.find", 1).firstOrNull()
        "vision.find_all" -> {
            val limit = (arguments["official.image.find_all.parameter.limit"] as? Number)?.toInt() ?: 100
            if (limit !in 1..1000) throw RuntimeFailure("vision.limit_invalid", "图像结果上限必须为 1..1000")
            find(arguments, "official.image.find_all", limit)
        }
        "text.recognize" -> recognize(arguments)
        else -> throw RuntimeFailure("vision.unsupported", "Android 图像宿主不支持：$opcode")
    }

    private fun cropRegion(arguments: Map<String, Any?>): Map<String, Any?> {
        control.checkpoint()
        val owner = "official.frame.crop_region"
        val frame = resolveFrame(arguments["$owner.parameter.frame"])
        val area = region(arguments["$owner.parameter.region"], frame.bitmap, clipToFrame = true)
        if (area.width == 0 || area.height == 0) {
            throw RuntimeFailure("vision.sample_empty", "取样区域与当前画面没有交集")
        }
        val view = Bitmap.createBitmap(frame.bitmap, area.x, area.y, area.width, area.height)
        val bitmap = try {
            view.copy(Bitmap.Config.ARGB_8888, false)
        } finally {
            if (view !== frame.bitmap) view.recycle()
        }
        val id = "sample.${++sampleSequence}"
        val reference = mapOf(
            "kind" to "image_sample",
            "image_sample.field.sample_id" to id,
            "image_sample.field.source_frame" to frame.reference.toMap(),
            "image_sample.field.source_target" to frame.reference["frame_ref.field.source_target"],
            "image_sample.field.space_version" to frame.reference["frame_ref.field.space_version"],
            "image_sample.field.region" to mapOf(
                "kind" to "rect", "x" to area.x, "y" to area.y,
                "width" to area.width, "height" to area.height,
            ),
            "image_sample.field.width" to area.width,
            "image_sample.field.height" to area.height,
        )
        samples[id] = Sample(bitmap, reference)
        return reference.toMap()
    }

    private fun resolveSample(value: Any?): Sample {
        val supplied = value as? Map<*, *>
            ?: throw RuntimeFailure("vision.sample_reference_invalid", "图片样本引用格式无效")
        if (supplied["kind"] != "image_sample") {
            throw RuntimeFailure("vision.sample_reference_invalid", "图片样本引用格式无效")
        }
        val id = supplied["image_sample.field.sample_id"]?.toString().orEmpty()
        val stored = samples[id]
            ?: throw RuntimeFailure("vision.sample_reference_expired", "图片样本已失效")
        if (stored.reference != supplied) {
            throw RuntimeFailure("vision.sample_reference_invalid", "图片样本元数据已被修改")
        }
        return stored
    }

    private fun compareSamples(arguments: Map<String, Any?>): Map<String, Any?> {
        control.checkpoint()
        val owner = "official.image.compare"
        val left = resolveSample(arguments["$owner.parameter.left"])
        val right = resolveSample(arguments["$owner.parameter.right"])
        val strategy = arguments["$owner.parameter.size_strategy"]?.toString() ?: "strict"
        val tolerance = integral(
            arguments["$owner.parameter.pixel_tolerance"] ?: 0,
            "vision.pixel_tolerance_invalid",
            "像素变化容差",
        )
        if (tolerance !in 0..255) {
            throw RuntimeFailure("vision.pixel_tolerance_invalid", "像素变化容差必须是 0 到 255 的整数")
        }
        val sameSize = left.bitmap.width == right.bitmap.width && left.bitmap.height == right.bitmap.height
        val width: Int
        val height: Int
        val rightBitmap: Bitmap
        var recycleRight = false
        when (strategy) {
            "strict" -> {
                if (!sameSize) throw RuntimeFailure("vision.sample_size_mismatch", "两个图片样本尺寸不一致")
                width = left.bitmap.width
                height = left.bitmap.height
                rightBitmap = right.bitmap
            }
            "intersection" -> {
                width = min(left.bitmap.width, right.bitmap.width)
                height = min(left.bitmap.height, right.bitmap.height)
                rightBitmap = right.bitmap
            }
            "scale_right_nearest" -> {
                width = left.bitmap.width
                height = left.bitmap.height
                rightBitmap = Bitmap.createScaledBitmap(right.bitmap, width, height, false)
                recycleRight = rightBitmap !== right.bitmap
            }
            else -> throw RuntimeFailure("vision.compare_strategy_invalid", "图片尺寸处理方式不受支持")
        }
        try {
            val leftPixels = IntArray(width * height)
            val rightPixels = IntArray(width * height)
            left.bitmap.getPixels(leftPixels, 0, width, 0, 0, width, height)
            rightBitmap.getPixels(rightPixels, 0, width, 0, 0, width, height)
            var totalDifference = 0L
            var changedCount = 0L
            var minX = width
            var minY = height
            var maxX = -1
            var maxY = -1
            for (index in leftPixels.indices) {
                if (index % max(1, width * 64) == 0) control.checkpoint()
                val a = leftPixels[index]
                val b = rightPixels[index]
                val red = kotlin.math.abs(Color.red(a) - Color.red(b))
                val green = kotlin.math.abs(Color.green(a) - Color.green(b))
                val blue = kotlin.math.abs(Color.blue(a) - Color.blue(b))
                totalDifference += red + green + blue
                if (max(red, max(green, blue)) > tolerance) {
                    changedCount++
                    val x = index % width
                    val y = index / width
                    minX = min(minX, x)
                    minY = min(minY, y)
                    maxX = max(maxX, x)
                    maxY = max(maxY, y)
                }
            }
            val pixelCount = width.toLong() * height.toLong()
            val similarity = (1.0 - totalDifference.toDouble() / (255.0 * 3.0 * pixelCount)).coerceIn(0.0, 1.0)
            val differenceRegion = if (changedCount == 0L) null else mapOf(
                "kind" to "rect", "x" to minX, "y" to minY,
                "width" to maxX - minX + 1, "height" to maxY - minY + 1,
            )
            return mapOf(
                "image_comparison.field.similarity" to similarity,
                "image_comparison.field.same_size" to sameSize,
                "image_comparison.field.compared_width" to width,
                "image_comparison.field.compared_height" to height,
                "image_comparison.field.changed_pixel_ratio" to changedCount.toDouble() / pixelCount,
                "image_comparison.field.difference_region" to differenceRegion,
                "image_comparison.field.left" to left.reference.toMap(),
                "image_comparison.field.right" to right.reference.toMap(),
            )
        } finally {
            if (recycleRight) rightBitmap.recycle()
        }
    }

    internal fun saveFrame(arguments: Map<String, Any?>, files: SafFileRuntime): Map<String, Any?> {
        control.checkpoint()
        val owner = "official.frame.save"
        val frame = resolveFrame(arguments["$owner.parameter.frame"])
        val area = region(arguments["$owner.parameter.region"], frame.bitmap)
        val format = arguments["$owner.parameter.format"]?.toString()?.lowercase() ?: "png"
        val compressFormat = when (format) {
            "png" -> Bitmap.CompressFormat.PNG
            "jpeg" -> Bitmap.CompressFormat.JPEG
            else -> throw RuntimeFailure("vision.image_format_unsupported", "图片格式只支持 PNG 或 JPEG")
        }
        val quality = (arguments["$owner.parameter.quality"] as? Number)?.toInt() ?: 90
        if (quality !in 1..100) throw RuntimeFailure("vision.image_quality_invalid", "JPEG 质量必须为 1 至 100 的整数")
        val cropped = Bitmap.createBitmap(frame.bitmap, area.x, area.y, area.width, area.height)
        val bytes = try {
            ByteArrayOutputStream().use { output ->
                if (!cropped.compress(compressFormat, quality, output)) {
                    throw RuntimeFailure("vision.image_encode_failed", "Android 无法编码当前画面")
                }
                output.toByteArray()
            }
        } catch (error: RuntimeFailure) {
            throw error
        } catch (error: Exception) {
            throw RuntimeFailure("vision.image_encode_failed", "Android 画面编码失败：${error.message}", true, error)
        } finally {
            if (cropped !== frame.bitmap) cropped.recycle()
        }
        control.checkpoint()
        return files.writeBinary(arguments["$owner.parameter.file"], bytes)
    }

    private fun readColor(arguments: Map<String, Any?>): Map<String, Int> {
        val owner = "official.color.read"
        val frame = resolveFrame(arguments["$owner.parameter.frame"])
        val point = point(arguments["$owner.parameter.position"])
        if (point.first !in 0 until frame.bitmap.width || point.second !in 0 until frame.bitmap.height) {
            throw RuntimeFailure("target.invalid_point", "颜色读取位置超出当前画面")
        }
        return colorValue(frame.bitmap.getPixel(point.first, point.second))
    }

    private fun findColor(arguments: Map<String, Any?>): Map<String, Any?>? {
        val owner = "official.color.find"
        val expected = parseColor(arguments["$owner.parameter.color"])
        val tolerance = integral(arguments["$owner.parameter.tolerance"] ?: 0, "vision.color_tolerance_invalid", "颜色容差")
        if (tolerance !in 0..255) {
            throw RuntimeFailure("vision.color_tolerance_invalid", "颜色容差必须是 0 到 255 的整数")
        }
        val frame = resolveFrame(arguments["$owner.parameter.frame"])
        val area = region(arguments["$owner.parameter.region"], frame.bitmap, clipToFrame = true)
        if (area.width == 0 || area.height == 0) return null
        val expectedAlpha = expected[3]
        if (kotlin.math.abs(255 - expectedAlpha) > tolerance) return null
        val row = IntArray(area.width)
        for (y in area.y until area.y + area.height) {
            control.checkpoint()
            frame.bitmap.getPixels(row, 0, area.width, area.x, y, area.width, 1)
            for (x in row.indices) {
                val pixel = row[x]
                if (
                    kotlin.math.abs(Color.red(pixel) - expected[0]) <= tolerance &&
                    kotlin.math.abs(Color.green(pixel) - expected[1]) <= tolerance &&
                    kotlin.math.abs(Color.blue(pixel) - expected[2]) <= tolerance &&
                    kotlin.math.abs(Color.alpha(pixel) - expectedAlpha) <= tolerance
                ) {
                    return mapOf("kind" to "point", "x" to area.x + x, "y" to y)
                }
            }
        }
        return null
    }

    private fun point(value: Any?): Pair<Int, Int> {
        val raw = value as? Map<*, *>
            ?: throw RuntimeFailure("target.invalid_point", "坐标参数无效")
        if (raw["kind"] != "point") throw RuntimeFailure("target.invalid_point", "坐标参数无效")
        return Pair(
            integral(raw["x"], "target.invalid_point", "坐标 X"),
            integral(raw["y"], "target.invalid_point", "坐标 Y"),
        )
    }

    private fun parseColor(value: Any?): IntArray {
        val raw = value as? Map<*, *>
            ?: throw RuntimeFailure("vision.color_invalid", "颜色参数无效")
        val channels = listOf("red", "green", "blue", "alpha").map { name ->
            integral(raw["color.field.$name"], "vision.color_invalid", "颜色通道")
        }
        if (channels.any { it !in 0..255 }) {
            throw RuntimeFailure("vision.color_invalid", "颜色通道必须是 0 到 255 的整数")
        }
        return channels.toIntArray()
    }

    private fun integral(value: Any?, errorId: String, label: String): Int {
        val number = value as? Number ?: throw RuntimeFailure(errorId, "$label 必须是整数")
        val decimal = number.toDouble()
        if (!decimal.isFinite() || decimal % 1.0 != 0.0 || decimal < Int.MIN_VALUE || decimal > Int.MAX_VALUE) {
            throw RuntimeFailure(errorId, "$label 必须是整数")
        }
        return decimal.toInt()
    }

    private fun colorValue(pixel: Int): Map<String, Int> = mapOf(
        "color.field.red" to Color.red(pixel),
        "color.field.green" to Color.green(pixel),
        "color.field.blue" to Color.blue(pixel),
        "color.field.alpha" to Color.alpha(pixel),
    )

    private fun recognize(arguments: Map<String, Any?>): Map<String, Any?> {
        val owner = "official.text.recognize"
        val language = arguments["$owner.parameter.language"]?.toString() ?: "auto"
        if (language != "auto") {
            throw RuntimeFailure("ocr.language_unsupported", "当前 Android OCR 不支持语言模式：$language")
        }
        val frame = resolveFrame(arguments["$owner.parameter.frame"])
        val area = region(arguments["$owner.parameter.region"], frame.bitmap, clipToFrame = true)
        val preprocess = ocrPreprocess(arguments["$owner.parameter.preprocess"])
        if (area.width == 0 || area.height == 0) {
            return mapOf(
                "ocr_result.field.text" to "",
                "ocr_result.field.lines" to emptyList<Map<String, Any?>>(),
                "ocr_result.field.region" to mapOf(
                    "kind" to "rect",
                    "x" to area.x,
                    "y" to area.y,
                    "width" to 0,
                    "height" to 0,
                ),
                "ocr_result.field.source_frame" to frame.reference.toMap(),
                "ocr_result.field.source_target" to frame.reference["frame_ref.field.source_target"],
                "ocr_result.field.space_version" to frame.reference["frame_ref.field.space_version"],
            )
        }
        val frameId = frame.reference["frame_ref.field.frame_id"]?.toString().orEmpty()
        val cacheKey = listOf(
            frameId, area.x, area.y, area.width, area.height,
            preprocess.grayscale, preprocess.binary, preprocess.threshold, preprocess.invert,
        ).joinToString("|")
        ocrCache[cacheKey]?.let { return it.toMap() }

        control.checkpoint()
        val prepared = prepareOcrBitmap(frame.bitmap, area, preprocess)
        val recognized = try {
            Tasks.await(
                ocrRecognizer.process(InputImage.fromBitmap(prepared, 0)),
                20,
                TimeUnit.SECONDS,
            )
        } catch (error: Exception) {
            throw RuntimeFailure(
                "ocr.inference_failed",
                "Android OCR 分析失败：${error.message ?: error.javaClass.simpleName}",
                transient = true,
                cause = error,
            )
        } finally {
            prepared.recycle()
        }
        control.checkpoint()
        val lines = recognized.textBlocks.flatMap { it.lines }.mapNotNull { line ->
            val bounds = line.boundingBox ?: return@mapNotNull null
            mapOf(
                "ocr_line.field.text" to line.text,
                "ocr_line.field.region" to mapOf(
                    "kind" to "rect",
                    "x" to area.x + bounds.left,
                    "y" to area.y + bounds.top,
                    "width" to bounds.width(),
                    "height" to bounds.height(),
                ),
            )
        }
        val result = mapOf(
            "ocr_result.field.text" to recognized.text,
            "ocr_result.field.lines" to lines,
            "ocr_result.field.region" to mapOf(
                "kind" to "rect",
                "x" to area.x,
                "y" to area.y,
                "width" to area.width,
                "height" to area.height,
            ),
            "ocr_result.field.source_frame" to frame.reference.toMap(),
            "ocr_result.field.source_target" to frame.reference["frame_ref.field.source_target"],
            "ocr_result.field.space_version" to frame.reference["frame_ref.field.space_version"],
        )
        ocrCache[cacheKey] = result
        return result.toMap()
    }

    private fun ocrPreprocess(value: Any?): OcrPreprocess {
        if (value == null) return OcrPreprocess()
        val raw = value as? Map<*, *>
            ?: throw RuntimeFailure("ocr.preprocess_invalid", "OCR 预处理参数格式无效")
        val allowed = setOf(
            "ocr_preprocess.field.grayscale",
            "ocr_preprocess.field.binary",
            "ocr_preprocess.field.threshold",
            "ocr_preprocess.field.invert",
        )
        val unknown = raw.keys.map(Any?::toString).filterNot(allowed::contains)
        if (unknown.isNotEmpty()) {
            throw RuntimeFailure("ocr.preprocess_invalid", "OCR 预处理包含未知字段：${unknown.sorted()}")
        }
        fun flag(name: String): Boolean = when (val item = raw[name]) {
            null -> false
            is Boolean -> item
            else -> throw RuntimeFailure("ocr.preprocess_invalid", "OCR 预处理开关必须是布尔值")
        }
        val thresholdValue = raw["ocr_preprocess.field.threshold"] ?: 127
        val threshold = (thresholdValue as? Number)?.toDouble()?.let { number ->
            if (number.isFinite() && number % 1.0 == 0.0) number.toInt() else null
        } ?: throw RuntimeFailure("ocr.preprocess_invalid", "OCR 二值化阈值必须是 0 到 255 的整数")
        if (threshold !in 0..255) {
            throw RuntimeFailure("ocr.preprocess_invalid", "OCR 二值化阈值必须是 0 到 255 的整数")
        }
        return OcrPreprocess(
            grayscale = flag("ocr_preprocess.field.grayscale"),
            binary = flag("ocr_preprocess.field.binary"),
            threshold = threshold,
            invert = flag("ocr_preprocess.field.invert"),
        )
    }

    private fun prepareOcrBitmap(source: Bitmap, area: Region, options: OcrPreprocess): Bitmap {
        val result = Bitmap.createBitmap(source, area.x, area.y, area.width, area.height)
            .copy(Bitmap.Config.ARGB_8888, true)
        if (!options.grayscale && !options.binary && !options.invert) return result
        val pixels = IntArray(result.width * result.height)
        result.getPixels(pixels, 0, result.width, 0, 0, result.width, result.height)
        for (index in pixels.indices) {
            val pixel = pixels[index]
            var red = Color.red(pixel)
            var green = Color.green(pixel)
            var blue = Color.blue(pixel)
            if (options.grayscale || options.binary) {
                val gray = (red * 299 + green * 587 + blue * 114 + 500) / 1000
                red = gray
                green = gray
                blue = gray
            }
            if (options.binary) {
                val value = if (red >= options.threshold) 255 else 0
                red = value
                green = value
                blue = value
            }
            if (options.invert) {
                red = 255 - red
                green = 255 - green
                blue = 255 - blue
            }
            pixels[index] = Color.argb(Color.alpha(pixel), red, green, blue)
        }
        result.setPixels(pixels, 0, result.width, 0, 0, result.width, result.height)
        return result
    }

    private fun find(arguments: Map<String, Any?>, owner: String, limit: Int): List<Map<String, Any?>> {
        val reference = arguments["$owner.parameter.image"] as? Map<*, *>
            ?: throw RuntimeFailure("vision.asset_reference_invalid", "图片参数需要稳定 asset_ref")
        if (reference["kind"] != "asset_ref") throw RuntimeFailure("vision.asset_reference_invalid", "图片参数需要稳定 asset_ref")
        val assetId = reference["asset_id"]?.toString().orEmpty()
        val template = loadAsset(assetId)
        try {
            val threshold = (arguments["$owner.parameter.similarity"] as? Number)?.toDouble() ?: 0.85
            if (!threshold.isFinite() || threshold !in 0.0..1.0) {
                throw RuntimeFailure("vision.similarity_invalid", "相似度必须是 0..1")
            }
            val frame = resolveFrame(arguments["$owner.parameter.frame"])
            val region = region(arguments["$owner.parameter.region"], frame.bitmap, clipToFrame = true)
            if (template.width > region.width || template.height > region.height) return emptyList()
            val matches = match(frame.bitmap, template, region, threshold, limit)
            return matches.map { match ->
                val rect = mapOf(
                    "kind" to "rect", "x" to match.x, "y" to match.y,
                    "width" to template.width, "height" to template.height,
                )
                mapOf(
                    "image_match.field.region" to rect,
                    "image_match.field.center" to mapOf(
                        "kind" to "point",
                        "x" to match.x + template.width / 2,
                        "y" to match.y + template.height / 2,
                    ),
                    "image_match.field.similarity" to match.score,
                    "image_match.field.source_asset" to mapOf("kind" to "asset_ref", "asset_id" to assetId),
                    "image_match.field.source_frame" to frame.reference.toMap(),
                    "image_match.field.source_target" to frame.reference["frame_ref.field.source_target"],
                    "image_match.field.space_version" to frame.reference["frame_ref.field.space_version"],
                )
            }
        } finally {
            template.recycle()
        }
    }

    private fun resolveFrame(value: Any?): Frame {
        if (value == null) {
            val reference = captureFrame()
            return frames[reference["frame_ref.field.frame_id"]]
                ?: throw RuntimeFailure("vision.frame_reference_expired", "新画面引用意外失效")
        }
        val supplied = value as? Map<*, *>
            ?: throw RuntimeFailure("vision.frame_reference_invalid", "画面引用格式无效")
        if (supplied["kind"] != "frame_ref") throw RuntimeFailure("vision.frame_reference_invalid", "画面引用格式无效")
        val id = supplied["frame_ref.field.frame_id"]?.toString().orEmpty()
        val stored = frames[id] ?: throw RuntimeFailure("vision.frame_reference_expired", "画面引用已失效")
        if (stored.reference != supplied) throw RuntimeFailure("vision.frame_reference_invalid", "画面引用元数据已被修改")
        return stored
    }

    private fun loadAsset(assetId: String): Bitmap {
        if (assetId.isBlank()) throw RuntimeFailure("vision.asset_reference_invalid", "asset_ref 缺少 asset_id")
        val bytes = if (assetId.startsWith("profile_")) {
            val digest = assetId.removePrefix("profile_")
            if (!digest.matches(Regex("[0-9a-f]{64}"))) throw RuntimeFailure("vision.asset_reference_invalid", "Player 私有图片 ID 无效")
            val file = java.io.File(profiles.dataRoot(bundle), "profiles/$profileId/images/$digest.png")
            if (!file.isFile || file.length() > 32L * 1024L * 1024L) throw RuntimeFailure("vision.asset_missing", "Player 私有图片不存在")
            val content = file.readBytes()
            if (JsonSupport.sha256(content) != digest) throw RuntimeFailure("vision.asset_corrupt", "Player 私有图片哈希不一致")
            content
        } else {
            val registry = try {
                JsonSupport.parseObject(bundle.readEntry("assets/registry.json", 16L * 1024L * 1024L), "资源注册表")
            } catch (error: BundleVerificationException) {
                throw RuntimeFailure("vision.asset_missing", "Player 包没有图片资源注册表", cause = error)
            }
            val record = registry.obj("assets").get(assetId)
                ?.takeIf { it.isJsonObject }?.asJsonObject
                ?: throw RuntimeFailure("vision.asset_missing", "图片资源不存在：$assetId")
            val path = record.string("path").replace('\\', '/').trim('/')
            if (!path.startsWith("assets/") || path.split('/').any { it in setOf("", ".", "..") }) {
                throw RuntimeFailure("vision.asset_corrupt", "资源注册路径无效")
            }
            val content = bundle.readEntry(path, 32L * 1024L * 1024L)
            val expected = record.string("sha256")
            if (expected.isNotBlank() && JsonSupport.sha256(content) != expected) {
                throw RuntimeFailure("vision.asset_corrupt", "图片资源哈希不一致")
            }
            content
        }
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
            ?: throw RuntimeFailure("vision.asset_corrupt", "图片资源无法解码")
    }

    private fun region(value: Any?, bitmap: Bitmap, clipToFrame: Boolean = false): Region {
        if (value == null) return Region(0, 0, bitmap.width, bitmap.height)
        val raw = value as? Map<*, *> ?: throw RuntimeFailure("vision.region_invalid", "图像区域必须是 rect")
        if (raw["kind"] != "rect") throw RuntimeFailure("vision.region_invalid", "图像区域必须是 rect")
        val x = integral(raw["x"], "vision.region_invalid", "图像区域 x")
        val y = integral(raw["y"], "vision.region_invalid", "图像区域 y")
        val width = integral(raw["width"], "vision.region_invalid", "图像区域 width")
        val height = integral(raw["height"], "vision.region_invalid", "图像区域 height")
        if (width <= 0 || height <= 0) {
            throw RuntimeFailure("vision.region_invalid", "图像区域宽高必须大于 0")
        }
        val right = x.toLong() + width.toLong()
        val bottom = y.toLong() + height.toLong()
        if (!clipToFrame) {
            if (x < 0 || y < 0 || right > bitmap.width.toLong() || bottom > bitmap.height.toLong()) {
                throw RuntimeFailure("vision.region_invalid", "图像区域越出当前帧")
            }
            return Region(x, y, width, height)
        }
        val left = x.toLong().coerceIn(0L, bitmap.width.toLong())
        val top = y.toLong().coerceIn(0L, bitmap.height.toLong())
        val clippedRight = right.coerceIn(0L, bitmap.width.toLong())
        val clippedBottom = bottom.coerceIn(0L, bitmap.height.toLong())
        return Region(
            left.toInt(),
            top.toInt(),
            max(0L, clippedRight - left).toInt(),
            max(0L, clippedBottom - top).toInt(),
        )
    }

    private fun match(
        frame: Bitmap,
        template: Bitmap,
        region: Region,
        threshold: Double,
        limit: Int,
    ): List<Match> {
        val framePixels = IntArray(frame.width * frame.height)
        frame.getPixels(framePixels, 0, frame.width, 0, 0, frame.width, frame.height)
        val templatePixels = IntArray(template.width * template.height)
        template.getPixels(templatePixels, 0, template.width, 0, 0, template.width, template.height)
        val xCount = region.width - template.width + 1
        val yCount = region.height - template.height + 1
        val candidates = xCount.toLong() * yCount.toLong()
        val stride = max(1, ceil(sqrt(candidates / 2_000_000.0)).toInt())
        val sampleX = sampleAxis(template.width, 12)
        val sampleY = sampleAxis(template.height, 12)
        val matches = mutableListOf<Match>()
        var y = region.y
        while (y <= region.y + region.height - template.height) {
            var x = region.x
            while (x <= region.x + region.width - template.width) {
                control.checkpoint()
                val score = similarity(framePixels, frame.width, templatePixels, template.width, x, y, sampleX, sampleY, threshold)
                if (score >= threshold) {
                    val candidate = Match(x, y, score)
                    if (matches.none { overlaps(it, candidate, template.width, template.height) }) {
                        matches += candidate
                        matches.sortByDescending(Match::score)
                        if (matches.size > limit) matches.removeAt(matches.lastIndex)
                    }
                }
                x += stride
            }
            y += stride
        }
        return matches.sortedWith(compareByDescending<Match> { it.score }.thenBy { it.y }.thenBy { it.x }).take(limit)
    }

    private fun similarity(
        frame: IntArray,
        frameWidth: Int,
        template: IntArray,
        templateWidth: Int,
        offsetX: Int,
        offsetY: Int,
        sampleX: IntArray,
        sampleY: IntArray,
        threshold: Double,
    ): Double {
        var difference = 0L
        var count = 0
        val maximumDifference = 255L * 3L * sampleX.size * sampleY.size
        val allowed = ((1.0 - threshold) * maximumDifference).toLong()
        for (y in sampleY) {
            for (x in sampleX) {
                val a = frame[(offsetY + y) * frameWidth + offsetX + x]
                val b = template[y * templateWidth + x]
                difference += kotlin.math.abs((a shr 16 and 255) - (b shr 16 and 255))
                difference += kotlin.math.abs((a shr 8 and 255) - (b shr 8 and 255))
                difference += kotlin.math.abs((a and 255) - (b and 255))
                count++
                if (difference > allowed && count >= 16) return 1.0 - difference.toDouble() / (255.0 * 3.0 * count)
            }
        }
        return 1.0 - difference.toDouble() / (255.0 * 3.0 * count)
    }

    private fun sampleAxis(size: Int, samples: Int): IntArray {
        if (size <= samples) return IntArray(size) { it }
        return IntArray(samples) { index -> ((size - 1) * index.toDouble() / (samples - 1)).toInt() }
    }

    private fun overlaps(left: Match, right: Match, width: Int, height: Int): Boolean {
        val overlapWidth = max(0, min(left.x + width, right.x + width) - max(left.x, right.x))
        val overlapHeight = max(0, min(left.y + height, right.y + height) - max(left.y, right.y))
        return overlapWidth.toLong() * overlapHeight * 2 > width.toLong() * height
    }

    override fun close() {
        frames.values.forEach { it.bitmap.recycle() }
        frames.clear()
        samples.values.forEach { it.bitmap.recycle() }
        samples.clear()
        ocrCache.clear()
        if (ocrRecognizerDelegate.isInitialized()) ocrRecognizer.close()
    }

    private data class Frame(val bitmap: Bitmap, val reference: Map<String, Any?>)
    private data class Sample(val bitmap: Bitmap, val reference: Map<String, Any?>)
    private data class Region(val x: Int, val y: Int, val width: Int, val height: Int)
    private data class OcrPreprocess(
        val grayscale: Boolean = false,
        val binary: Boolean = false,
        val threshold: Int = 127,
        val invert: Boolean = false,
    )
    private data class Match(val x: Int, val y: Int, val score: Double)
}
