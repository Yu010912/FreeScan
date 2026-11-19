# FreeScan

**本地运行的智能图片扫描工具** —— 把手机拍摄的照片处理成干净、平直、高清的电子文档，支持无损导出 PNG / TIFF / 多页 PDF。

- 作者：**Yu010912**
- 邮箱：**2206394025@qq.com**
- GitHub：**https://github.com/Yu010912/FreeScan**
- 许可：**CC BY-NC 4.0（禁止商业使用，使用或分发请标注作者来源）**

---

## 功能

- **智能扫描**：自动识别纸张四角，校正透视，裁掉桌面与背景，并统一输出为 **A4 比例的原生分辨率文稿**。
- **去除阴影**：基于稳健光照曲面拟合的阴影消除，并用 S 曲线把纸张提为纯白、文字压为深黑。
- **三种处理模式**：原图（仅裁剪拉直）/ 增强（去阴影、纯白纸张）/ 黑白（文字更锐利）。
- **参数可调**：阴影去除、纸张提白、墨色加深、亮度、对比度、边缘内缩均可用滑条调整。
- **页面管理**：批量勾选、批量删除、上移 / 下移排序、旋转、删除、全选；项目可重命名或删除。
- **多格式导入**：PNG、JPG、JPEG、BMP、TIFF、WEBP、HEIC、HEIF。
- **无损导出**：
  - PNG：旋转为 0° 时直接复制处理结果，字节级一致；
  - TIFF：Deflate 无损压缩；
  - PDF：像素以 FlateDecode 无损嵌入，不做 JPEG 重编码，输出多页 A4 文档。
- **项目管理**：新建、重命名、删除项目；自动保存页面、原始图片、缩略图与处理参数。
- **批量导出**：页面勾选 / 全选，批量导出图片或多页 PDF。
- **双主题**：浅色 / 深色，简约清爽，自动记住上次选择。
- **纯本地**：不上传任何图片或项目数据，不依赖网络。
- **对比原图**：按住按钮即可查看未处理的原始照片。

## 快速开始

### 环境要求

- Windows 10 / 11（已在 Windows + Python 3.9.10 上测试）
- Python 3.9 – 3.12

### 安装与运行

