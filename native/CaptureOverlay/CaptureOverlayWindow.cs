using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using Forms = System.Windows.Forms;

namespace Easycode.CaptureOverlay
{
    internal sealed class CaptureRect
    {
        internal int X;
        internal int Y;
        internal int Width;
        internal int Height;
    }

    internal sealed class PortChoice
    {
        internal Dictionary<string, object> Data;
        public string Label { get; set; }
        public string Role { get; set; }
        public int Order { get; set; }
        public Brush MarkerBrush { get; set; }
        public override string ToString() { return Label; }
    }

    internal sealed class CaptureOverlayWindow : Window
    {
        private CapturePayload _payload;
        private readonly Forms.Screen _screen;
        private readonly Action _requestClose;
        private readonly CaptureFileBrowserWindow _resourceBrowser;
        private readonly CaptureApiClient _api;
        private readonly Canvas _root;
        private readonly Grid _captureGrid;
        private readonly Image _image;
        private readonly Canvas _drawing;
        private readonly Border _toolbar;
        private readonly ComboBox _portCombo;
        private readonly Button _clickButton;
        private readonly Button _imageButton;
        private readonly Button _ocrButton;
        private readonly Button _pageButton;
        private readonly Button _recordButton;
        private readonly Button _clearButton;
        private readonly Button _confirmButton;
        private readonly Label _status;
        private readonly string _hostSnapshotId;
        private readonly string _chainId;
        private readonly List<CaptureRect> _rectangles = new List<CaptureRect>();
        private readonly List<PortChoice> _ports = new List<PortChoice>();
        private System.Windows.Point? _point;
        private System.Windows.Point? _dragStart;
        private CaptureRect _draft;
        private bool _appendDraft;
        private bool _moved;
        private int _activeRect = -1;
        private bool _busy;
        private bool _closing;
        private bool _fieldCompleted;
        private int _operationSerial;
        private readonly Dictionary<string, object> _fieldCapture;
        private readonly bool _fieldMode;
        private readonly string _fieldSelectionMode;
        private readonly string _fieldCategory;
        private readonly string _fieldRequestId;
        private readonly int _fieldMaxRects;

        internal string SnapshotId { get { return _hostSnapshotId; } }

