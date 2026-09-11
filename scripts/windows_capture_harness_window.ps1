Add-Type -AssemblyName PresentationFramework

$window = [System.Windows.Window]::new()
$window.Title = 'EasyCode Capture Harness'
$window.Width = 720
$window.Height = 480
$window.WindowStartupLocation = 'CenterScreen'

$panel = [System.Windows.Controls.StackPanel]::new()
$panel.Margin = [System.Windows.Thickness]::new(32)

$title = [System.Windows.Controls.TextBlock]::new()
$title.Text = 'Windows 捕获与控件验收窗口'
$title.FontSize = 26
$title.Margin = [System.Windows.Thickness]::new(0, 0, 0, 24)
$panel.Children.Add($title) | Out-Null

$input = [System.Windows.Controls.TextBox]::new()
$input.Name = 'HarnessInput'
$input.Text = 'EasyCode Windows UIA'
$input.FontSize = 18
$input.Margin = [System.Windows.Thickness]::new(0, 0, 0, 20)
$panel.Children.Add($input) | Out-Null

$button = [System.Windows.Controls.Button]::new()
$button.Name = 'HarnessButton'
$button.Content = '捕获这个按钮'
$button.Width = 220
$button.Height = 56
$button.HorizontalAlignment = 'Left'
$panel.Children.Add($button) | Out-Null

$status = [System.Windows.Controls.TextBlock]::new()
$status.Text = '等待操作'
$status.FontSize = 18
$status.Margin = [System.Windows.Thickness]::new(0, 24, 0, 0)
$panel.Children.Add($status) | Out-Null
$button.Add_Click({ $status.Text = '按钮已点击' })

$window.Content = $panel
$window.ShowDialog() | Out-Null
