# core/emulator_presets.py
# 模拟器预设偏移表（只保留雷电和MuMu，其余不裁剪）

EMULATOR_PRESETS = {
    '雷电': {'top': 40, 'bottom': 50, 'left': 0, 'right': 0},
    'ldplayer': {'top': 40, 'bottom': 50, 'left': 0, 'right': 0},
    'mumu': {'top': 35, 'bottom': 45, 'left': 0, 'right': 0},
}


def get_emulator_offset(title):
    """根据窗口标题匹配预设偏移，若无匹配则返回零偏移（不裁剪）"""
    title_lower = title.lower()
    for keyword, offset in EMULATOR_PRESETS.items():
        if keyword.lower() in title_lower:
            return offset
    return {'top': 0, 'bottom': 0, 'left': 0, 'right': 0}