        internal CaptureOverlayWindow(
            CapturePayload payload,
            Forms.Screen screen,
            CaptureFileBrowserWindow resourceBrowser,
            Action requestClose)
        {
            _payload = payload;
            _screen = screen;
            _resourceBrowser = resourceBrowser;
            _requestClose = requestClose;
            _hostSnapshotId = payload.SnapshotId;
            _chainId = payload.SnapshotId;
            _api = new CaptureApiClient(payload.Origin);
            _fieldCapture = JsonUtil.Object(payload.CaptureContext, "fieldCapture");
            _fieldMode = _fieldCapture != null;
            _fieldSelectionMode = JsonUtil.String(_fieldCapture, "selectionMode", "");
            _fieldCategory = JsonUtil.String(_fieldCapture, "category", "image");
            _fieldRequestId = JsonUtil.String(_fieldCapture, "requestId", "");
            _fieldMaxRects = Math.Max(1, Math.Min(32, JsonUtil.Int(_fieldCapture, "maxRects", 1)));

            WindowStyle = WindowStyle.None;
            ResizeMode = ResizeMode.NoResize;
            ShowInTaskbar = false;
            Topmost = true;
            AllowsTransparency = true;
            Background = Brush("#C0080B10");
            Foreground = Brush("#E8EDF5");
            Focusable = true;
            Title = "Easycode 原生捕获";

            _root = new Canvas { Background = Brush("#C0080B10"), ClipToBounds = true };
            Content = _root;

            _image = new Image { Stretch = Stretch.Fill, SnapsToDevicePixels = true };
            RenderOptions.SetBitmapScalingMode(_image, BitmapScalingMode.HighQuality);
            _drawing = new Canvas { Background = Brushes.Transparent, Cursor = Cursors.Cross };
            _captureGrid = new Grid { Background = Brushes.Transparent, ClipToBounds = true };
            _captureGrid.Children.Add(_image);
            _captureGrid.Children.Add(_drawing);
            Border frame = new Border
            {
                BorderBrush = Brush("#4ED19C"), BorderThickness = new Thickness(2),
                Child = _captureGrid,
                Effect = new DropShadowEffect { Color = Color.FromRgb(78, 209, 156), BlurRadius = 18, ShadowDepth = 0, Opacity = 0.9 }
            };
            _root.Children.Add(frame);

            Border chip = new Border
            {
                Background = Brush("#E626283D"), CornerRadius = new CornerRadius(5), Padding = new Thickness(9, 4, 9, 4),
                Child = new TextBlock
                {
                    Text = "●  " + (_fieldMode ? JsonUtil.String(_fieldCapture, "title", "属性捕获") : "捕获中") + " · " + payload.ProjectName + (String.IsNullOrWhiteSpace(payload.TargetName) ? "" : " · " + payload.TargetName),
                    Foreground = Brush("#D7F8EB"), FontSize = 11
                }
            };
            _root.Children.Add(chip);

            StackPanel tools = new StackPanel { Orientation = Orientation.Horizontal, VerticalAlignment = VerticalAlignment.Center };
            _portCombo = new ComboBox
            {
                Width = 112, Height = 30, Margin = new Thickness(0, 0, 4, 0), ToolTip = "上游节点端口",
                Background = Brush("#181926"), Foreground = Brush("#CFD3E6"), BorderBrush = Brush("#313352"),
                BorderThickness = new Thickness(1), Padding = new Thickness(7, 2, 5, 2), FontSize = 11,
                ItemTemplate = CreatePortTemplate()
            };
            _clickButton = ToolButton("crosshair", "生成点击节点 (1)", delegate { CreateClick(); });
            _imageButton = ToolButton("image", "生成图像识别节点 (2)", delegate { OpenSaveManager("image"); });
            _ocrButton = ToolButton("scan-text", "生成 OCR 节点 (3)", delegate { OpenSaveManager("ocr"); });
            _pageButton = ToolButton("layers", "生成页面节点 (4)", delegate { OpenSaveManager("page"); });
            _recordButton = ToolButton("download", "录入图像资源 (5)", delegate { OpenSaveManager("record"); });
            _clearButton = ToolButton("trash", "清空点和框选 (Delete)", delegate { ClearSelection(); });
            Button exit = ToolButton("x", "退出捕获 (Esc)", delegate { CloseAsync(); }, "#FF6B81");
            _confirmButton = ToolButton("check", "确认并回填 (Enter)", delegate { ConfirmFieldCapture(); }, "#4ED19C");
            if (_fieldMode)
            {
                tools.Children.Add(_clearButton);
                tools.Children.Add(exit);
                tools.Children.Add(_confirmButton);
            }
            else
            {
                tools.Children.Add(_portCombo);
                tools.Children.Add(Separator());
                tools.Children.Add(_clickButton);
                tools.Children.Add(_imageButton);
                tools.Children.Add(_ocrButton);
                tools.Children.Add(_pageButton);
                tools.Children.Add(_recordButton);
                tools.Children.Add(Separator());
                tools.Children.Add(_clearButton);
                tools.Children.Add(exit);
            }
            _toolbar = new Border
            {
                Background = Brush("#F226283D"), BorderBrush = Brush("#313352"), BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(8), Padding = new Thickness(4),
                Effect = new DropShadowEffect { Color = Colors.Black, BlurRadius = 18, ShadowDepth = 4, Opacity = 0.52 },
                Child = tools
            };
            _root.Children.Add(_toolbar);

            _status = new Label
            {
                Visibility = Visibility.Collapsed, Background = Brush("#E31B2028"), Foreground = Brushes.White,
                Padding = new Thickness(12, 7, 12, 7), FontSize = 12
            };
            _root.Children.Add(_status);

            LoadPorts(payload.CaptureContext, null);
            LoadImageFile(payload.SnapshotPath);
            SourceInitialized += delegate { NativeMethods.Place(this, _screen); };
            Loaded += delegate { LayoutOverlay(frame, chip); FocusOverlay(); };
            SizeChanged += delegate { LayoutToolbar(); };
            KeyDown += OnKeyDown;
            PreviewMouseDown += delegate(object sender, MouseButtonEventArgs args)
            {
                if (!_captureGrid.IsMouseOver && !_toolbar.IsMouseOver) args.Handled = true;
            };
            _captureGrid.MouseLeftButtonDown += CaptureMouseDown;
            _captureGrid.MouseMove += CaptureMouseMove;
            _captureGrid.MouseLeftButtonUp += CaptureMouseUp;
            _captureGrid.LostMouseCapture += delegate { _dragStart = null; _draft = null; Redraw(); };
            UpdateButtons();
        }

        private static SolidColorBrush Brush(string value)
        {
            return new SolidColorBrush((Color)ColorConverter.ConvertFromString(value));
        }

        private static Border Separator()
        {
            return new Border { Width = 1, Height = 20, Margin = new Thickness(4, 0, 4, 0), Background = Brush("#313352") };
        }

