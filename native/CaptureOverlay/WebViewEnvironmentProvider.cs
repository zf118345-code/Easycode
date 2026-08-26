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
                if (_environmentTask == null)
                {
                    string dataRoot = Path.Combine(
                        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                        "Easycode", "WebView2");
                    Directory.CreateDirectory(dataRoot);
                    _environmentTask = CoreWebView2Environment.CreateAsync(null, dataRoot);
                }
                return _environmentTask;
            }
        }
    }
}
