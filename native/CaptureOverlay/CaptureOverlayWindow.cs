using System;
using System.Collections.Generic;
using System.IO;
using System.IO.MemoryMappedFiles;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using System.Windows.Threading;
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
        private readonly Border _frame;
        private readonly Grid _captureGrid;
        private readonly Image _image;
        private readonly Canvas _drawing;
        private readonly Canvas _cursorLayer;
        private readonly Grid _cursorMarker;
        private readonly TranslateTransform _cursorTransform;
        private readonly DispatcherTimer _cursorUpdateTimer;
        private readonly Border _toolbar;
        private readonly ComboBox _portCombo;
        private readonly Button _clickButton;
        private readonly Button _imageButton;
        private readonly Button _ocrButton;
        private readonly Button _pageButton;
        private readonly Button _recordButton;
        private readonly Button _clearButton;
        private readonly Button _parentButton;
        private readonly Button _confirmButton;
        private readonly Label _status;
        private readonly string _hostSnapshotId;
        private readonly string _chainId;
        private readonly List<CaptureRect> _rectangles = new List<CaptureRect>();
        private readonly List<System.Windows.Point> _pathPoints = new List<System.Windows.Point>();
        private readonly List<PortChoice> _ports = new List<PortChoice>();
        private readonly List<Dictionary<string, object>> _controlCandidates = new List<Dictionary<string, object>>();
        private System.Windows.Point? _pendingPointerPosition;
        private int _controlCandidateIndex = -1;
        private System.Windows.Point? _point;
        private System.Windows.Point? _dragStart;
        private CaptureRect _draft;
        private bool _appendDraft;
        private bool _moved;
        private int _activeRect = -1;
        private bool _busy;
        private bool _closing;
        private bool _fieldCompleted;
        private bool _pageWarningArmed;
        private int _operationSerial;
        private readonly Dictionary<string, object> _fieldCapture;
        private readonly bool _fieldMode;
        private readonly string _fieldSelectionMode;
        private readonly string _fieldCategory;
        private readonly string _fieldDestination;
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
            _fieldDestination = JsonUtil.String(_fieldCapture, "destination", "parameter");
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
            // The system crosshair uses inverse colors and can visibly alternate over a
            // changing snapshot. Keep one stable EasyCode pointer in the top overlay layer.
            _drawing = new Canvas { Background = Brushes.Transparent, Cursor = Cursors.None };
            _cursorLayer = new Canvas { Background = Brushes.Transparent, IsHitTestVisible = false };
            _cursorMarker = CreatePointerMarker();
            _cursorTransform = new TranslateTransform();
            _cursorMarker.RenderTransform = _cursorTransform;
            _cursorMarker.CacheMode = new BitmapCache();
            _cursorUpdateTimer = new DispatcherTimer(DispatcherPriority.Render)
            {
                Interval = TimeSpan.FromMilliseconds(16)
            };
            _cursorUpdateTimer.Tick += delegate { FlushPointerMarker(); };
            _cursorMarker.Visibility = Visibility.Collapsed;
            _cursorLayer.Children.Add(_cursorMarker);
            _captureGrid = new Grid { Background = Brushes.Transparent, ClipToBounds = true };
            _captureGrid.Children.Add(_image);
            _captureGrid.Children.Add(_drawing);
            _captureGrid.Children.Add(_cursorLayer);
            _frame = new Border
            {
                BorderBrush = Brush("#4A4D58"), BorderThickness = new Thickness(2),
                Child = _captureGrid
            };
            _root.Children.Add(_frame);

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
            _parentButton = ToolButton("corner-up-left", "选择父级控件；再次点击继续向上", delegate { SelectParentControl(); });
            Button exit = ToolButton("x", "退出捕获 (Esc)", delegate { CloseAsync(); }, "#FF6B81");
            _confirmButton = ToolButton("check", _fieldDestination == "resource" ? "录入所选资源 (Enter)" : "确认并回填 (Enter)", delegate { ConfirmFieldCapture(); }, "#4ED19C");
            if (_fieldMode)
            {
                tools.Children.Add(_clearButton);
                if (_fieldSelectionMode == "control") tools.Children.Add(_parentButton);
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
                Background = Brush("#F21A1C20"), BorderBrush = Brush("#4A4D54"), BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(7), Padding = new Thickness(3),
                Effect = new DropShadowEffect { Color = Colors.Black, BlurRadius = 12, ShadowDepth = 2, Opacity = 0.42 },
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
            LoadImagePayload(payload);
            SourceInitialized += delegate { NativeMethods.Place(this, _screen); };
            Loaded += delegate { LayoutOverlay(_frame, chip); FocusOverlay(); };
            SizeChanged += delegate { LayoutToolbar(); };
            KeyDown += OnKeyDown;
            PreviewMouseDown += delegate(object sender, MouseButtonEventArgs args)
            {
                if (!_captureGrid.IsMouseOver && !_toolbar.IsMouseOver) args.Handled = true;
            };
            _captureGrid.MouseLeftButtonDown += CaptureMouseDown;
            _captureGrid.MouseMove += CaptureMouseMove;
            _captureGrid.MouseLeftButtonUp += CaptureMouseUp;
            _captureGrid.MouseEnter += delegate(object sender, MouseEventArgs args) { UpdatePointerMarker(args); };
            _captureGrid.MouseLeave += delegate { HidePointerMarker(); };
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

        private static Grid CreatePointerMarker()
        {
            Grid marker = new Grid
            {
                Width = 20, Height = 20, IsHitTestVisible = false,
                SnapsToDevicePixels = true, UseLayoutRounding = true
            };
            marker.Children.Add(new Line
            {
                X1 = 1, X2 = 19, Y1 = 10, Y2 = 10,
                Stroke = Brush("#0B0D10"), StrokeThickness = 3.5
            });
            marker.Children.Add(new Line
            {
                X1 = 10, X2 = 10, Y1 = 1, Y2 = 19,
                Stroke = Brush("#0B0D10"), StrokeThickness = 3.5
            });
            marker.Children.Add(new Line
            {
                X1 = 1, X2 = 19, Y1 = 10, Y2 = 10,
                Stroke = Brush("#F26A21"), StrokeThickness = 1.5
            });
            marker.Children.Add(new Line
            {
                X1 = 10, X2 = 10, Y1 = 1, Y2 = 19,
                Stroke = Brush("#F26A21"), StrokeThickness = 1.5
            });
            marker.Children.Add(new Ellipse
            {
                Width = 4, Height = 4, Fill = Brush("#F26A21"),
                Stroke = Brush("#0B0D10"), StrokeThickness = 1,
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center
            });
            return marker;
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
            FrameworkElement glyph = LucideIcons.Create(icon, 17, color);
            ControlTemplate template = new ControlTemplate(typeof(Button));
            FrameworkElementFactory chrome = new FrameworkElementFactory(typeof(Border));
            chrome.SetValue(Border.CornerRadiusProperty, new CornerRadius(4));
            chrome.SetBinding(Border.BackgroundProperty, new Binding("Background") { RelativeSource = RelativeSource.TemplatedParent });
            chrome.SetBinding(Border.BorderBrushProperty, new Binding("BorderBrush") { RelativeSource = RelativeSource.TemplatedParent });
            chrome.SetBinding(Border.BorderThicknessProperty, new Binding("BorderThickness") { RelativeSource = RelativeSource.TemplatedParent });
            FrameworkElementFactory content = new FrameworkElementFactory(typeof(ContentPresenter));
            content.SetValue(FrameworkElement.HorizontalAlignmentProperty, HorizontalAlignment.Center);
            content.SetValue(FrameworkElement.VerticalAlignmentProperty, VerticalAlignment.Center);
            chrome.AppendChild(content);
            template.VisualTree = chrome;
            Button button = new Button
            {
                Content = glyph, ToolTip = tooltip,
                Width = 32, Height = 30, Margin = new Thickness(1, 0, 1, 0),
                Background = Brushes.Transparent, BorderBrush = Brushes.Transparent, BorderThickness = new Thickness(1),
                Padding = new Thickness(6), Cursor = Cursors.Hand, Opacity = 1,
                Template = template, FocusVisualStyle = null
            };
            AutomationProperties.SetName(button, tooltip);
            AutomationProperties.SetHelpText(button, tooltip);
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
            button.IsEnabledChanged += delegate
            {
                // Preserve the toolbar silhouette and quiet only the glyph.
                // Disabled actions then look unavailable rather than broken.
                button.Opacity = 1;
                glyph.Opacity = button.IsEnabled ? 1 : 0.26;
                button.Cursor = button.IsEnabled ? Cursors.Hand : Cursors.Arrow;
                button.Background = Brushes.Transparent;
                button.BorderBrush = Brushes.Transparent;
            };
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
            double above = y + 6;
            Rect selection;
            if (_fieldMode && TryGetSelectionBounds(out selection))
            {
                toolbarX = Math.Max(6, Math.Min(
                    ActualWidth - _toolbar.ActualWidth - 6,
                    x + selection.Left + (selection.Width - _toolbar.ActualWidth) / 2));
                below = y + selection.Bottom + 10;
                above = y + selection.Top - _toolbar.ActualHeight - 10;
            }
            double toolbarY = below + _toolbar.ActualHeight <= ActualHeight - 6
                ? below : Math.Max(6, above);
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

        private void LoadImagePayload(CapturePayload payload)
        {
            if (!String.Equals(payload.SnapshotTransport, "shared_bgra", StringComparison.OrdinalIgnoreCase))
            {
                LoadImageFile(payload.SnapshotPath);
                return;
            }
            int stride = payload.SnapshotStride > 0 ? payload.SnapshotStride : payload.Width * 4;
            long required = (long)stride * payload.Height;
            if (required <= 0 || required > Int32.MaxValue)
                throw new InvalidDataException("冻结帧共享内存尺寸无效");
            byte[] pixels = new byte[(int)required];
            using (MemoryMappedFile mapping = MemoryMappedFile.OpenExisting(payload.SnapshotMapping, MemoryMappedFileRights.Read))
            using (MemoryMappedViewAccessor view = mapping.CreateViewAccessor(0, required, MemoryMappedFileAccess.Read))
            {
                int read = view.ReadArray(0, pixels, 0, pixels.Length);
                if (read != pixels.Length) throw new EndOfStreamException("冻结帧共享内存读取不完整");
            }
            BitmapSource bitmap = BitmapSource.Create(
                payload.Width, payload.Height, 96, 96,
                PixelFormats.Bgra32, null, pixels, stride);
            bitmap.Freeze();
            _image.Source = bitmap;
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

        private Dictionary<string, object> SampleColor(System.Windows.Point point)
        {
            BitmapSource source = _image.Source as BitmapSource;
            if (source == null) throw new InvalidOperationException("冻结帧不支持像素取色");
            BitmapSource bgra = source.Format == PixelFormats.Bgra32
                ? source
                : new FormatConvertedBitmap(source, PixelFormats.Bgra32, null, 0);
            int x = Clamp((int)point.X, 0, bgra.PixelWidth - 1);
            int y = Clamp((int)point.Y, 0, bgra.PixelHeight - 1);
            byte[] pixel = new byte[4];
            bgra.CopyPixels(new Int32Rect(x, y, 1, 1), pixel, 4, 0);
            return new Dictionary<string, object>
            {
                { "red", (int)pixel[2] }, { "green", (int)pixel[1] },
                { "blue", (int)pixel[0] }, { "alpha", (int)pixel[3] }
            };
        }

        private Brush SampleColorBrush(System.Windows.Point point)
        {
            Dictionary<string, object> color = SampleColor(point);
            return new SolidColorBrush(Color.FromArgb(
                Convert.ToByte(color["alpha"]), Convert.ToByte(color["red"]),
                Convert.ToByte(color["green"]), Convert.ToByte(color["blue"])));
        }

        private void DrawColorLabel(System.Windows.Point point)
        {
            Dictionary<string, object> color = SampleColor(point);
            string hex = String.Format("#{0:X2}{1:X2}{2:X2}", color["red"], color["green"], color["blue"]);
            Border chip = new Border
            {
                Background = Brush("#F21B2028"), BorderBrush = Brush("#4A4D58"),
                BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(5),
                Padding = new Thickness(5, 4, 8, 4)
            };
            StackPanel content = new StackPanel { Orientation = Orientation.Horizontal };
            content.Children.Add(new Border
            {
                Width = 18, Height = 18, Margin = new Thickness(0, 0, 6, 0),
                CornerRadius = new CornerRadius(3), Background = SampleColorBrush(point),
                BorderBrush = Brushes.White, BorderThickness = new Thickness(1)
            });
            content.Children.Add(new TextBlock
            {
                Text = hex, Foreground = Brush("#E8EDF5"), FontSize = 11,
                FontFamily = new FontFamily("Consolas"), VerticalAlignment = VerticalAlignment.Center
            });
            chip.Child = content;
            chip.Measure(new Size(150, 40));
            double x = point.X * _drawing.ActualWidth / _payload.Width;
            double y = point.Y * _drawing.ActualHeight / _payload.Height;
            double left = Math.Max(4, Math.Min(_drawing.ActualWidth - chip.DesiredSize.Width - 4, x + 16));
            double top = y + chip.DesiredSize.Height + 20 < _drawing.ActualHeight
                ? y + 14 : y - chip.DesiredSize.Height - 14;
            Canvas.SetLeft(chip, left);
            Canvas.SetTop(chip, Math.Max(4, top));
            _drawing.Children.Add(chip);
        }

        private static int Clamp(int value, int min, int max) { return Math.Max(min, Math.Min(max, value)); }

        private void CaptureMouseDown(object sender, MouseButtonEventArgs args)
        {
            if (_busy) return;
            FocusOverlay();
            _dragStart = PixelPoint(args);
            if (_fieldMode && _fieldSelectionMode == "control")
            {
                _moved = false;
                _captureGrid.CaptureMouse();
                args.Handled = true;
                return;
            }
            if (_fieldMode && _fieldSelectionMode == "path")
            {
                _pathPoints.Clear();
                _pathPoints.Add(_dragStart.Value);
                _point = null;
                _rectangles.Clear();
                _activeRect = -1;
                _moved = false;
                _captureGrid.CaptureMouse();
                Redraw();
                args.Handled = true;
                return;
            }
            _appendDraft = Keyboard.Modifiers.HasFlag(ModifierKeys.Shift) && (!_fieldMode || _fieldMaxRects > 1);
            _moved = false;
            _draft = new CaptureRect { X = (int)_dragStart.Value.X, Y = (int)_dragStart.Value.Y, Width = 1, Height = 1 };
            _captureGrid.CaptureMouse();
            args.Handled = true;
        }

        private void CaptureMouseMove(object sender, MouseEventArgs args)
        {
            UpdatePointerMarker(args);
            if (_busy || !_dragStart.HasValue || args.LeftButton != MouseButtonState.Pressed) return;
            System.Windows.Point current = PixelPoint(args);
            if (_fieldMode && _fieldSelectionMode == "path")
            {
                System.Windows.Point previous = _pathPoints[_pathPoints.Count - 1];
                double distance = Math.Sqrt(Math.Pow(current.X - previous.X, 2) + Math.Pow(current.Y - previous.Y, 2));
                if (distance >= 3)
                {
                    _pathPoints.Add(current);
                    _moved = true;
                    Redraw();
                }
                return;
            }
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

        private void UpdatePointerMarker(MouseEventArgs args)
        {
            if (_busy)
            {
                HidePointerMarker();
                return;
            }
            _pendingPointerPosition = args.GetPosition(_captureGrid);
            if (_cursorMarker.Visibility != Visibility.Visible)
            {
                FlushPointerMarker();
                return;
            }
            if (!_cursorUpdateTimer.IsEnabled) _cursorUpdateTimer.Start();
        }

        private void FlushPointerMarker()
        {
            _cursorUpdateTimer.Stop();
            if (!_pendingPointerPosition.HasValue) return;
            System.Windows.Point point = _pendingPointerPosition.Value;
            _pendingPointerPosition = null;
            DpiScale dpi = VisualTreeHelper.GetDpi(_captureGrid);
            double left = Math.Round((point.X - _cursorMarker.Width / 2) * dpi.DpiScaleX) / dpi.DpiScaleX;
            double top = Math.Round((point.Y - _cursorMarker.Height / 2) * dpi.DpiScaleY) / dpi.DpiScaleY;
            if (Math.Abs(_cursorTransform.X - left) > 0.001) _cursorTransform.X = left;
            if (Math.Abs(_cursorTransform.Y - top) > 0.001) _cursorTransform.Y = top;
            if (_cursorMarker.Visibility != Visibility.Visible) _cursorMarker.Visibility = Visibility.Visible;
        }

        private void HidePointerMarker()
        {
            _cursorUpdateTimer.Stop();
            _pendingPointerPosition = null;
            _cursorMarker.Visibility = Visibility.Collapsed;
        }

        private void CaptureMouseUp(object sender, MouseButtonEventArgs args)
        {
            if (!_dragStart.HasValue) return;
            System.Windows.Point click = PixelPoint(args);
            if (_fieldMode && _fieldSelectionMode == "control")
            {
                _dragStart = null;
                _draft = null;
                _captureGrid.ReleaseMouseCapture();
                args.Handled = true;
                ProbeControl(click);
                return;
            }
            if (_fieldMode && _fieldSelectionMode == "path")
            {
                System.Windows.Point previous = _pathPoints[_pathPoints.Count - 1];
                if (Math.Abs(click.X - previous.X) >= 1 || Math.Abs(click.Y - previous.Y) >= 1)
                    _pathPoints.Add(click);
                // A gesture needs a start and an end. A simple click is kept as an
                // incomplete draft so Enter cannot accidentally commit it.
            }
            else if (_fieldMode && (_fieldSelectionMode == "point" || _fieldSelectionMode == "color"))
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
            DrawSelectionFocusMask();
            if (_pathPoints.Count > 0)
            {
                Polyline path = new Polyline
                {
                    Stroke = Brush("#39A9FF"), StrokeThickness = 3,
                    StrokeLineJoin = PenLineJoin.Round, StrokeStartLineCap = PenLineCap.Round,
                    StrokeEndLineCap = PenLineCap.Round
                };
                foreach (System.Windows.Point point in _pathPoints)
                    path.Points.Add(new System.Windows.Point(
                        point.X * _drawing.ActualWidth / _payload.Width,
                        point.Y * _drawing.ActualHeight / _payload.Height));
                _drawing.Children.Add(path);
                for (int i = 0; i < _pathPoints.Count; i++)
                {
                    if (i != 0 && i != _pathPoints.Count - 1 && i % 8 != 0) continue;
                    double x = _pathPoints[i].X * _drawing.ActualWidth / _payload.Width;
                    double y = _pathPoints[i].Y * _drawing.ActualHeight / _payload.Height;
                    Ellipse marker = new Ellipse
                    {
                        Width = i == 0 || i == _pathPoints.Count - 1 ? 9 : 5,
                        Height = i == 0 || i == _pathPoints.Count - 1 ? 9 : 5,
                        Fill = i == 0 ? Brush("#4ED19C") : (i == _pathPoints.Count - 1 ? Brush("#FF5964") : Brushes.White),
                        Stroke = Brush("#11141B"), StrokeThickness = 1
                    };
                    Canvas.SetLeft(marker, x - marker.Width / 2);
                    Canvas.SetTop(marker, y - marker.Height / 2);
                    _drawing.Children.Add(marker);
                }
            }
            bool showSequence = _fieldSelectionMode != "control" && (!_fieldMode || _fieldMaxRects > 1);
            for (int i = 0; i < _rectangles.Count; i++)
                DrawRect(_rectangles[i], showSequence ? i : -1, i == _activeRect, false);
            if (_draft != null && _moved) DrawRect(_draft, -1, true, true);
            if (_point.HasValue)
            {
                double x = _point.Value.X * _drawing.ActualWidth / _payload.Width;
                double y = _point.Value.Y * _drawing.ActualHeight / _payload.Height;
                Brush pointBrush = _fieldSelectionMode == "color" ? SampleColorBrush(_point.Value) : Brush("#FF5964");
                Ellipse dot = new Ellipse { Width = 12, Height = 12, Fill = pointBrush, Stroke = Brushes.White, StrokeThickness = 2 };
                Canvas.SetLeft(dot, x - 6); Canvas.SetTop(dot, y - 6); _drawing.Children.Add(dot);
                Line h = new Line { X1 = x - 12, X2 = x + 12, Y1 = y, Y2 = y, Stroke = Brush("#39A9FF"), StrokeThickness = 1.5 };
                Line v = new Line { X1 = x, X2 = x, Y1 = y - 12, Y2 = y + 12, Stroke = Brush("#39A9FF"), StrokeThickness = 1.5 };
                _drawing.Children.Add(h); _drawing.Children.Add(v);
                if (_fieldSelectionMode == "color") DrawColorLabel(_point.Value);
            }
            if (_fieldSelectionMode == "control" && _controlCandidateIndex >= 0 && _controlCandidateIndex < _controlCandidates.Count)
                DrawControlLabel(_controlCandidates[_controlCandidateIndex]);
            LayoutToolbar();
        }

        private bool TryGetSelectionBounds(out Rect bounds)
        {
            bounds = Rect.Empty;
            double scaleX = _drawing.ActualWidth / Math.Max(1, _payload.Width);
            double scaleY = _drawing.ActualHeight / Math.Max(1, _payload.Height);
            CaptureRect rect = _draft != null && _moved
                ? _draft
                : (_activeRect >= 0 && _activeRect < _rectangles.Count ? _rectangles[_activeRect] : null);
            if (rect != null)
            {
                bounds = new Rect(rect.X * scaleX, rect.Y * scaleY,
                    Math.Max(1, rect.Width * scaleX), Math.Max(1, rect.Height * scaleY));
                return true;
            }
            if (_point.HasValue)
            {
                double x = _point.Value.X * scaleX;
                double y = _point.Value.Y * scaleY;
                bounds = new Rect(x - 28, y - 28, 56, 56);
                return true;
            }
            if (_pathPoints.Count > 0)
            {
                double left = _pathPoints.Min(point => point.X) * scaleX;
                double top = _pathPoints.Min(point => point.Y) * scaleY;
                double right = _pathPoints.Max(point => point.X) * scaleX;
                double bottom = _pathPoints.Max(point => point.Y) * scaleY;
                bounds = new Rect(left, top, Math.Max(1, right - left), Math.Max(1, bottom - top));
                return true;
            }
            return false;
        }

        private void DrawSelectionFocusMask()
        {
            Rect selection;
            if (!_fieldMode || _fieldSelectionMode == "path" || !TryGetSelectionBounds(out selection)) return;
            GeometryGroup geometry = new GeometryGroup { FillRule = FillRule.EvenOdd };
            geometry.Children.Add(new RectangleGeometry(new Rect(0, 0, _drawing.ActualWidth, _drawing.ActualHeight)));
            if (_fieldSelectionMode == "point" || _fieldSelectionMode == "color")
                geometry.Children.Add(new EllipseGeometry(selection));
            else
                geometry.Children.Add(new RectangleGeometry(selection));
            _drawing.Children.Add(new System.Windows.Shapes.Path
            {
                Data = geometry,
                Fill = Brush("#6B080B10"),
                IsHitTestVisible = false
            });
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
            if (active && !draft && _fieldSelectionMode != "control")
            {
                DrawCornerGuides(x, y, width, height);
            }
        }

        private void DrawCornerGuides(double x, double y, double width, double height)
        {
            const double length = 9;
            SolidColorBrush stroke = Brush("#D9EDF8FF");
            double[,] segments = {
                { x, y, x + length, y }, { x, y, x, y + length },
                { x + width - length, y, x + width, y }, { x + width, y, x + width, y + length },
                { x, y + height, x + length, y + height }, { x, y + height - length, x, y + height },
                { x + width - length, y + height, x + width, y + height }, { x + width, y + height - length, x + width, y + height }
            };
            for (int i = 0; i < 8; i++)
            {
                _drawing.Children.Add(new Line
                {
                    X1 = segments[i, 0], Y1 = segments[i, 1], X2 = segments[i, 2], Y2 = segments[i, 3],
                    Stroke = stroke, StrokeThickness = 2.25, StrokeStartLineCap = PenLineCap.Square,
                    StrokeEndLineCap = PenLineCap.Square, IsHitTestVisible = false
                });
            }
        }

        private void ClearSelection()
        {
            _pageWarningArmed = false;
            _point = null;
            _rectangles.Clear();
            _pathPoints.Clear();
            _activeRect = -1;
            _draft = null;
            _controlCandidates.Clear();
            _controlCandidateIndex = -1;
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
            _portCombo.IsEnabled = !_busy && _ports.Count > 0;
            _clearButton.IsEnabled = !_busy && (_point.HasValue || _rectangles.Count > 0 || _pathPoints.Count > 0);
            _parentButton.IsEnabled = !_busy && _controlCandidateIndex >= 0 && _controlCandidateIndex + 1 < _controlCandidates.Count;
            _confirmButton.IsEnabled = !_busy && ((_fieldSelectionMode == "point" || _fieldSelectionMode == "color")
                ? _point.HasValue
                : (_fieldSelectionMode == "region" ? _rectangles.Count == 1
                : (_fieldSelectionMode == "path" ? _pathPoints.Count >= 2
                : (_fieldSelectionMode == "control" ? _controlCandidateIndex >= 0 : _rectangles.Count > 0))));
        }

        private void DrawControlLabel(Dictionary<string, object> candidate)
        {
            Rect bounds;
            if (!TryGetSelectionBounds(out bounds)) return;
            string label = JsonUtil.String(candidate, "label", "未命名控件");
            string role = JsonUtil.String(candidate, "role", "control");
            Border chip = new Border
            {
                Background = Brush("#F21B2028"), BorderBrush = Brush("#4A4D58"), BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(5), Padding = new Thickness(8, 4, 8, 4),
                Child = new TextBlock
                {
                    Text = role + " · " + label + "  " + (_controlCandidateIndex + 1) + "/" + _controlCandidates.Count,
                    Foreground = Brush("#E8EDF5"), FontSize = 11, MaxWidth = 360,
                    TextTrimming = TextTrimming.CharacterEllipsis
                }
            };
            chip.Measure(new Size(380, 40));
            double left = Math.Max(4, Math.Min(_drawing.ActualWidth - chip.DesiredSize.Width - 4, bounds.Left));
            double top = bounds.Top >= chip.DesiredSize.Height + 8
                ? bounds.Top - chip.DesiredSize.Height - 6
                : Math.Min(_drawing.ActualHeight - chip.DesiredSize.Height - 4, bounds.Bottom + 6);
            Canvas.SetLeft(chip, left);
            Canvas.SetTop(chip, Math.Max(4, top));
            _drawing.Children.Add(chip);
        }

        private void ApplyControlCandidate(int index)
        {
            if (index < 0 || index >= _controlCandidates.Count) return;
            object[] rect = JsonUtil.Array(_controlCandidates[index], "frame_rect");
            if (rect == null || rect.Length != 4) return;
            _controlCandidateIndex = index;
            int x = Clamp(Convert.ToInt32(rect[0]), 0, _payload.Width - 1);
            int y = Clamp(Convert.ToInt32(rect[1]), 0, _payload.Height - 1);
            _rectangles.Clear();
            _rectangles.Add(new CaptureRect
            {
                X = x,
                Y = y,
                Width = Math.Max(1, Math.Min(_payload.Width - x, Convert.ToInt32(rect[2]))),
                Height = Math.Max(1, Math.Min(_payload.Height - y, Convert.ToInt32(rect[3])))
            });
            _activeRect = 0;
            _point = null;
            _pathPoints.Clear();
            Redraw();
            UpdateButtons();
        }

        private void SelectParentControl()
        {
            if (_busy || _controlCandidateIndex < 0 || _controlCandidateIndex + 1 >= _controlCandidates.Count) return;
            ApplyControlCandidate(_controlCandidateIndex + 1);
        }

        private async void ProbeControl(System.Windows.Point click)
        {
            if (_busy) return;
            SetBusy(true, "正在识别控件…");
            try
            {
                Dictionary<string, object> action = BaseAction("field_control_probe");
                action["field_request_id"] = _fieldRequestId;
                action["point"] = new object[] { (int)click.X, (int)click.Y };
                Dictionary<string, object> result = await RequestActionAsync(action);
                object[] candidates = JsonUtil.Array(result, "candidates") ?? new object[0];
                _controlCandidates.Clear();
                foreach (object value in candidates)
                {
                    Dictionary<string, object> candidate = value as Dictionary<string, object>;
                    if (candidate != null && JsonUtil.Object(candidate, "selector") != null)
                        _controlCandidates.Add(candidate);
                }
                if (_controlCandidates.Count == 0) throw new InvalidOperationException("当前位置没有可识别控件");
                ApplyControlCandidate(0);
            }
            catch (Exception ex)
            {
                ClearSelection();
                ShowNotice("控件识别失败：" + ex.Message, "error");
            }
            finally
            {
                SetBusy(false, "");
                FocusOverlay();
            }
        }

        private void SetBusy(bool value, string message)
        {
            _busy = value;
            if (value)
            {
                _status.Tag = "busy";
                _status.Background = Brush("#E31B2028");
                _status.Foreground = Brushes.White;
                _status.Content = message ?? "";
                _status.Visibility = Visibility.Visible;
            }
            else if (Convert.ToString(_status.Tag) == "busy")
            {
                _status.Visibility = Visibility.Collapsed;
                _status.Tag = null;
            }
            Cursor = value ? Cursors.Wait : Cursors.Arrow;
            if (value || !_captureGrid.IsMouseOver) HidePointerMarker();
            else _cursorMarker.Visibility = Visibility.Visible;
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
            catch (Exception ex) { ShowNotice("点击节点生成失败：" + ex.Message, "error"); }
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
                if (_fieldSelectionMode == "point" || _fieldSelectionMode == "color")
                {
                    action["point"] = new object[] { (int)_point.Value.X, (int)_point.Value.Y };
                    if (_fieldSelectionMode == "color") action["color"] = SampleColor(_point.Value);
                }
                else if (_fieldSelectionMode == "path")
                    action["path"] = _pathPoints.Select(point => (object)new object[] { (int)point.X, (int)point.Y }).ToArray();
                else if (_fieldSelectionMode == "control")
                    action["selector"] = JsonUtil.Object(_controlCandidates[_controlCandidateIndex], "selector");
                else
                    action["rects"] = _rectangles.Select(rect => (object)new object[] { rect.X, rect.Y, rect.Width, rect.Height }).ToArray();
                await RequestActionAsync(action);
                _fieldCompleted = true;
                closeAfter = true;
            }
            catch (Exception ex) { ShowNotice("属性回填失败：" + ex.Message, "error"); }
            finally
            {
                SetBusy(false, "");
                if (closeAfter) CloseAsync(); else FocusOverlay();
            }
        }

        private async void OpenSaveManager(string kind)
        {
            if (_busy) return;
            if (kind == "page" && _rectangles.Count > 8 && !_pageWarningArmed)
            {
                _pageWarningArmed = true;
                ShowNotice("当前页面包含 " + _rectangles.Count + " 个特征，可能增加识别耗时；再次点击页面按钮继续。", "warning");
                return;
            }
            _pageWarningArmed = false;
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
                    { "destination", fieldSave ? _fieldDestination : "parameter" },
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
            catch (Exception ex) { ShowNotice("资源保存失败：" + ex.Message, "error"); }
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
            catch (Exception ex) { ShowNotice("无法撤销：" + ex.Message, "warning"); }
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
            catch (Exception ex) { ShowNotice("刷新失败：" + ex.Message, "warning"); }
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

        private void ShowNotice(string message, string tone = "normal")
        {
            _status.Tag = "notice";
            _status.Content = message;
            _status.Background = Brush(tone == "error" ? "#F23A1F28" : tone == "warning" ? "#F23A311B" : "#E31B2028");
            _status.Foreground = Brush(tone == "error" ? "#FFD2D8" : tone == "warning" ? "#FFE7B0" : "#FFFFFF");
            _status.Visibility = Visibility.Visible;
            System.Windows.Threading.DispatcherTimer timer = new System.Windows.Threading.DispatcherTimer
            {
                Interval = TimeSpan.FromSeconds(tone == "normal" ? 2.4 : 5.0)
            };
            timer.Tick += delegate
            {
                timer.Stop();
                if (!_busy && Convert.ToString(_status.Tag) == "notice")
                {
                    _status.Visibility = Visibility.Collapsed;
                    _status.Tag = null;
                }
            };
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
            else if (_pathPoints.Count > 0)
            {
                int minX = (int)_pathPoints.Min(point => point.X);
                int maxX = (int)_pathPoints.Max(point => point.X);
                int minY = (int)_pathPoints.Min(point => point.Y);
                int maxY = (int)_pathPoints.Max(point => point.Y);
                int nextMinX = Clamp(minX + dx, 0, _payload.Width - 1);
                int nextMaxX = Clamp(maxX + dx, 0, _payload.Width - 1);
                int nextMinY = Clamp(minY + dy, 0, _payload.Height - 1);
                int nextMaxY = Clamp(maxY + dy, 0, _payload.Height - 1);
                int safeDx = dx < 0 ? nextMinX - minX : nextMaxX - maxX;
                int safeDy = dy < 0 ? nextMinY - minY : nextMaxY - maxY;
                for (int i = 0; i < _pathPoints.Count; i++)
                    _pathPoints[i] = new System.Windows.Point(_pathPoints[i].X + safeDx, _pathPoints[i].Y + safeDy);
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
            else if (_fieldSelectionMode != "control" && (args.Key == Key.Left || args.Key == Key.Right || args.Key == Key.Up || args.Key == Key.Down))
            { AdjustSelection(args.Key, modifiers); args.Handled = true; }
            else if (args.Key == Key.D1 || args.Key == Key.NumPad1) { if (_clickButton.IsEnabled) CreateClick(); args.Handled = true; }
            else if (args.Key == Key.D2 || args.Key == Key.NumPad2) { if (_imageButton.IsEnabled) OpenSaveManager("image"); args.Handled = true; }
            else if (args.Key == Key.D3 || args.Key == Key.NumPad3) { if (_ocrButton.IsEnabled) OpenSaveManager("ocr"); args.Handled = true; }
            else if (args.Key == Key.D4 || args.Key == Key.NumPad4) { if (_pageButton.IsEnabled) OpenSaveManager("page"); args.Handled = true; }
            else if (args.Key == Key.D5 || args.Key == Key.NumPad5) { if (_recordButton.IsEnabled) OpenSaveManager("record"); args.Handled = true; }
        }
    }
}
