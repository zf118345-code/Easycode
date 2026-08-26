using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Forms.Integration;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace Easycode.CaptureOverlay
{
    internal sealed class CaptureFileBrowserResult
    {
        internal bool Completed;
        internal Dictionary<string, object> ActionResult;
        internal int FileCount;
    }

    /// <summary>
    /// One resident floating shell around the shared Vue FileBrowser.
    /// The window and WebView are prewarmed once, hidden between operations,
    /// and receive a fresh context message for every capture save.
    /// </summary>
    internal sealed class CaptureFileBrowserWindow : Window
    {
        private readonly WebView2 _webView;
        private readonly TextBlock _metadata;
        private readonly Grid _loadingLayer;
        private TaskCompletionSource<bool> _pageReady = NewSignal<bool>();
        private TaskCompletionSource<CaptureFileBrowserResult> _pending;
        private Dictionary<string, object> _pendingContext;
        private string _allowedOrigin = "";
        private string _loadedOrigin = "";
        private bool _coreInitialized;
        private bool _allowClose;
        private bool _prewarmWindowShown;

        internal bool IsPageReady { get { return _pageReady.Task.IsCompleted; } }
        internal bool HasPendingOperation { get { return _pending != null; } }

        internal CaptureFileBrowserWindow()
        {
            Title = "Easycode 资源管理器";
            Width = 980;
            Height = 650;
            MinWidth = 820;
            MinHeight = 540;
            WindowStartupLocation = WindowStartupLocation.Manual;
            WindowStyle = WindowStyle.None;
            ResizeMode = ResizeMode.CanResizeWithGrip;
            ShowInTaskbar = false;
            ShowActivated = false;
            Topmost = true;
            Background = Brush("#1F2033");
            Foreground = Brush("#CFD3E6");

            Border shell = new Border
            {
                Background = Brush("#1F2033"), BorderBrush = Brush("#353757"), BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(10),
                Effect = new DropShadowEffect { Color = Colors.Black, BlurRadius = 28, ShadowDepth = 8, Opacity = 0.55 }
            };
            Grid root = new Grid();
            root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(42) });
            root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            shell.Child = root;

            Grid titleBar = new Grid { Background = Brush("#26283D") };
            titleBar.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            titleBar.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(42) });
            titleBar.MouseLeftButtonDown += delegate(object sender, MouseButtonEventArgs args)
            {
                if (args.ButtonState == MouseButtonState.Pressed) DragMove();
            };
            StackPanel heading = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                Margin = new Thickness(14, 0, 0, 0),
                VerticalAlignment = VerticalAlignment.Center
            };
            heading.Children.Add(LucideIcons.Create("folder-open", 17, "#4ED19C"));
            heading.Children.Add(new TextBlock
            {
                Text = "项目资源管理器", FontSize = 13, FontWeight = FontWeights.SemiBold,
                Foreground = Brushes.White, Margin = new Thickness(8, 0, 8, 0), VerticalAlignment = VerticalAlignment.Center
            });
            _metadata = new TextBlock
            {
                FontSize = 11, Foreground = Brush("#8C8FA8"), VerticalAlignment = VerticalAlignment.Center
            };
            heading.Children.Add(_metadata);
            titleBar.Children.Add(heading);

            Button close = new Button
            {
                Width = 30, Height = 28, Margin = new Thickness(0, 0, 6, 0),
                HorizontalAlignment = HorizontalAlignment.Right, VerticalAlignment = VerticalAlignment.Center,
                Background = Brushes.Transparent, BorderBrush = Brushes.Transparent,
                Content = LucideIcons.Create("x", 16, "#CFD3E6"), Cursor = Cursors.Hand
            };
            close.Click += delegate { Complete(false, null, 0); };
            close.MouseEnter += delegate { close.Background = Brush("#3A2940"); };
            close.MouseLeave += delegate { close.Background = Brushes.Transparent; };
            Grid.SetColumn(close, 1);
            titleBar.Children.Add(close);
            root.Children.Add(titleBar);

            Grid content = new Grid();
            _webView = new WebView2 { Dock = System.Windows.Forms.DockStyle.Fill };
            content.Children.Add(new WindowsFormsHost { Child = _webView });
            _loadingLayer = new Grid { Background = Brush("#1F2033") };
            _loadingLayer.Children.Add(new TextBlock
            {
                Text = "正在准备项目资源管理器…", Foreground = Brush("#8C8FA8"), FontSize = 13,
                HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center
            });
            content.Children.Add(_loadingLayer);
            Grid.SetRow(content, 1);
            root.Children.Add(content);
            Content = shell;

            PreviewKeyDown += delegate(object sender, KeyEventArgs args)
            {
                if (args.Key == Key.Escape && HasPendingOperation)
                {
                    Complete(false, null, 0);
                    args.Handled = true;
                }
            };
            Closing += delegate(object sender, System.ComponentModel.CancelEventArgs args)
            {
                if (_allowClose) return;
                args.Cancel = true;
                Complete(false, null, 0);
            };
        }

        internal async Task<bool> PrewarmAsync(string origin)
        {
            if (String.IsNullOrWhiteSpace(origin)) return false;
            origin = origin.TrimEnd('/');
            try
            {
                EnsureWindowHandleForPrewarm();
                if (!_coreInitialized)
                {
                    CoreWebView2Environment environment = await WebViewEnvironmentProvider.GetAsync();
                    await _webView.EnsureCoreWebView2Async(environment);
                    ConfigureCore();
                    _coreInitialized = true;
                }
                if (!String.Equals(_loadedOrigin, origin, StringComparison.OrdinalIgnoreCase))
                {
                    _allowedOrigin = origin;
                    _loadedOrigin = origin;
                    _pageReady = NewSignal<bool>();
                    _loadingLayer.Visibility = Visibility.Visible;
                    _webView.Source = new Uri(origin + "/capture.html");
                }
                Task completed = await Task.WhenAny(_pageReady.Task, Task.Delay(8000));
                bool ready = completed == _pageReady.Task && _pageReady.Task.Result;
                if (ready) _loadingLayer.Visibility = Visibility.Collapsed;
                if (!HasPendingOperation && IsVisible) Hide();
                return ready;
            }
            catch
            {
                if (!HasPendingOperation && IsVisible) Hide();
                return false;
            }
        }

        internal async Task<CaptureFileBrowserResult> OpenAsync(
            Window owner,
            string origin,
            Dictionary<string, object> context,
            string category,
            int count)
        {
            if (HasPendingOperation) throw new InvalidOperationException("资源管理器已有正在处理的保存操作");
            bool ready = await PrewarmAsync(origin);
            if (!ready) throw new InvalidOperationException("项目资源管理器预热失败，请检查 WebView2 运行环境");

            _metadata.Text = "· " + category + (count > 1 ? " · " + count + " 个范围" : "");
            _pending = NewSignal<CaptureFileBrowserResult>();
            _pendingContext = context;
            PositionOver(owner);
            ShowActivated = true;
            if (!IsVisible) Show();
            Activate();
            Focus();
            if (owner != null) owner.IsEnabled = false;
            SendContext();

            CaptureFileBrowserResult result;
            try { result = await _pending.Task; }
            finally
            {
                if (owner != null)
                {
                    owner.IsEnabled = true;
                    owner.Activate();
                }
            }
            return result;
        }

        internal void CancelPending()
        {
            if (HasPendingOperation) Complete(false, null, 0);
        }

        internal void Shutdown()
        {
            _allowClose = true;
            CancelPending();
            try { _webView.Dispose(); } catch { }
            try { Close(); } catch { }
        }

        private void EnsureWindowHandleForPrewarm()
        {
            if (_prewarmWindowShown) return;
            _prewarmWindowShown = true;
            ShowActivated = false;
            Opacity = 0;
            Left = -32000;
            Top = -32000;
            Width = 820;
            Height = 540;
            Show();
        }

        private void ConfigureCore()
        {
            CoreWebView2Settings settings = _webView.CoreWebView2.Settings;
            settings.AreDevToolsEnabled = false;
            settings.AreDefaultContextMenusEnabled = false;
            settings.IsStatusBarEnabled = false;
            settings.IsZoomControlEnabled = false;
            _webView.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
            _webView.CoreWebView2.NavigationStarting += delegate(object sender, CoreWebView2NavigationStartingEventArgs args)
            {
                Uri target;
                if (!Uri.TryCreate(args.Uri, UriKind.Absolute, out target) ||
                    !String.Equals(target.GetLeftPart(UriPartial.Authority), _allowedOrigin, StringComparison.OrdinalIgnoreCase))
                    args.Cancel = true;
            };
            _webView.CoreWebView2.ProcessFailed += delegate
            {
                _pageReady = NewSignal<bool>();
                if (HasPendingOperation) Complete(false, null, 0);
            };
        }

        private void OnWebMessageReceived(object sender, CoreWebView2WebMessageReceivedEventArgs args)
        {
            Dictionary<string, object> message;
            try { message = JsonUtil.Parse(args.WebMessageAsJson); }
            catch { return; }
            string kind = JsonUtil.String(message, "event", "");
            if (kind == "capture-file-manager-ready")
            {
                _pageReady.TrySetResult(true);
                _loadingLayer.Visibility = Visibility.Collapsed;
                SendContext();
                return;
            }
            if (kind == "capture-save-cancel")
            {
                Complete(false, null, 0);
                return;
            }
            if (kind != "capture-save-complete") return;
            Dictionary<string, object> result = JsonUtil.Object(message, "result");
            if (result != null) Complete(true, result, JsonUtil.Int(message, "file_count", 0));
        }

        private void SendContext()
        {
            if (!_coreInitialized || !IsPageReady || _pendingContext == null) return;
            _webView.CoreWebView2.PostWebMessageAsJson(JsonUtil.Serialize(new Dictionary<string, object>
            {
                { "event", "capture-save-context" },
                { "version", 1 },
                { "context", _pendingContext }
            }));
            _pendingContext = null;
        }

        private void Complete(bool completed, Dictionary<string, object> actionResult, int fileCount)
        {
            TaskCompletionSource<CaptureFileBrowserResult> pending = _pending;
            if (pending == null) return;
            _pending = null;
            _pendingContext = null;
            Hide();
            pending.TrySetResult(new CaptureFileBrowserResult
            {
                Completed = completed,
                ActionResult = actionResult,
                FileCount = fileCount
            });
        }

        private void PositionOver(Window owner)
        {
            Width = Math.Max(MinWidth, 980);
            Height = Math.Max(MinHeight, 650);
            Opacity = 1;
            if (owner != null)
            {
                Left = owner.Left + Math.Max(0, (owner.ActualWidth - Width) / 2);
                Top = owner.Top + Math.Max(0, (owner.ActualHeight - Height) / 2);
            }
            else
            {
                Left = Math.Max(0, (SystemParameters.PrimaryScreenWidth - Width) / 2);
                Top = Math.Max(0, (SystemParameters.PrimaryScreenHeight - Height) / 2);
            }
        }

        private static TaskCompletionSource<T> NewSignal<T>()
        {
            return new TaskCompletionSource<T>();
        }

        private static SolidColorBrush Brush(string value)
        {
            return new SolidColorBrush((Color)ColorConverter.ConvertFromString(value));
        }
    }
}