        private static DataTemplate CreatePortTemplate()
        {
            FrameworkElementFactory row = new FrameworkElementFactory(typeof(StackPanel));
            row.SetValue(StackPanel.OrientationProperty, Orientation.Horizontal);
            row.SetValue(FrameworkElement.VerticalAlignmentProperty, VerticalAlignment.Center);

            FrameworkElementFactory marker = new FrameworkElementFactory(typeof(Border));
            marker.SetValue(FrameworkElement.WidthProperty, 17.0);
            marker.SetValue(FrameworkElement.HeightProperty, 17.0);
            marker.SetValue(Border.CornerRadiusProperty, new CornerRadius(9));
            marker.SetValue(FrameworkElement.MarginProperty, new Thickness(0, 0, 6, 0));
            marker.SetBinding(Border.BackgroundProperty, new Binding("MarkerBrush"));
            FrameworkElementFactory number = new FrameworkElementFactory(typeof(TextBlock));
            number.SetBinding(TextBlock.TextProperty, new Binding("Order"));
            number.SetValue(TextBlock.ForegroundProperty, Brushes.White);
            number.SetValue(TextBlock.FontSizeProperty, 10.0);
            number.SetValue(TextBlock.FontWeightProperty, FontWeights.Bold);
            number.SetValue(TextBlock.TextAlignmentProperty, TextAlignment.Center);
            number.SetValue(FrameworkElement.VerticalAlignmentProperty, VerticalAlignment.Center);
            marker.AppendChild(number);
            row.AppendChild(marker);

            FrameworkElementFactory label = new FrameworkElementFactory(typeof(TextBlock));
            label.SetBinding(TextBlock.TextProperty, new Binding("Label"));
            label.SetValue(TextBlock.ForegroundProperty, Brush("#CFD3E6"));
            label.SetValue(TextBlock.FontSizeProperty, 11.0);
            label.SetValue(FrameworkElement.VerticalAlignmentProperty, VerticalAlignment.Center);
            row.AppendChild(label);
            return new DataTemplate(typeof(PortChoice)) { VisualTree = row };
        }

        private Button ToolButton(string icon, string tooltip, RoutedEventHandler click, string color = "#CFD3E6")
        {
            Button button = new Button
            {
                Content = LucideIcons.Create(icon, 17, color), ToolTip = tooltip,
                Width = 32, Height = 30, Margin = new Thickness(1, 0, 1, 0),
                Background = Brushes.Transparent, BorderBrush = Brushes.Transparent, BorderThickness = new Thickness(1),
                Padding = new Thickness(6), Cursor = Cursors.Hand, Opacity = 1
            };
            button.Click += click;
            button.MouseEnter += delegate
            {
                if (!button.IsEnabled) return;
                button.Background = Brush("#1D1E30");
                button.BorderBrush = Brush("#3A3D5E");
            };
            button.MouseLeave += delegate
            {
                button.Background = Brushes.Transparent;
                button.BorderBrush = Brushes.Transparent;
            };
            button.IsEnabledChanged += delegate { button.Opacity = button.IsEnabled ? 1 : 0.32; };
            return button;
        }

        private void LayoutOverlay(Border frame, Border chip)
        {
            Matrix fromDevice = PresentationSource.FromVisual(this).CompositionTarget.TransformFromDevice;
            double x = (_payload.Left - _screen.Bounds.Left) * fromDevice.M11;
            double y = (_payload.Top - _screen.Bounds.Top) * fromDevice.M22;
            double width = (_payload.Right - _payload.Left) * fromDevice.M11;
            double height = (_payload.Bottom - _payload.Top) * fromDevice.M22;
            frame.Width = Math.Max(1, width);
            frame.Height = Math.Max(1, height);
            Canvas.SetLeft(frame, x);
            Canvas.SetTop(frame, y);
            Canvas.SetLeft(chip, x + 8);
            Canvas.SetTop(chip, y + 8);
            _captureGrid.Width = frame.Width - 4;
            _captureGrid.Height = frame.Height - 4;
            LayoutToolbar();
            Canvas.SetLeft(_status, Math.Max(8, x + 8));
            Canvas.SetTop(_status, Math.Max(8, y + height - 42));
        }

        private void LayoutToolbar()
        {
            if (!IsLoaded || _toolbar.ActualWidth <= 0) return;
            Matrix fromDevice = PresentationSource.FromVisual(this).CompositionTarget.TransformFromDevice;
            double x = (_payload.Left - _screen.Bounds.Left) * fromDevice.M11;
            double y = (_payload.Top - _screen.Bounds.Top) * fromDevice.M22;
            double width = (_payload.Right - _payload.Left) * fromDevice.M11;
            double height = (_payload.Bottom - _payload.Top) * fromDevice.M22;
            double toolbarX = Math.Max(6, Math.Min(ActualWidth - _toolbar.ActualWidth - 6, x + (width - _toolbar.ActualWidth) / 2));
            double below = y + height + 8;
            double toolbarY = below + _toolbar.ActualHeight <= ActualHeight - 6
                ? below : Math.Max(y + 6, y + height - _toolbar.ActualHeight - 10);
            Canvas.SetLeft(_toolbar, toolbarX);
            Canvas.SetTop(_toolbar, toolbarY);
        }

