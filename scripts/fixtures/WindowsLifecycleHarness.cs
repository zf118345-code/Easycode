using System;
using System.Drawing;
using System.Windows.Forms;

namespace EasyCode.Acceptance
{
    internal static class WindowsLifecycleHarness
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            var form = new Form
            {
                Text = "EasyCode Windows 生命周期验收",
                StartPosition = FormStartPosition.CenterScreen,
                ClientSize = new Size(520, 220),
                FormBorderStyle = FormBorderStyle.FixedDialog,
                MaximizeBox = false,
                MinimizeBox = true
            };
            form.Controls.Add(new Label
            {
                AutoSize = true,
                Location = new Point(32, 42),
                Text = "此窗口由 EasyCode 冻结 Player 启动。"
            });
            form.Controls.Add(new TextBox
            {
                Name = "AcceptanceInput",
                Location = new Point(32, 88),
                Width = 440,
                Text = "等待生命周期测试"
            });
            form.Controls.Add(new Button
            {
                Name = "AcceptanceButton",
                Location = new Point(32, 136),
                Width = 160,
                Text = "验收控件"
            });
            Application.Run(form);
        }
    }
}
