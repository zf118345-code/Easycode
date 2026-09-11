package com.easycode.player.runtime

import org.junit.Test
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class AndroidStandardTextHostTest {
    @Test
    fun exactContainsAndRegexMatchWindowsSemantics() {
        assertTrue(AndroidStandardImageHost.textMatches("体力 86", "体力 86", "exact"))
        assertFalse(AndroidStandardImageHost.textMatches("体力 86/120", "体力 86", "exact"))
        assertTrue(AndroidStandardImageHost.textMatches("体力 86/120", "86", "contains"))
        assertTrue(AndroidStandardImageHost.textMatches("体力 86/120", "体力\\s+\\d+", "regex"))
    }

    @Test
    fun invalidUserInputKeepsStableErrors() {
        val empty = assertFailsWith<RuntimeFailure> {
            AndroidStandardImageHost.textMatches("任意文字", "", "contains")
        }
        assertTrue(empty.errorId == "runtime.argument_range")

        val regex = assertFailsWith<RuntimeFailure> {
            AndroidStandardImageHost.textMatches("任意文字", "[", "regex")
        }
        assertTrue(regex.errorId == "text.regex_invalid")

        val mode = assertFailsWith<RuntimeFailure> {
            AndroidStandardImageHost.textMatches("任意文字", "文字", "unknown")
        }
        assertTrue(mode.errorId == "runtime.argument_range")
    }
}
