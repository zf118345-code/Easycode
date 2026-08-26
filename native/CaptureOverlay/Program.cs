using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using Forms = System.Windows.Forms;

namespace Easycode.CaptureOverlay
{
    internal static class JsonUtil
    {
        private static readonly JavaScriptSerializer Serializer = new JavaScriptSerializer { MaxJsonLength = 32 * 1024 * 1024 };
        private static readonly object WriteLock = new object();
        private static TextReader Input = Console.In;
        private static TextWriter Output = Console.Out;

        internal static void ConfigureRedirectedPipes()
        {
            // A /target:winexe process has no console. Console.InputEncoding and
            // Console.OutputEncoding call Get/SetConsoleCP and fail with
            // ERROR_INVALID_HANDLE even though Python supplied valid redirected
            // stdin/stdout pipes. Wrap those handles directly instead.
            Input = new StreamReader(
                Console.OpenStandardInput(), new UTF8Encoding(false), false, 4096);
            Output = new StreamWriter(
                Console.OpenStandardOutput(), new UTF8Encoding(false), 4096) { AutoFlush = true };
        }

        internal static string ReadLine()
        {
            return Input.ReadLine();
        }

        internal static Dictionary<string, object> Parse(string value)
        {
            return Serializer.DeserializeObject(value) as Dictionary<string, object>;
        }

        internal static string Serialize(object value)
        {
            return Serializer.Serialize(value);
        }

        internal static void Write(Dictionary<string, object> value)
        {
            lock (WriteLock)
            {
                Output.WriteLine(Serializer.Serialize(value));
                Output.Flush();
            }
        }

        internal static string String(Dictionary<string, object> data, string key, string fallback)
        {
            object value;
            return data != null && data.TryGetValue(key, out value) && value != null ? Convert.ToString(value) : fallback;
        }

        internal static int Int(Dictionary<string, object> data, string key, int fallback)
        {
            object value;
            int result;
            return data != null && data.TryGetValue(key, out value) && value != null && Int32.TryParse(Convert.ToString(value), out result)
                ? result : fallback;
        }

        internal static Dictionary<string, object> Object(Dictionary<string, object> data, string key)
        {
            object value;
            return data != null && data.TryGetValue(key, out value) ? value as Dictionary<string, object> : null;
        }

        internal static object[] Array(Dictionary<string, object> data, string key)
        {
            object value;
            return data != null && data.TryGetValue(key, out value) ? value as object[] : null;
        }
    }

    internal static class NativeMethods
    {
        internal const int GWL_EXSTYLE = -20;
        internal const int WS_EX_TOOLWINDOW = 0x00000080;
        internal const int SWP_SHOWWINDOW = 0x0040;
        internal static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);

        [DllImport("user32.dll")]
        internal static extern bool SetProcessDpiAwarenessContext(IntPtr value);

        [DllImport("user32.dll")]
        internal static extern bool SetWindowPos(IntPtr hwnd, IntPtr after, int x, int y, int width, int height, uint flags);

        [DllImport("user32.dll")]
        internal static extern int GetWindowLong(IntPtr hwnd, int index);

        [DllImport("user32.dll")]
        internal static extern int SetWindowLong(IntPtr hwnd, int index, int value);

        [DllImport("user32.dll")]
        internal static extern bool SetForegroundWindow(IntPtr hwnd);

        [DllImport("user32.dll")]
        internal static extern bool ReleaseCapture();

        [DllImport("user32.dll")]
        internal static extern IntPtr SendMessage(IntPtr hwnd, int message, IntPtr wParam, IntPtr lParam);

        internal const int WM_NCLBUTTONDOWN = 0x00A1;
        internal const int HTCAPTION = 2;

        internal static void EnablePerMonitorV2()
        {
            try { SetProcessDpiAwarenessContext(new IntPtr(-4)); }
            catch { }
        }