        private void LoadImageFile(string path)
        {
            using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                BitmapImage bitmap = new BitmapImage();
                bitmap.BeginInit();
                bitmap.CacheOption = BitmapCacheOption.OnLoad;
                bitmap.StreamSource = stream;
                bitmap.EndInit();
                bitmap.Freeze();
                _image.Source = bitmap;
            }
        }

        private void LoadImageBytes(byte[] bytes)
        {
            using (MemoryStream stream = new MemoryStream(bytes))
            {
                BitmapImage bitmap = new BitmapImage();
                bitmap.BeginInit();
                bitmap.CacheOption = BitmapCacheOption.OnLoad;
                bitmap.StreamSource = stream;
                bitmap.EndInit();
                bitmap.Freeze();
                _image.Source = bitmap;
            }
        }

        internal void FocusOverlay()
        {
            if (!IsVisible) return;
            Activate();
            Focus();
            Keyboard.Focus(this);
            try { NativeMethods.SetForegroundWindow(new WindowInteropHelper(this).Handle); } catch { }
        }

        private System.Windows.Point PixelPoint(MouseEventArgs args)
        {
            System.Windows.Point point = args.GetPosition(_captureGrid);
            int x = (int)Math.Round(point.X * _payload.Width / Math.Max(1, _captureGrid.ActualWidth));
            int y = (int)Math.Round(point.Y * _payload.Height / Math.Max(1, _captureGrid.ActualHeight));
            return new System.Windows.Point(Clamp(x, 0, _payload.Width - 1), Clamp(y, 0, _payload.Height - 1));
        }

        private static int Clamp(int value, int min, int max) { return Math.Max(min, Math.Min(max, value)); }

        private void CaptureMouseDown(object sender, MouseButtonEventArgs args)
        {
            if (_busy) return;
            FocusOverlay();
            _dragStart = PixelPoint(args);
            _appendDraft = Keyboard.Modifiers.HasFlag(ModifierKeys.Shift) && (!_fieldMode || _fieldMaxRects > 1);
            _moved = false;
            _draft = new CaptureRect { X = (int)_dragStart.Value.X, Y = (int)_dragStart.Value.Y, Width = 1, Height = 1 };
            _captureGrid.CaptureMouse();
            args.Handled = true;
        }

        private void CaptureMouseMove(object sender, MouseEventArgs args)
        {
            if (_busy || !_dragStart.HasValue || args.LeftButton != MouseButtonState.Pressed) return;
            System.Windows.Point current = PixelPoint(args);
            int dx = (int)Math.Abs(current.X - _dragStart.Value.X);
            int dy = (int)Math.Abs(current.Y - _dragStart.Value.Y);
            if (!_moved && Math.Sqrt(dx * dx + dy * dy) < 3) return;
            _moved = true;
            _draft.X = (int)Math.Min(current.X, _dragStart.Value.X);
            _draft.Y = (int)Math.Min(current.Y, _dragStart.Value.Y);
            _draft.Width = Math.Max(1, dx);
            _draft.Height = Math.Max(1, dy);
            Redraw();
        }

        private void CaptureMouseUp(object sender, MouseButtonEventArgs args)
        {
            if (!_dragStart.HasValue) return;
            System.Windows.Point click = PixelPoint(args);
            if (_fieldMode && _fieldSelectionMode == "point")
            {
                _point = click;
                _rectangles.Clear();
                _activeRect = -1;
            }
            else if (_moved && _draft != null && _draft.Width > 0 && _draft.Height > 0)
            {
                if (!_appendDraft) _rectangles.Clear();
                if (!_fieldMode || _rectangles.Count < _fieldMaxRects) _rectangles.Add(_draft);
                _activeRect = _rectangles.Count - 1;
                _point = null;
            }
            else
            {
                int hit = -1;
                for (int i = _rectangles.Count - 1; i >= 0; i--)
                {
                    CaptureRect rect = _rectangles[i];
                    if (click.X >= rect.X && click.X <= rect.X + rect.Width && click.Y >= rect.Y && click.Y <= rect.Y + rect.Height)
                    { hit = i; break; }
                }
                if (hit >= 0) _activeRect = hit;
                else
                {
                    _point = click;
                    _rectangles.Clear();
                    _activeRect = -1;
                }
            }
            _dragStart = null;
            _draft = null;
            _captureGrid.ReleaseMouseCapture();
            Redraw();
            UpdateButtons();
            args.Handled = true;
        }

