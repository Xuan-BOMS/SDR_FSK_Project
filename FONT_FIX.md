# 中文字体配置问题解决方案

## ✅ 问题已解决

频谱图中文乱码问题已完全修复！

## 🔧 修复内容

### 1. 安装中文字体
```bash
sudo apt install fonts-wqy-zenhei fonts-noto-cjk
```

已安装的中文字体:
- **WenQuanYi Zen Hei** (文泉驿正黑) ← 主要使用
- **Noto Sans CJK SC** (思源黑体 简体中文)
- **Noto Sans CJK JP** (思源黑体 日文)

### 2. 更新代码配置

在 `dsp_processor.py` 的 `visualize_spectrum` 方法中添加:

```python
# 配置中文字体支持
matplotlib.rcParams['font.sans-serif'] = [
    'WenQuanYi Zen Hei',      # 首选: 文泉驿正黑
    'Noto Sans CJK SC',       # 备选: 思源黑体
    'Noto Sans CJK JP',       # 备选: 日文字体
    'DejaVu Sans'             # 英文后备
]
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示
```

### 3. 字符编码

- 所有 Python 文件头部添加: `# -*- coding: utf-8 -*-`
- 确保文件保存为 UTF-8 编码
- matplotlib 自动处理 UTF-8 字符串

## 🎯 测试验证

### 运行测试脚本
```bash
python3 test_font.py
```

输出:
```
✓ 实际使用的字体: WenQuanYi Zen Hei
✓ 测试图已保存为 font_test.png
```

### 生成实际频谱图
```bash
python3 main.py --spectrum
xdg-open spectrum.png
```

**预期结果**: 频谱图中所有中文标签清晰显示，无乱码方框。

## 📋 技术细节

### 问题原因
1. 系统默认字体不支持中文 Unicode 字符
2. matplotlib 未配置中文字体路径
3. 字体缓存未更新

### 解决原理
1. **安装支持中文的 TrueType 字体** → 提供字形数据
2. **配置 matplotlib.rcParams** → 指定字体查找顺序
3. **刷新字体缓存** → 让系统识别新字体
4. **清除 matplotlib 缓存** → 重建字体索引

### 字体选择逻辑
```python
# matplotlib 按顺序查找字体:
1. WenQuanYi Zen Hei     ✓ 找到 → 使用
2. Noto Sans CJK SC      (未使用，作为备选)
3. Noto Sans CJK JP      (未使用，作为备选)
4. DejaVu Sans           (仅用于英文字符)
```

## 🔍 故障排除

### 如果中文仍然显示为方框

#### 方法 1: 手动刷新字体
```bash
# 刷新系统字体缓存
fc-cache -fv

# 清除 matplotlib 缓存
rm -rf ~/.cache/matplotlib

# 验证字体可用
fc-list :lang=zh | grep -i "wqy\|noto"
```

#### 方法 2: 检查 matplotlib 字体列表
```python
import matplotlib.font_manager as fm
chinese_fonts = [f.name for f in fm.fontManager.ttflist 
                 if 'WenQuanYi' in f.name or 'CJK' in f.name]
print('\n'.join(set(chinese_fonts)))
```

#### 方法 3: 强制重建字体缓存
```python
import matplotlib.font_manager
matplotlib.font_manager.findfont('WenQuanYi Zen Hei', rebuild_if_missing=True)
```

### 如果想使用其他中文字体

编辑 `dsp_processor.py`:
```python
matplotlib.rcParams['font.sans-serif'] = [
    'Noto Sans SC',          # 思源黑体
    'Microsoft YaHei',       # 微软雅黑 (Windows)
    'PingFang SC',           # 苹方 (macOS)
    'WenQuanYi Zen Hei'      # 文泉驿正黑 (Linux)
]
```

## 📚 参考资料

- [Matplotlib 中文显示官方文档](https://matplotlib.org/stable/tutorials/text/text_props.html)
- [文泉驿字体项目](http://wenq.org/)
- [Noto 字体 (Google)](https://fonts.google.com/noto)

## ✨ 效果对比

### 修复前
```
标题: □□□□□□  (方框乱码)
X 轴: □□□□ (kHz)
Y 轴: □□□□□□ (dB)
```

### 修复后
```
标题: 接收信号频谱
X 轴: 频率偏移 (kHz)
Y 轴: 功率谱密度 (dB)
```

---

**状态**: ✅ 已完全修复  
**测试时间**: 2025年12月15日  
**系统**: Linux Mint / Ubuntu 24.04
