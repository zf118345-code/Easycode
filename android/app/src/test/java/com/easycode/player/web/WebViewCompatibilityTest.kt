package com.easycode.player.web

import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import org.junit.Test

class WebViewCompatibilityTest {
    @Test
    fun oldOrUnknownEnginesFailBeforeLoadingTheSharedPlayer() {
        val old = webViewCompatibility(
            "Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 Chrome/37.0.0.0 Mobile Safari/537.36",
            64,
        )
        assertFalse(old.compatible)
        assertEquals(37, old.detectedMajor)
        assertFalse(webViewCompatibility("VendorWebView/1.0", 64).compatible)
    }

    @Test
    fun supportedEngineIsAcceptedIndependentlyFromAndroidApiLevel() {
        val result = webViewCompatibility(
            "Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 Chrome/64.0.3282.137 Mobile Safari/537.36",
            64,
        )
        assertTrue(result.compatible)
        assertEquals(64, result.detectedMajor)
    }
}