```bat
cd FreeScan
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

也可以直接双击 `run.bat`（会自动使用项目内置的 `.venv`）。

## 使用流程

1. 点击 **新建项目**，输入项目名称。
2. 点击 **导入图片**，或把图片直接拖拽到窗口。
3. 导入时自动执行智能扫描：识别边缘 → 校正透视 → 消除阴影 → 生成高清 PNG。
4. 在左侧页面列表切换页面；可勾选多页批量删除，或用 **上移 / 下移** 调整页面顺序。
5. 在右侧选择 **原图 / 增强 / 黑白**，点击 **调整扫描参数** 可用滑条调节阴影、提白、墨色、亮度、对比度与边缘内缩。
6. 勾选需要导出的页面（或点击 **全选**），点击 **导出 ▾**：
   - **导出图片**：PNG / TIFF，全部页面或选中页面；
   - **导出 PDF**：按页面顺序合并为多页 A4 PDF。

项目名称旁的 **⋯** 菜单可以重命名项目、打开项目文件夹或删除项目。

按住预览下方的 **按住对比原图**，可以随时对照处理前后的差异。

## 无损保证

| 导出格式 | 编码方式 | 像素损失 |
| --- | --- | --- |
| PNG | 直接复制处理结果；旋转时使用无损转置 | 无 |
| TIFF | Deflate 无损压缩 | 无 |
| PDF | 原始 RGB 像素 FlateDecode 嵌入，A4 页面（原生像素） | 无 |

> 说明：如果导入的源文件本身是 JPG / HEIF，源文件已经过有损压缩；FreeScan 不会再进行任何二次压缩或缩放。扫描时保持 A4 比例与原生分辨率，不主动缩小像素；导出的 DPI 元数据按实际像素尺寸计算。

## 智能扫描说明

FreeScan 的“智能扫描”基于计算机视觉算法，全部在本机完成：

- **边缘检测**：Canny + 轮廓近似，辅以纸张亮度分割候选；按面积、边缘贴合度、纸张亮度与矩形度综合评分选择最佳四角。
- **透视校正**：四点透视变换；四角向内收缩约 0.65%，避免把纸张外的桌面、阴影带入结果。
- **标准尺寸**：输出保持 A4 比例；像素尺寸沿用源图的原生分辨率，DPI 元数据按实际尺寸计算（例如 600+ DPI），不强制降采样到 300 DPI。
- **阴影消除**：在降采样图上用稳健二次多项式拟合纸张光照曲面（自动剔除文字等暗部样本），再按光照增益归一化，避免大面积阴影与渐变残留。
- **纸张提白**：亮度归一化、白点提升、局部色偏校正与亮部平滑，得到干净的白纸背景。
- **黑白模式**：自适应高斯阈值 + 中值去噪，适合文字、票据与表格。

当画面中没有可靠的纸张四角时，会按 A4 比例居中裁剪原图，仍输出标准尺寸，不会破坏原图。

## 技术参考

本项目为自研实现，开发过程中参考了以下公开资料与开源方案：

- [Complete Scanning Application Using OpenCV（FCPT 四点透视校正）](https://arxiv.org/ftp/arxiv/papers/2107/2107.03700.pdf)
- [page-dewarp：文档页面去弯曲](https://pypi.org/project/page-dewarp/)
- [DocumentShadowRemoval：文档阴影检测与去除数据集](https://github.com/BingshuCV/DocumentShadowRemoval)
- [OpenCV Forum：利用灰度膨胀估计光照并做除法归一化](https://forum.opencv.org/t/optic-marker-recognition/14335)
- [Dynamsoft：文档检测、裁剪与归一化](https://www.dynamsoft.com/codepool/html5-web-document-detect-crop-save.html)

## 数据位置

- 项目库：`C:\Users\<用户名>\Documents\FreeScan`
- 应用配置：`%APPDATA%\FreeScan\settings.json`
- 每个项目包含：
  - `project.json`：页面、模式、旋转、边缘坐标等元数据；
  - `sources/`：导入的原始图片副本；
  - `pages/`：全分辨率无损处理结果（PNG）；
  - `.thumbs/`：仅用于界面展示的缩略图。

可通过环境变量 `FREESCAN_LIBRARY` 指定其他项目库目录。

## 快捷键与交互

- `Ctrl + N`：新建项目
- `Ctrl + O`：导入图片
- 鼠标滚轮：缩放预览
- 双击预览：适应窗口
- 按住“对比原图”：查看未处理照片

## 技术栈

- UI：PySide6（Qt for Python）
- 图像处理：OpenCV、NumPy、Pillow、pillow-heif
- PDF：自研无损 PDF 写入器（FlateDecode，无第三方 PDF 编码）

## 已知限制

- 仅实现本地图片导入，不包含摄像头连续拍摄、OCR、云同步与账号系统。
- 输出保持 A4 比例；DPI 随源图分辨率变化，不再固定为 300 DPI。非 A4 纸张（如小票、名片）会按 A4 比例适配。
- 仅处理平面纸张与透视变形，不包含曲面书页去弯曲。
- 自动边缘检测在纸张与背景对比度极低时可能无法准确定位四角，此时按 A4 比例居中裁剪。
- HEIF 解码依赖 `pillow-heif`；少数特殊编码的 HEIC 可能无法读取。
- 界面按桌面端设计，当前主要面向 Windows。

## 许可与署名

本项目采用 **Creative Commons Attribution-NonCommercial 4.0 International（CC BY-NC 4.0）** 许可：

- **禁止商业使用**：不得将本软件或衍生作品用于任何商业目的。
- **必须署名**：复制、分发、修改或以其他方式使用本项目时，必须保留以下署名，并注明来源：
  > FreeScan by Yu010912 — https://github.com/Yu010912/FreeScan
- 许可全文：https://creativecommons.org/licenses/by-nc/4.0/legalcode

详见 [LICENSE](LICENSE)。

## 第三方组件许可

- PySide6 / Qt：LGPL v3
- OpenCV：Apache License 2.0
- Pillow：HPND License
- pillow-heif：BSD 3-Clause License
- NumPy：BSD 3-Clause License

以上组件遵循各自许可证；CC BY-NC 4.0 仅适用于本项目的原创代码与资源。