        private void Redraw()
        {
            _drawing.Children.Clear();
            for (int i = 0; i < _rectangles.Count; i++) DrawRect(_rectangles[i], i, i == _activeRect, false);
            if (_draft != null && _moved) DrawRect(_draft, -1, true, true);
            if (_point.HasValue)
            {
                double x = _point.Value.X * _drawing.ActualWidth / _payload.Width;
                double y = _point.Value.Y * _drawing.ActualHeight / _payload.Height;
                Ellipse dot = new Ellipse { Width = 10, Height = 10, Fill = Brush("#FF5964"), Stroke = Brushes.White, StrokeThickness = 1 };
                Canvas.SetLeft(dot, x - 5); Canvas.SetTop(dot, y - 5); _drawing.Children.Add(dot);
                Line h = new Line { X1 = x - 12, X2 = x + 12, Y1 = y, Y2 = y, Stroke = Brush("#FF5964"), StrokeThickness = 1.5 };
                Line v = new Line { X1 = x, X2 = x, Y1 = y - 12, Y2 = y + 12, Stroke = Brush("#FF5964"), StrokeThickness = 1.5 };
                _drawing.Children.Add(h); _drawing.Children.Add(v);
            }
        }

        private void DrawRect(CaptureRect rect, int index, bool active, bool draft)
        {
            double x = rect.X * _drawing.ActualWidth / _payload.Width;
            double y = rect.Y * _drawing.ActualHeight / _payload.Height;
            double width = Math.Max(1, rect.Width * _drawing.ActualWidth / _payload.Width);
            double height = Math.Max(1, rect.Height * _drawing.ActualHeight / _payload.Height);
            Rectangle shape = new Rectangle
            {
                Width = width, Height = height, Fill = Brush(active ? "#1839A9FF" : "#142FDF9A"),
                Stroke = Brush(active ? "#39A9FF" : "#45D7A0"), StrokeThickness = active ? 2 : 1.5,
                StrokeDashArray = draft ? new DoubleCollection { 4, 3 } : null
            };
            Canvas.SetLeft(shape, x); Canvas.SetTop(shape, y); _drawing.Children.Add(shape);
            if (index >= 0)
            {
                Border badge = new Border
                {
                    Width = 20, Height = 20, CornerRadius = new CornerRadius(10), Background = shape.Stroke,
                    Child = new TextBlock { Text = Convert.ToString(index + 1), Foreground = Brushes.White, FontWeight = FontWeights.Bold, FontSize = 11, TextAlignment = TextAlignment.Center, VerticalAlignment = VerticalAlignment.Center }
                };
                Canvas.SetLeft(badge, x + 4); Canvas.SetTop(badge, y + 4); _drawing.Children.Add(badge);
            }
            if (active && !draft)
            {
                double[,] handles = { { x, y }, { x + width / 2, y }, { x + width, y }, { x, y + height / 2 }, { x + width, y + height / 2 }, { x, y + height }, { x + width / 2, y + height }, { x + width, y + height } };
                for (int i = 0; i < 8; i++)
                {
                    Ellipse handle = new Ellipse { Width = 8, Height = 8, Fill = Brushes.White, Stroke = Brush("#39A9FF"), StrokeThickness = 1.5 };
                    Canvas.SetLeft(handle, handles[i, 0] - 4); Canvas.SetTop(handle, handles[i, 1] - 4); _drawing.Children.Add(handle);
                }
            }
        }

        private void ClearSelection()
        {
            _point = null;
            _rectangles.Clear();
            _activeRect = -1;
            _draft = null;
            Redraw();
            UpdateButtons();
        }

        private void UpdateButtons()
        {
            bool topology = JsonUtil.String(_payload.CaptureContext, "canvasMode", JsonUtil.String(_payload.CaptureContext, "canvas_mode", "")) == "topology";
            _clickButton.IsEnabled = !_busy && _point.HasValue;
            _imageButton.IsEnabled = !_busy && _rectangles.Count == 1;
            _ocrButton.IsEnabled = !_busy && _rectangles.Count == 1;
            _pageButton.IsEnabled = !_busy && topology && _rectangles.Count > 0;
            _recordButton.IsEnabled = !_busy && _rectangles.Count > 0;
            _clearButton.IsEnabled = !_busy && (_point.HasValue || _rectangles.Count > 0);
            _portCombo.IsEnabled = !_busy && _ports.Count > 0;
            _confirmButton.IsEnabled = !_busy && (_fieldSelectionMode == "point"
                ? _point.HasValue
                : (_fieldSelectionMode == "region" ? _rectangles.Count == 1 : _rectangles.Count > 0));
        }

        private void SetBusy(bool value, string message)
        {
            _busy = value;
            _status.Content = message ?? "";
            _status.Visibility = value ? Visibility.Visible : Visibility.Collapsed;
            Cursor = value ? Cursors.Wait : Cursors.Arrow;
            UpdateButtons();
        }

