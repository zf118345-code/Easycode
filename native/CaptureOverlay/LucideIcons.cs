using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Shapes;

namespace Easycode.CaptureOverlay
{
    /// <summary>
    /// Lucide icons rendered as native WPF vector paths. Keeping the original
    /// 24x24 stroke geometry avoids font/symbol differences across machines.
    /// </summary>
    internal static class LucideIcons
    {
        private static readonly Dictionary<string, string[]> Paths = new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase)
        {
            { "crosshair", new[] {
                "M12,2 L12,6", "M12,18 L12,22", "M4.93,4.93 L7.76,7.76",
                "M16.24,16.24 L19.07,19.07", "M2,12 L6,12", "M18,12 L22,12",
                "M4.93,19.07 L7.76,16.24", "M16.24,7.76 L19.07,4.93",
                "M12,8 A4,4 0 1 1 12,16 A4,4 0 1 1 12,8"
            } },
            { "image", new[] {
                "M5,3 L19,3 A2,2 0 0 1 21,5 L21,19 A2,2 0 0 1 19,21 L5,21 A2,2 0 0 1 3,19 L3,5 A2,2 0 0 1 5,3",
                "M9,8 A1,1 0 1 1 7,8 A1,1 0 1 1 9,8", "M21,15 L16,10 L5,21"
            } },
            { "scan-text", new[] {
                "M3,7 L3,5 A2,2 0 0 1 5,3 L7,3", "M17,3 L19,3 A2,2 0 0 1 21,5 L21,7",
                "M21,17 L21,19 A2,2 0 0 1 19,21 L17,21", "M7,21 L5,21 A2,2 0 0 1 3,19 L3,17",
                "M7,8 L17,8", "M7,12 L17,12", "M7,16 L13,16"
            } },
            { "layers", new[] {
                "M12,2 L2,7 L12,12 L22,7 L12,2", "M2,12 L12,17 L22,12", "M2,17 L12,22 L22,17"
            } },
            { "download", new[] {
                "M21,15 L21,19 A2,2 0 0 1 19,21 L5,21 A2,2 0 0 1 3,19 L3,15",
                "M7,10 L12,15 L17,10", "M12,15 L12,3"
            } },
            { "trash", new[] {
                "M3,6 L21,6", "M8,6 L8,4 A1,1 0 0 1 9,3 L15,3 A1,1 0 0 1 16,4 L16,6",
                "M19,6 L18,20 A2,2 0 0 1 16,22 L8,22 A2,2 0 0 1 6,20 L5,6",
                "M10,11 L10,17", "M14,11 L14,17"
            } },
            { "check", new[] { "M20,6 L9,17 L4,12" } },
            { "x", new[] { "M18,6 L6,18", "M6,6 L18,18" } },
            { "corner-up-left", new[] { "M9,14 L4,9 L9,4", "M4,9 L14,9 A6,6 0 0 1 20,15 L20,20" } },
            { "folder-open", new[] {
                "M6,14 L8,12 L22,12 L19,21 L3,21 A2,2 0 0 1 1,19 L1,5 A2,2 0 0 1 3,3 L8,3 L10,6 L19,6 A2,2 0 0 1 21,8 L21,9"
            } }
        };

        internal static FrameworkElement Create(string name, double size, string color)
        {
            Grid canvas = new Grid { Width = 24, Height = 24 };
            string[] values;
            if (!Paths.TryGetValue(name, out values)) values = Paths["x"];
            foreach (string value in values)
            {
                Path path = new Path
                {
                    Data = Geometry.Parse(value),
                    Stroke = new SolidColorBrush((Color)ColorConverter.ConvertFromString(color)),
                    StrokeThickness = 2,
                    StrokeStartLineCap = PenLineCap.Round,
                    StrokeEndLineCap = PenLineCap.Round,
                    StrokeLineJoin = PenLineJoin.Round,
                    Fill = Brushes.Transparent,
                    SnapsToDevicePixels = true
                };
                canvas.Children.Add(path);
            }
            return new Viewbox { Width = size, Height = size, Stretch = Stretch.Uniform, Child = canvas };
        }
    }
}
