using System;
using System.IO;
using System.Threading.Tasks;
using Microsoft.Web.WebView2.Core;

namespace Easycode.CaptureOverlay
{
    internal static class WebViewEnvironmentProvider
    {
        private static readonly object Sync = new object();
        private static Task<CoreWebView2Environment> _environmentTask;

        internal static Task<CoreWebView2Environment> GetAsync()
        {
            lock (Sync)
            {
                // A failed CreateAsync task must not poison the resident
                // capture host forever.  WebView2 documents that controller
                // retries should start from a fresh environment.
                if (_environmentTask != null &&
                    (_environmentTask.IsFaulted || _environmentTask.IsCanceled))
                    _environmentTask = null;
                if (_environmentTask == null)
                {
                    string instanceRoot = Environment.GetEnvironmentVariable("EASYCODE_PLAYER_DATA_DIR");
                    string dataRoot = string.IsNullOrWhiteSpace(instanceRoot)
                        ? Path.Combine(
                            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                            "Easycode", "WebView2")
                        : Path.Combine(Path.GetFullPath(instanceRoot), "WebView2");
                    Directory.CreateDirectory(dataRoot);
                    _environmentTask = CoreWebView2Environment.CreateAsync(null, dataRoot);
                }
                return _environmentTask;
            }
        }

        internal static void ResetAfterFailure()
        {
            lock (Sync)
            {
                _environmentTask = null;
            }
        }
    }
}
