using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Forms.Integration;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Shell;
using Forms = System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace Easycode.CaptureOverlay
{
    /// <summary>
    /// Native desktop owner for the packaged Player UI.  Vue still owns the
    /// product surface; this window owns only OS lifecycle, WebView2 and the
    /// small, versioned window-command bridge.
    /// </summary>
    internal sealed class DesktopShellWindow : Window
    {
        private readonly Uri _entryUri;
        private readonly string _allowedOrigin;
        private readonly WebView2 _webView;
        private readonly Border _loadingLayer;
        private readonly TextBlock _loadingText;
        private readonly Button _retryButton;
        private HwndSource _windowSource;
        private int _navigationAttempts;
        private bool _initialized;
        private bool _closing;
        private bool _uiReady;
        private bool _closeAuthorized;
        private bool _closeRequestPending;

        internal DesktopShellWindow(string url, string title, string iconPath, int width, int height)
        {
            Uri parsed;
            if (!Uri.TryCreate(url, UriKind.Absolute, out parsed) ||
                (parsed.Scheme != Uri.UriSchemeHttp && parsed.Scheme != Uri.UriSchemeHttps))
                throw new ArgumentException("桌面客户端入口地址无效", "url");

            _entryUri = parsed;
            _allowedOrigin = parsed.GetLeftPart(UriPartial.Authority);

            Title = String.IsNullOrWhiteSpace(title) ? "Easycode 自动化运行助手" : title;
            Width = Math.Max(800, width);
            Height = Math.Max(600, height);
            MinWidth = 800;
            MinHeight = 600;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            WindowStyle = WindowStyle.None;
            ResizeMode = ResizeMode.CanResize;
            Background = new SolidColorBrush(Color.FromRgb(18, 24, 36));
            WindowChrome.SetWindowChrome(this, new WindowChrome
            {
                CaptionHeight = 0,
                ResizeBorderThickness = new Thickness(10),
                CornerRadius = new CornerRadius(0),
                GlassFrameThickness = new Thickness(0),
                UseAeroCaptionButtons = false
            });
            TrySetIcon(iconPath);

            _webView = new WebView2 { Dock = Forms.DockStyle.Fill };
            WindowsFormsHost host = new WindowsFormsHost { Child = _webView };

            _loadingText = new TextBlock
            {
                Text = "正在启动 Easycode Player…",
                Foreground = new SolidColorBrush(Color.FromRgb(214, 222, 234)),
                FontSize = 14,
                HorizontalAlignment = HorizontalAlignment.Center,
                TextAlignment = TextAlignment.Center,
                Margin = new Thickness(24, 0, 24, 14)
            };
            _retryButton = new Button
            {
                Content = "重试",
                Width = 84,
                Height = 30,
                Visibility = Visibility.Collapsed,
                Background = new SolidColorBrush(Color.FromRgb(64, 158, 255)),
                Foreground = Brushes.White,
                BorderThickness = new Thickness(0)
            };
            _retryButton.Click += delegate { BeginNavigation(true); };

            StackPanel loadingContent = new StackPanel
            {
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center
            };
            loadingContent.Children.Add(_loadingText);
            loadingContent.Children.Add(_retryButton);
            _loadingLayer = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(18, 24, 36)),
                Child = loadingContent
            };

            Grid root = new Grid();
            root.Children.Add(host);
            root.Children.Add(_loadingLayer);
            Content = root;

            Loaded += async delegate { await InitializeAsync(); };
            Closing += OnClosing;
            Closed += delegate
            {
                _closing = true;
                if (_windowSource != null) _windowSource.RemoveHook(WindowProcedure);
                try { _webView.Dispose(); } catch { }
            };
            StateChanged += delegate { PublishWindowState(); };
            SourceInitialized += OnSourceInitialized;
        }

        private void OnSourceInitialized(object sender, EventArgs args)
        {
            NativeMethods.RemoveVisibleWindowFrame(this);
            IntPtr handle = new WindowInteropHelper(this).Handle;
            _windowSource = HwndSource.FromHwnd(handle);
            if (_windowSource != null) _windowSource.AddHook(WindowProcedure);
        }

        private IntPtr WindowProcedure(IntPtr hwnd, int message, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            const int WmNcHitTest = 0x0084;
            if (message != WmNcHitTest || WindowState == WindowState.Maximized) return IntPtr.Zero;

            long packed = lParam.ToInt64();
            double screenX = unchecked((short)(packed & 0xffff));
            double screenY = unchecked((short)((packed >> 16) & 0xffff));
            Point point = PointFromScreen(new Point(screenX, screenY));
            const double grip = 10.0;
            bool left = point.X >= 0 && point.X <= grip;
            bool right = point.X <= ActualWidth && point.X >= ActualWidth - grip;
            bool top = point.Y >= 0 && point.Y <= grip;
            bool bottom = point.Y <= ActualHeight && point.Y >= ActualHeight - grip;

            int hit = 0;
            if (top && left) hit = 13;          // HTTOPLEFT
            else if (top && right) hit = 14;   // HTTOPRIGHT
            else if (bottom && left) hit = 16; // HTBOTTOMLEFT
            else if (bottom && right) hit = 17;// HTBOTTOMRIGHT
            else if (left) hit = 10;           // HTLEFT
            else if (right) hit = 11;          // HTRIGHT
            else if (top) hit = 12;            // HTTOP
            else if (bottom) hit = 15;         // HTBOTTOM
            if (hit == 0) return IntPtr.Zero;
            handled = true;
            return new IntPtr(hit);
        }

        private void TrySetIcon(string iconPath)
        {
            if (String.IsNullOrWhiteSpace(iconPath) || !System.IO.File.Exists(iconPath)) return;
            try
            {
                BitmapImage image = new BitmapImage();
                image.BeginInit();
                image.CacheOption = BitmapCacheOption.OnLoad;
                image.UriSource = new Uri(System.IO.Path.GetFullPath(iconPath), UriKind.Absolute);
                image.EndInit();
                image.Freeze();
                Icon = image;
            }
            catch { }
        }

        private async Task InitializeAsync()
        {
            if (_initialized || _closing) return;
            try
            {
                CoreWebView2Environment environment = await WebViewEnvironmentProvider.GetAsync();
                await _webView.EnsureCoreWebView2Async(environment);
                _webView.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
                _webView.CoreWebView2.Settings.AreDevToolsEnabled = false;
                _webView.CoreWebView2.Settings.IsStatusBarEnabled = false;
                _webView.CoreWebView2.Settings.IsZoomControlEnabled = false;
                _webView.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
                _webView.CoreWebView2.NavigationStarting += OnNavigationStarting;
                _webView.CoreWebView2.NavigationCompleted += OnNavigationCompleted;
                _webView.CoreWebView2.ProcessFailed += OnProcessFailed;
                _initialized = true;
                BeginNavigation(true);
            }
            catch (Exception ex)
            {
                ShowFailure("桌面渲染器初始化失败：" + ex.Message);
            }
        }

        private void BeginNavigation(bool resetAttempts)
        {
            if (!_initialized || _closing) return;
            if (resetAttempts) _navigationAttempts = 0;
            _retryButton.Visibility = Visibility.Collapsed;
            _loadingText.Text = "正在连接本地运行引擎…";
            _loadingLayer.Visibility = Visibility.Visible;
            _navigationAttempts++;
            _webView.CoreWebView2.Navigate(_entryUri.AbsoluteUri);
        }

        private void OnNavigationStarting(object sender, CoreWebView2NavigationStartingEventArgs args)
        {
            Uri target;
            if (!Uri.TryCreate(args.Uri, UriKind.Absolute, out target))
            {
                args.Cancel = true;
                return;
            }
            string origin = target.GetLeftPart(UriPartial.Authority);
            if (!String.Equals(origin, _allowedOrigin, StringComparison.OrdinalIgnoreCase))
                args.Cancel = true;
        }

        private async void OnNavigationCompleted(object sender, CoreWebView2NavigationCompletedEventArgs args)
        {
            if (_closing) return;
            if (args.IsSuccess)
            {
                _uiReady = true;
                _loadingLayer.Visibility = Visibility.Collapsed;
                PublishWindowState();
                PostMessage(new Dictionary<string, object>
                {
                    { "event", "desktop-shell-ready" },
                    { "version", 1 }
                });
                return;
            }

            // The shell starts immediately while uvicorn is warming.  Retrying
            // inside the native dispatcher avoids a Python GUI loop and keeps a
            // responsive, honest startup surface.
            if (_navigationAttempts < 60)
            {
                _loadingText.Text = "运行引擎正在初始化…";
                await Task.Delay(250);
                if (!_closing) BeginNavigation(false);
                return;
            }
            ShowFailure("无法连接本地运行引擎（" + args.WebErrorStatus + "）");
        }

        private void OnProcessFailed(object sender, CoreWebView2ProcessFailedEventArgs args)
        {
            ShowFailure("桌面渲染进程异常退出，请重试（" + args.ProcessFailedKind + "）");
        }

        private void ShowFailure(string message)
        {
            _loadingText.Text = message;
            _retryButton.Visibility = Visibility.Visible;
            _loadingLayer.Visibility = Visibility.Visible;
        }

        private void OnWebMessageReceived(object sender, CoreWebView2WebMessageReceivedEventArgs args)
        {
            Dictionary<string, object> data;
            try { data = JsonUtil.Parse(args.WebMessageAsJson); }
            catch { return; }
            if (data == null || JsonUtil.String(data, "event", "") != "window-command") return;
            string command = JsonUtil.String(data, "command", "");
            if (command == "minimize") WindowState = WindowState.Minimized;
            else if (command == "maximize")
                WindowState = WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
            else if (command == "close") RequestClose();
            else if (command == "close-confirmed")
            {
                _closeAuthorized = true;
                _closeRequestPending = false;
                Close();
            }
            else if (command == "close-cancelled") _closeRequestPending = false;
            else if (command == "drag" && WindowState != WindowState.Maximized)
                BeginNativeDrag();
        }

        private void OnClosing(object sender, CancelEventArgs args)
        {
            if (_closing || _closeAuthorized || !_uiReady)
            {
                _closing = true;
                return;
            }
            args.Cancel = true;
            RequestClose();
        }

        private void RequestClose()
        {
            if (_closing || _closeRequestPending) return;
            if (!_uiReady)
            {
                _closeAuthorized = true;
                Close();
                return;
            }
            _closeRequestPending = true;
            PostMessage(new Dictionary<string, object>
            {
                { "event", "desktop-window-close-requested" },
                { "version", 1 }
            });
        }

        private void BeginNativeDrag()
        {
            try
            {
                IntPtr handle = new WindowInteropHelper(this).Handle;
                NativeMethods.ReleaseCapture();
                NativeMethods.SendMessage(handle, NativeMethods.WM_NCLBUTTONDOWN,
                    new IntPtr(NativeMethods.HTCAPTION), IntPtr.Zero);
            }
            catch { }
        }

        private void PublishWindowState()
        {
            if (!_initialized || _webView.CoreWebView2 == null) return;
            PostMessage(new Dictionary<string, object>
            {
                { "event", "desktop-window-state" },
                { "version", 1 },
                { "maximized", WindowState == WindowState.Maximized }
            });
        }

        private void PostMessage(Dictionary<string, object> payload)
        {
            try { _webView.CoreWebView2.PostWebMessageAsJson(JsonUtil.Serialize(payload)); }
            catch { }
        }
    }
}