        private void LoadPorts(Dictionary<string, object> context, Dictionary<string, object> preferred)
        {
            _ports.Clear();
            object[] values = JsonUtil.Array(context, "ports") ?? new object[0];
            foreach (object value in values)
            {
                Dictionary<string, object> data = value as Dictionary<string, object>;
                if (data == null) continue;
                _ports.Add(new PortChoice
                {
                    Data = data,
                    Label = JsonUtil.String(data, "label", "出口"),
                    Role = JsonUtil.String(data, "role", "success"),
                    Order = JsonUtil.Int(data, "order", _ports.Count + 1),
                    MarkerBrush = Brush(JsonUtil.String(data, "role", "success") == "failure" ? "#E9576B" : "#35B982")
                });
            }
            _portCombo.ItemsSource = null;
            _portCombo.ItemsSource = _ports;
            PortChoice selected = null;
            string stableId = preferred == null ? "" : JsonUtil.String(preferred, "stableId", "");
            if (!String.IsNullOrEmpty(stableId)) selected = _ports.FirstOrDefault(port => JsonUtil.String(port.Data, "stableId", "") == stableId);
            if (selected == null) selected = _ports.FirstOrDefault(port => port.Role != "failure") ?? _ports.FirstOrDefault();
            _portCombo.SelectedItem = selected;
            _portCombo.Visibility = _ports.Count > 0 ? Visibility.Visible : Visibility.Collapsed;
        }

        private Dictionary<string, object> BaseAction(string kind)
        {
            PortChoice selected = _portCombo.SelectedItem as PortChoice;
            _operationSerial += 1;
            return new Dictionary<string, object>
            {
                { "session_id", _payload.SessionId },
                { "snapshot_id", _payload.SnapshotId },
                { "capture_chain_id", _chainId },
                { "capture_context", _payload.CaptureContext },
                { "reference_size", new object[] { _payload.Width, _payload.Height } },
                { "port", selected == null ? null : selected.Data },
                { "operation_id", kind == "undo" ? "" : "capture_native_" + DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() + "_" + _operationSerial },
                { "kind", kind }
            };
        }

        private static bool IsOk(Dictionary<string, object> result)
        {
            object value;
            return result != null && result.TryGetValue("ok", out value) && value is bool && (bool)value;
        }

        private async Task<Dictionary<string, object>> RequestActionAsync(Dictionary<string, object> payload)
        {
            Dictionary<string, object> result = await _api.PostAsync("/api/capture/action", payload);
            if (!IsOk(result)) throw new InvalidOperationException(JsonUtil.String(result, "message", "捕获操作失败"));
            return result;
        }

        private void ApplyCommit(Dictionary<string, object> result)
        {
            Dictionary<string, object> nextContext = new Dictionary<string, object>(_payload.CaptureContext);
            object ports;
            if (result.TryGetValue("ports", out ports)) nextContext["ports"] = ports;
            _payload.CaptureContext = nextContext;
            LoadPorts(nextContext, JsonUtil.Object(result, "selectedPort"));
            ClearSelection();
        }

        private async void CreateClick()
        {
            if (_busy || !_point.HasValue) return;
            SetBusy(true, "正在生成点击节点…");
            try
            {
                Dictionary<string, object> action = BaseAction("click");
                action["point"] = new object[] { (int)_point.Value.X, (int)_point.Value.Y };
                Dictionary<string, object> result = await RequestActionAsync(action);
                ApplyCommit(result);
                ShowNotice("点击节点已生成");
            }
            catch (Exception ex) { MessageBox.Show(this, ex.Message, "点击节点生成失败", MessageBoxButton.OK, MessageBoxImage.Error); }
            finally { SetBusy(false, ""); FocusOverlay(); }
        }

        private async void ConfirmFieldCapture()
        {
            if (!_fieldMode || _busy || !_confirmButton.IsEnabled) return;
            if (_fieldSelectionMode == "asset")
            {
                OpenSaveManager("field_confirm");
                return;
            }
            SetBusy(true, "正在回填属性…");
            bool closeAfter = false;
            try
            {
                Dictionary<string, object> action = BaseAction("field_confirm");
                action["field_request_id"] = _fieldRequestId;
                if (_fieldSelectionMode == "point")
                    action["point"] = new object[] { (int)_point.Value.X, (int)_point.Value.Y };
                else
                    action["rects"] = _rectangles.Select(rect => (object)new object[] { rect.X, rect.Y, rect.Width, rect.Height }).ToArray();
                await RequestActionAsync(action);
                _fieldCompleted = true;
                closeAfter = true;
            }
            catch (Exception ex) { MessageBox.Show(this, ex.Message, "属性回填失败", MessageBoxButton.OK, MessageBoxImage.Error); }
            finally
            {
                SetBusy(false, "");
                if (closeAfter) CloseAsync(); else FocusOverlay();
            }
        }

