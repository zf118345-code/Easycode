package com.easycode.player.bundle

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ContentPackageRepositoryDecisionTest {
    @Test
    fun embeddedBaselineDoesNotReplaceOnlineContentUntilApkBaselineChanges() {
        assertTrue(shouldActivateEmbedded(false, "", "apk-v1"))
        assertFalse(shouldActivateEmbedded(true, "apk-v1", "apk-v1"))
        assertTrue(shouldActivateEmbedded(true, "apk-v1", "apk-v2"))
    }
}