        internal static void Place(Window window, Forms.Screen screen)
        {
            WindowInteropHelper helper = new WindowInteropHelper(window);
            IntPtr hwnd = helper.Handle;
            int style = GetWindowLong(hwnd, GWL_EXSTYLE);
            SetWindowLong(hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW);
            SetWindowPos(hwnd, HWND_TOPMOST, screen.Bounds.Left, screen.Bounds.Top,
                screen.Bounds.Width, screen.Bounds.Height, SWP_SHOWWINDOW);
        }
    }

    internal sealed class CapturePayload
    {
        internal Dictionary<string, object> Raw;
        internal string Origin;
        internal string SnapshotPath;
        internal string SnapshotId;
        internal string SessionId;
        internal string ProjectPath;
        internal string ProjectName;
        internal string TargetName;
        internal string Backend;
        internal int Width;
        internal int Height;
        internal int Left;
        internal int Top;
        internal int Right;
        internal int Bottom;
        internal Dictionary<string, object> CaptureContext;

        internal static CapturePayload From(Dictionary<string, object> data)
        {
            CapturePayload payload = new CapturePayload();
            payload.Raw = data;
            payload.Origin = JsonUtil.String(data, "origin", "");
            payload.SnapshotPath = JsonUtil.String(data, "snapshot_path", "");
            payload.SnapshotId = JsonUtil.String(data, "snapshot_id", "");
            payload.SessionId = JsonUtil.String(data, "session_id", "");
            payload.ProjectPath = JsonUtil.String(data, "project_path", "");
            payload.ProjectName = JsonUtil.String(data, "project_name", "Easycode 项目");
            payload.TargetName = JsonUtil.String(data, "target_name", "");
            payload.Backend = JsonUtil.String(data, "backend", "");
            payload.Width = Math.Max(1, JsonUtil.Int(data, "width", 1));
            payload.Height = Math.Max(1, JsonUtil.Int(data, "height", 1));
            object[] region = JsonUtil.Array(data, "region");
            if (region == null || region.Length != 4) throw new InvalidDataException("工作面板屏幕范围无效");
            payload.Left = Convert.ToInt32(region[0]);
            payload.Top = Convert.ToInt32(region[1]);
            payload.Right = Convert.ToInt32(region[2]);
            payload.Bottom = Convert.ToInt32(region[3]);
            if (payload.Right <= payload.Left || payload.Bottom <= payload.Top) throw new InvalidDataException("工作面板尺寸无效");
            payload.CaptureContext = JsonUtil.Object(data, "capture_context") ?? new Dictionary<string, object>();
            return payload;
        }
    }

    internal sealed class MaskWindow : Window
    {
        internal Forms.Screen ScreenInfo;

        internal MaskWindow(Forms.Screen screen)
        {
            ScreenInfo = screen;
            WindowStyle = WindowStyle.None;
            ResizeMode = ResizeMode.NoResize;
            ShowInTaskbar = false;
            Topmost = true;
            Background = new SolidColorBrush(Color.FromArgb(190, 8, 11, 16));
            AllowsTransparency = true;
            Focusable = false;
            SourceInitialized += delegate { NativeMethods.Place(this, ScreenInfo); };
            MouseDown += delegate { };
        }
    }

    internal sealed class OverlayHost
    {
        private readonly Application _application;
        private readonly List<MaskWindow> _masks = new List<MaskWindow>();
        private readonly CaptureFileBrowserWindow _resourceBrowser;
        private CaptureOverlayWindow _overlay;
        private Thread _reader;

        internal OverlayHost(Application application)
        {
            _application = application;
            _resourceBrowser = new CaptureFileBrowserWindow();
        }

        internal void Start()
        {
            _reader = new Thread(ReadLoop);
            _reader.IsBackground = true;
            _reader.Name = "capture-overlay-command-pipe";
            _reader.Start();
        }

        private void ReadLoop()
        {
            string line;
            while ((line = JsonUtil.ReadLine()) != null)
            {
                Dictionary<string, object> command;
                try { command = JsonUtil.Parse(line); }
                catch (Exception ex)
                {
                    JsonUtil.Write(new Dictionary<string, object> { { "ok", false }, { "message", "命令 JSON 无效: " + ex.Message } });
                    continue;
                }
                if (command == null) continue;
                _application.Dispatcher.BeginInvoke(new Action(delegate { Execute(command); }));
            }
            _application.Dispatcher.BeginInvoke(new Action(delegate
            {
                _resourceBrowser.Shutdown();
                _application.Shutdown();
            }));
        }

        private void Reply(Dictionary<string, object> command, bool ok, string message)
        {
            JsonUtil.Write(new Dictionary<string, object>
            {
                { "request_id", JsonUtil.String(command, "request_id", "") },
                { "ok", ok },
                { "message", message ?? "" }
            });
        }

        private async void Execute(Dictionary<string, object> command)
        {
            string kind = JsonUtil.String(command, "command", "");
            try
            {
                if (kind == "show")
                {
                    Show(CapturePayload.From(command));
                    Reply(command, true, "");
                }
                else if (kind == "warm")
                {
                    bool ready = await _resourceBrowser.PrewarmAsync(JsonUtil.String(command, "origin", ""));
                    Reply(command, ready, ready ? "" : "资源管理器预热失败");
                }
                else if (kind == "focus")
                {
                    bool ok = _overlay != null && _overlay.IsVisible;
                    if (ok) _overlay.FocusOverlay();
                    Reply(command, ok, ok ? "" : "当前没有打开的捕获画面");
                }
                else if (kind == "hide")
                {
                    Hide(JsonUtil.String(command, "snapshot_id", ""), true);
                    Reply(command, true, "");
                }
                else if (kind == "shutdown")
                {
                    Hide("", false);
                    _resourceBrowser.Shutdown();
                    Reply(command, true, "");
                    _application.Shutdown();
                }
                else Reply(command, false, "未知宿主命令: " + kind);
            }
            catch (Exception ex)
            {
                Reply(command, false, ex.Message);
            }
        }

        private void Show(CapturePayload payload)
        {
            Hide("", false);
            if (!File.Exists(payload.SnapshotPath)) throw new FileNotFoundException("冻结帧文件不存在", payload.SnapshotPath);
            Forms.Screen target = Forms.Screen.FromRectangle(new System.Drawing.Rectangle(
                payload.Left, payload.Top, payload.Right - payload.Left, payload.Bottom - payload.Top));
            if (!target.Bounds.Contains(new System.Drawing.Rectangle(
                payload.Left, payload.Top, payload.Right - payload.Left, payload.Bottom - payload.Top)))
                throw new InvalidOperationException("目标工作面板跨越了多个显示器，请将窗口完整移到一个显示器后重试");
            foreach (Forms.Screen screen in Forms.Screen.AllScreens)
            {
                if (screen.DeviceName == target.DeviceName) continue;
                MaskWindow mask = new MaskWindow(screen);
                _masks.Add(mask);
                mask.Show();
            }
            _overlay = new CaptureOverlayWindow(payload, target, _resourceBrowser, delegate { Hide(payload.SnapshotId, true); });
            _overlay.Show();
            _overlay.FocusOverlay();
        }

        private void Hide(string snapshotId, bool notify)
        {
            CaptureOverlayWindow current = _overlay;
            _overlay = null;
            if (current != null)
            {
                _resourceBrowser.CancelPending();
                string closedId = String.IsNullOrEmpty(snapshotId) ? current.SnapshotId : snapshotId;
                current.CloseFromHost();
                if (notify)
                {
                    JsonUtil.Write(new Dictionary<string, object> { { "event", "closed" }, { "snapshot_id", closedId } });
                }
            }
            foreach (MaskWindow mask in _masks.ToArray())
            {
                try { mask.Close(); } catch { }
            }
            _masks.Clear();
        }
    }

    internal static class Program
    {
        [STAThread]
        private static void Main(string[] args)
        {
            NativeMethods.EnablePerMonitorV2();
            if (HasArgument(args, "--desktop-shell"))
            {
                RunDesktopShell(args);
                return;
            }

            JsonUtil.ConfigureRedirectedPipes();
            Application application = new Application();
            application.ShutdownMode = ShutdownMode.OnExplicitShutdown;
            OverlayHost host = new OverlayHost(application);
            host.Start();
            JsonUtil.Write(new Dictionary<string, object> { { "event", "ready" }, { "pid", System.Diagnostics.Process.GetCurrentProcess().Id } });
            application.Run();
        }

        private static bool HasArgument(string[] args, string expected)
        {
            foreach (string value in args ?? new string[0])
                if (String.Equals(value, expected, StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }

        private static string Argument(string[] args, string name, string fallback)
        {
            for (int index = 0; index + 1 < (args ?? new string[0]).Length; index++)
                if (String.Equals(args[index], name, StringComparison.OrdinalIgnoreCase)) return args[index + 1];
            return fallback;
        }

        private static int IntegerArgument(string[] args, string name, int fallback)
        {
            int parsed;
            return Int32.TryParse(Argument(args, name, ""), out parsed) ? parsed : fallback;
        }

        private static void RunDesktopShell(string[] args)
        {
            Application application = new Application();
            application.ShutdownMode = ShutdownMode.OnMainWindowClose;
            DesktopShellWindow window = new DesktopShellWindow(
                Argument(args, "--url", "http://127.0.0.1:8000/player.html"),
                Argument(args, "--title", "Easycode 自动化运行助手"),
                IntegerArgument(args, "--width", 960),
                IntegerArgument(args, "--height", 720));
            application.Run(window);
        }
    }
}