        private async void OpenSaveManager(string kind)
        {
            if (_busy) return;
            if (kind == "page" && _rectangles.Count > 8 && MessageBox.Show(this,
                "当前页面包含 " + _rectangles.Count + " 个特征，可能增加识别耗时。仍要继续吗？",
                "性能提示", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes) return;
            bool fieldSave = kind == "field_confirm";
            string category = fieldSave ? _fieldCategory : (kind == "record" ? "image" : kind);
            SetBusy(true, "正在打开项目资源管理器…");
            bool closeAfter = false;
            try
            {
                Dictionary<string, object> action = BaseAction(kind);
                if (fieldSave) action["field_request_id"] = _fieldRequestId;
                object[] rects = _rectangles.Select(rect => (object)new object[] { rect.X, rect.Y, rect.Width, rect.Height }).ToArray();
                Dictionary<string, object> context = new Dictionary<string, object>
                {
                    { "snapshot_id", _payload.SnapshotId },
                    { "kind", kind },
                    { "chain_id", _chainId },
                    { "operation_id", Convert.ToString(action["operation_id"]) },
                    { "rects", rects },
                    { "port", action["port"] },
                    { "category", category },
                    { "field_request_id", fieldSave ? _fieldRequestId : "" }
                };
                CaptureFileBrowserResult result = await _resourceBrowser.OpenAsync(
                    this, _payload.Origin, context, category, _rectangles.Count);
                if (result.Completed && result.ActionResult != null)
                {
                    if (fieldSave)
                    {
                        _fieldCompleted = true;
                        closeAfter = true;
                    }
                    else
                    {
                        ApplyCommit(result.ActionResult);
                        ShowNotice(kind == "record" ? "已录入 " + result.FileCount + " 个资源" : "捕获节点已生成");
                    }
                }
            }
            catch (Exception ex) { MessageBox.Show(this, ex.Message, "资源保存失败", MessageBoxButton.OK, MessageBoxImage.Error); }
            finally
            {
                SetBusy(false, "");
                if (closeAfter) CloseAsync(); else FocusOverlay();
            }
        }

        private async void UndoLast()
        {
            if (_busy) return;
            SetBusy(true, "正在撤销最近一次捕获操作…");
            try
            {
                Dictionary<string, object> result = await RequestActionAsync(BaseAction("undo"));
                string transaction = JsonUtil.String(result, "undo_asset_transaction", "");
                if (!String.IsNullOrEmpty(transaction))
                    await _api.PostAsync("/api/capture/assets/undo", new Dictionary<string, object> { { "transaction_id", transaction } });
                Dictionary<string, object> nextContext = new Dictionary<string, object>(_payload.CaptureContext);
                object ports;
                if (result.TryGetValue("ports", out ports)) nextContext["ports"] = ports;
                _payload.CaptureContext = nextContext;
                LoadPorts(nextContext, JsonUtil.Object(result, "selectedPort"));
                ShowNotice("已撤销最近一次捕获操作");
            }
            catch (Exception ex) { MessageBox.Show(this, ex.Message, "无法撤销", MessageBoxButton.OK, MessageBoxImage.Information); }
            finally { SetBusy(false, ""); FocusOverlay(); }
        }

        private async void RefreshSnapshot()
        {
            if (_busy) return;
            SetBusy(true, "正在重新获取工作面板…");
            try
            {
                Dictionary<string, object> response = await _api.PostAsync("/api/capture/snapshot", new Dictionary<string, object>
                {
                    { "project_path", _payload.ProjectPath }, { "session_id", _payload.SessionId }
                });
                int width = JsonUtil.Int(response, "width", _payload.Width);
                int height = JsonUtil.Int(response, "height", _payload.Height);
                object[] region = JsonUtil.Array(response, "region");
                if (width != _payload.Width || height != _payload.Height || region == null || region.Length != 4 ||
                    Convert.ToInt32(region[0]) != _payload.Left || Convert.ToInt32(region[1]) != _payload.Top ||
                    Convert.ToInt32(region[2]) != _payload.Right || Convert.ToInt32(region[3]) != _payload.Bottom)
                    throw new InvalidOperationException("工作面板的位置或尺寸已经变化。请按 Esc 退出后重新进入捕获，以重新对齐。 ");
                string base64 = JsonUtil.String(response, "image", "");
                LoadImageBytes(Convert.FromBase64String(base64));
                _payload.SnapshotId = JsonUtil.String(response, "snapshot_id", _payload.SnapshotId);
                ClearSelection();
                ShowNotice("冻结帧已刷新");
            }
            catch (Exception ex) { MessageBox.Show(this, ex.Message, "刷新失败", MessageBoxButton.OK, MessageBoxImage.Warning); }
            finally { SetBusy(false, ""); FocusOverlay(); }
        }

        private async void CloseAsync()
        {
            if (_busy || _closing) return;
            _closing = true;
            if (_fieldMode && !_fieldCompleted)
            {
                try
                {
                    Dictionary<string, object> cancel = BaseAction("field_cancel");
                    cancel["field_request_id"] = _fieldRequestId;
                    await RequestActionAsync(cancel);
                }
                catch { }
            }
            try { await _api.PostAsync("/api/capture/close", new Dictionary<string, object> { { "snapshot_id", _payload.SnapshotId } }); }
            catch { }
            _requestClose();
        }

        internal void CloseFromHost()
        {
            if (!Dispatcher.CheckAccess()) { Dispatcher.BeginInvoke(new Action(CloseFromHost)); return; }
            _closing = true;
            try { _api.Dispose(); } catch { }
            try { Close(); } catch { }
        }

        private void ShowNotice(string message)
        {
            _status.Content = message;
            _status.Visibility = Visibility.Visible;
            System.Windows.Threading.DispatcherTimer timer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromSeconds(1.8) };
            timer.Tick += delegate { timer.Stop(); if (!_busy) _status.Visibility = Visibility.Collapsed; };
            timer.Start();
        }

        private void AdjustSelection(Key key, ModifierKeys modifiers)
        {
            int step = modifiers.HasFlag(ModifierKeys.Control) ? 10 : 1;
            int dx = key == Key.Left ? -step : key == Key.Right ? step : 0;
            int dy = key == Key.Up ? -step : key == Key.Down ? step : 0;
            if (_point.HasValue)
            {
                _point = new System.Windows.Point(Clamp((int)_point.Value.X + dx, 0, _payload.Width - 1), Clamp((int)_point.Value.Y + dy, 0, _payload.Height - 1));
            }
            else if (_activeRect >= 0 && _activeRect < _rectangles.Count)
            {
                CaptureRect rect = _rectangles[_activeRect];
                if (modifiers.HasFlag(ModifierKeys.Shift))
                {
                    if (dx != 0) rect.Width = Clamp(rect.Width + dx, 1, _payload.Width - rect.X);
                    if (dy != 0) rect.Height = Clamp(rect.Height + dy, 1, _payload.Height - rect.Y);
                }
                else
                {
                    rect.X = Clamp(rect.X + dx, 0, _payload.Width - rect.Width);
                    rect.Y = Clamp(rect.Y + dy, 0, _payload.Height - rect.Height);
                }
            }
            Redraw();
        }

        private void OnKeyDown(object sender, KeyEventArgs args)
        {
            if (_busy) return;
            ModifierKeys modifiers = Keyboard.Modifiers;
            if (args.Key == Key.Escape) { CloseAsync(); args.Handled = true; }
            else if (args.Key == Key.Delete) { ClearSelection(); args.Handled = true; }
            else if (_fieldMode && args.Key == Key.Enter) { if (_confirmButton.IsEnabled) ConfirmFieldCapture(); args.Handled = true; }
            else if (_fieldMode && (args.Key == Key.Z || args.Key == Key.R || args.Key == Key.D1 || args.Key == Key.D2 || args.Key == Key.D3 || args.Key == Key.D4 || args.Key == Key.D5)) { args.Handled = true; }
            else if (args.Key == Key.Z && modifiers.HasFlag(ModifierKeys.Control)) { UndoLast(); args.Handled = true; }
            else if (args.Key == Key.R && modifiers == ModifierKeys.None) { RefreshSnapshot(); args.Handled = true; }
            else if (args.Key == Key.Left || args.Key == Key.Right || args.Key == Key.Up || args.Key == Key.Down)
            { AdjustSelection(args.Key, modifiers); args.Handled = true; }
            else if (args.Key == Key.D1 || args.Key == Key.NumPad1) { if (_clickButton.IsEnabled) CreateClick(); args.Handled = true; }
            else if (args.Key == Key.D2 || args.Key == Key.NumPad2) { if (_imageButton.IsEnabled) OpenSaveManager("image"); args.Handled = true; }
            else if (args.Key == Key.D3 || args.Key == Key.NumPad3) { if (_ocrButton.IsEnabled) OpenSaveManager("ocr"); args.Handled = true; }
            else if (args.Key == Key.D4 || args.Key == Key.NumPad4) { if (_pageButton.IsEnabled) OpenSaveManager("page"); args.Handled = true; }
            else if (args.Key == Key.D5 || args.Key == Key.NumPad5) { if (_recordButton.IsEnabled) OpenSaveManager("record"); args.Handled = true; }
        }
    }
}
