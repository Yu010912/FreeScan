"""图像导入与智能文档处理。

提供 HEIF/PNG/JPG/TIFF 等格式读取、文档边缘自动检测、透视校正、
基于多项式光照模型的阴影消除、A4 标准尺寸输出与黑白二值化。
"""
from __future__ import annotations

import os
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps

try:  # HEIF/HEIC 支持
    from pillow_heif import register_heif_opener

    register_heif_opener(thumbnails=False)
    HEIF_SUPPORTED = True
except Exception:  # pragma: no cover - 缺少依赖时降级
    HEIF_SUPPORTED = False


SUPPORTED_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".heic",
    ".heif",
)

MODE_ORIGINAL = "original"
MODE_ENHANCE = "enhance"
MODE_BW = "bw"

MODE_LABELS = {
    MODE_ORIGINAL: "原图",
    MODE_ENHANCE: "增强",
    MODE_BW: "黑白",
}

# A4 300 DPI 标准像素尺寸（用于参考与旧数据）
A4_PORTRAIT = (2480, 3508)
A4_LANDSCAPE = (3508, 2480)
A4_PORTRAIT_RATIO = A4_PORTRAIT[1] / A4_PORTRAIT[0]
A4_WIDTH_IN = 210.0 / 25.4
A4_HEIGHT_IN = 297.0 / 25.4
OUTPUT_DPI = 300

DEFAULT_OPTIONS = {
    "shadow": 80,
    "whiten": 70,
    "ink": 60,
    "brightness": 0,
    "contrast": 10,
    "inset": 0.65,
}


def normalize_options(options: Optional[dict] = None) -> dict:
    merged = dict(DEFAULT_OPTIONS)
    if options:
        for key in merged:
            if key in options and options[key] is not None:
                try:
                    merged[key] = float(options[key])
                except (TypeError, ValueError):
                    pass
    merged["shadow"] = float(np.clip(merged["shadow"], 0, 100))
    merged["whiten"] = float(np.clip(merged["whiten"], 0, 100))
    merged["ink"] = float(np.clip(merged["ink"], 0, 100))
    merged["brightness"] = float(np.clip(merged["brightness"], -50, 50))
    merged["contrast"] = float(np.clip(merged["contrast"], -50, 50))
    merged["inset"] = float(np.clip(merged["inset"], 0, 2))
    return merged

# 四角向内收缩比例，避免把纸张外的桌面/阴影带入结果
DOCUMENT_INSET = 0.0065


class ImageLoadError(Exception):
    pass


def is_supported(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_EXTENSIONS


def load_image(path: str) -> Image.Image:
    """读取图片并统一为 RGB，应用 EXIF 方向。"""
    try:
        img = Image.open(path)
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise ImageLoadError(f"无法读取图片：{os.path.basename(path)}（{exc}）") from exc

    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(background, img).convert("RGB")
    else:
        img = img.convert("RGB")
    return img


def pil_to_bgr(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def bgr_to_pil(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))


def _order_points(points: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    rect[0] = points[np.argmin(sums)]  # 左上
    rect[2] = points[np.argmax(sums)]  # 右下
    diffs = np.diff(points, axis=1)
    rect[1] = points[np.argmin(diffs)]  # 右上
    rect[3] = points[np.argmax(diffs)]  # 左下
    return rect


def _quad_area(pts: np.ndarray) -> float:
    return float(abs(cv2.contourArea(pts.reshape(-1, 1, 2).astype(np.float32))))


def _score_quad(
    quad_small: np.ndarray,
    gray: np.ndarray,
    edges: np.ndarray,
) -> float:
    """对候选四边形打分：面积、边缘贴合、纸张亮度与矩形度。"""
    h, w = gray.shape[:2]
    image_area = float(h * w)
    pts = quad_small.reshape(-1, 2).astype(np.float32)
    area = _quad_area(pts)
    if area <= 0:
        return -1.0
    area_ratio = area / image_area
    if area_ratio < 0.12 or area_ratio > 0.995:
        return -1.0

    rect = cv2.minAreaRect(pts)
    rect_area = float(rect[1][0] * rect[1][1])
    rectangularity = min(1.0, area / rect_area) if rect_area > 0 else 0.0

    mask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(mask, pts.astype(np.int32), 255)
    kernel = np.ones((11, 11), np.uint8)
    inner = cv2.erode(mask, kernel, iterations=1)
    outer = cv2.bitwise_and(255 - cv2.dilate(mask, kernel, iterations=1), np.full_like(mask, 255))
    mean_in = float(cv2.mean(gray, mask=inner)[0]) if cv2.countNonZero(inner) else 0.0
    mean_out = float(cv2.mean(gray, mask=outer)[0]) if cv2.countNonZero(outer) else 0.0
    brightness_gain = (mean_in - mean_out) / 255.0

    band = np.zeros((h, w), np.uint8)
    cv2.polylines(band, [pts.astype(np.int32)], True, 255, 5)
    band_pixels = int(cv2.countNonZero(band))
    support = float(cv2.countNonZero(cv2.bitwise_and(edges, band))) / band_pixels if band_pixels else 0.0

    margin = min(h, w) * 0.008
    touch = min(
        float(pts[:, 0].min()),
        float(pts[:, 1].min()),
        float(w - 1 - pts[:, 0].max()),
        float(h - 1 - pts[:, 1].max()),
    )
    border_penalty = 0.0 if touch >= margin else -0.18

    return (
        0.42 * area_ratio
        + 0.22 * support
        + 0.24 * max(0.0, brightness_gain * 3.0)
        + 0.12 * rectangularity
        + border_penalty
    )


def _paper_mask_quad(gray: np.ndarray) -> Optional[np.ndarray]:
    """用亮度分割提取纸张轮廓，作为边缘检测失败或评分时的候选。"""
    h, w = gray.shape[:2]
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if cv2.countNonZero(mask) == 0:
        return None
    if gray[mask > 0].mean() < gray[mask == 0].mean():
        mask = 255 - mask

    kernel_size = max(9, int(min(h, w) * 0.02) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < h * w * 0.15:
        return None

    perimeter = cv2.arcLength(contour, True)
    for epsilon in (0.02, 0.03, 0.045):
        approx = cv2.approxPolyDP(contour, epsilon * perimeter, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return approx.reshape(4, 2).astype(np.float32)
    box = cv2.boxPoints(cv2.minAreaRect(contour))
    return box.astype(np.float32)


def detect_document(img: Image.Image) -> Optional[List[Tuple[float, float]]]:
    """检测画面中的文档四角，返回原图坐标；未检测到返回 None。"""
    bgr = pil_to_bgr(img)
    h, w = bgr.shape[:2]
    if h < 64 or w < 64:
        return None

    longest = max(h, w)
    scale = 900.0 / longest if longest > 900 else 1.0
    if scale < 1.0:
        small = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        small = bgr

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 140)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    candidates: List[np.ndarray] = []

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:12]
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        for epsilon in (0.015, 0.02, 0.03):
            approx = cv2.approxPolyDP(contour, epsilon * perimeter, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                candidates.append(approx.reshape(4, 2).astype(np.float32))
                break

    paper_quad = _paper_mask_quad(gray)
    if paper_quad is not None:
        candidates.append(paper_quad)

    best: Optional[np.ndarray] = None
    best_score = -1.0
    for candidate in candidates:
        score = _score_quad(candidate, gray, edges)
        if score > best_score:
            best_score = score
            best = candidate

    if best is None or best_score <= 0:
        return None

    pts = best.reshape(4, 2).astype(np.float32)
    if scale < 1.0:
        pts /= scale
    pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
    pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
    return [(float(x), float(y)) for x, y in pts]


def _quad_dimensions(pts: np.ndarray) -> Tuple[float, float]:
    top_left, top_right, bottom_right, bottom_left = pts
    width = max(
        float(np.linalg.norm(bottom_right - bottom_left)),
        float(np.linalg.norm(top_right - top_left)),
    )
    height = max(
        float(np.linalg.norm(top_right - bottom_right)),
        float(np.linalg.norm(top_left - bottom_left)),
    )
    return width, height


def _a4_native_size(width: float, height: float) -> Tuple[int, int]:
    """在保持 A4 比例的前提下使用原生像素尺寸，避免缩小原始扫描稿。"""
    if height >= width:
        ratio = A4_WIDTH_IN / A4_HEIGHT_IN
        target_width = max(width, height * ratio)
        target_height = target_width / ratio
    else:
        ratio = A4_HEIGHT_IN / A4_WIDTH_IN
        target_height = max(height, width / ratio)
        target_width = target_height * ratio
    return max(16, int(round(target_width))), max(16, int(round(target_height)))


def _warp_to_standard(
    bgr: np.ndarray,
    quad: Sequence[Tuple[float, float]],
    inset_percent: float = 0.65,
) -> np.ndarray:
    """把检测到的纸张区域校正为 A4 比例，并保留原生像素分辨率。"""
    pts = _order_points(np.array(quad, dtype=np.float32))
    inset = float(np.clip(inset_percent, 0.0, 2.0)) / 100.0
    center = pts.mean(axis=0)
    pts = center + (pts - center) * (1.0 - 2.0 * inset)

    width, height = _quad_dimensions(pts)
    if width < 16 or height < 16:
        return _standard_fallback(bgr)

    target = _a4_native_size(width, height)
    dst = np.array(
        [
            [0, 0],
            [target[0] - 1, 0],
            [target[0] - 1, target[1] - 1],
            [0, target[1] - 1],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(pts, dst)
    return cv2.warpPerspective(
        bgr,
        matrix,
        target,
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _standard_fallback(bgr: np.ndarray) -> np.ndarray:
    """未检测到纸张时按 A4 比例居中裁剪，保留原始像素。"""
    h, w = bgr.shape[:2]
    portrait = h >= w
    target_ratio = (A4_WIDTH_IN / A4_HEIGHT_IN) if portrait else (A4_HEIGHT_IN / A4_WIDTH_IN)
    image_ratio = w / max(1, h)
    if image_ratio > target_ratio:
        crop_w = max(1, int(round(h * target_ratio)))
        crop_h = h
        x0 = (w - crop_w) // 2
        y0 = 0
    else:
        crop_w = w
        crop_h = max(1, int(round(w / target_ratio)))
        x0 = 0
        y0 = (h - crop_h) // 2
    return bgr[y0 : y0 + crop_h, x0 : x0 + crop_w].copy()


def _illumination_surface(bgr: np.ndarray, degree: int = 2) -> np.ndarray:
    """用稳健多项式曲面拟合纸张背景亮度，返回与原图同尺寸的光照图。"""
    h, w = bgr.shape[:2]
    small_w = 620
    small_h = max(2, int(round(small_w * h / max(1, w))))
    small = cv2.resize(bgr, (small_w, small_h), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
    lightness = lab[:, :, 0].astype(np.float32)

    ys, xs = np.mgrid[0:small_h, 0:small_w].astype(np.float32)
    x = (xs / max(1, small_w - 1)) * 2.0 - 1.0
    y = (ys / max(1, small_h - 1)) * 2.0 - 1.0
    terms = [np.ones_like(x), x, y, x * x, x * y, y * y]
    if degree >= 3:
        terms += [x * x * x, x * x * y, x * y * y, y * y * y]
    design = np.stack([term.ravel() for term in terms], axis=1)
    values = lightness.ravel()

    mask = values > 60.0
    if int(mask.sum()) < 1000:
        surface = np.full((small_h, small_w), 220.0, dtype=np.float32)
    else:
        coefficient = None
        for _ in range(3):
            coefficient, *_ = np.linalg.lstsq(design[mask], values[mask], rcond=None)
            residual = values - design @ coefficient
            limit = max(10.0, float(np.percentile(np.abs(residual[mask]), 55)))
            refined = (values > 60.0) & (np.abs(residual) < limit)
            if int(refined.sum()) < 1000:
                break
            mask = refined
        if coefficient is None:
            surface = np.full((small_h, small_w), 220.0, dtype=np.float32)
        else:
            surface = (design @ coefficient).reshape(small_h, small_w)
            surface = np.clip(surface, 50.0, 255.0)

    return cv2.resize(surface, (w, h), interpolation=cv2.INTER_CUBIC)


def _enhance_document(bgr: np.ndarray, options: Optional[dict] = None) -> np.ndarray:
    """消除阴影与光照不均，并用 S 曲线得到接近电子文稿的纯白纸张与深黑文字。"""
    opts = normalize_options(options)
    surface = _illumination_surface(bgr, degree=2)
    strength = opts["shadow"] / 100.0
    gain = 1.0 + (252.0 / np.maximum(surface, 1.0) - 1.0) * strength
    normalized = np.clip(bgr.astype(np.float32) * gain[..., None], 0, 255)

    lab = cv2.cvtColor(normalized.astype(np.uint8), cv2.COLOR_BGR2LAB)
    lightness, a_chan, b_chan = cv2.split(lab)
    lightness = lightness.astype(np.float32)

    paper_level = float(np.percentile(lightness, 90))
    if paper_level > 30:
        lightness = np.clip(lightness * (250.0 / paper_level), 0, 255)

    # 以纸张亮部和文字暗部为锚点，做平滑 S 曲线
    dark_level = float(np.percentile(lightness, 3))
    bright_level = float(np.percentile(lightness, 25))
    black_point = float(np.clip(dark_level + (opts["ink"] - 60.0) * 0.7, 20, 150))
    white_point = float(np.clip(bright_level - (opts["whiten"] - 60.0) * 0.35, black_point + 45, 248))
    if white_point <= black_point + 10:
        white_point = black_point + 10

    normalized_levels = np.clip((lightness - black_point) / (white_point - black_point), 0, 1)
    normalized_levels = normalized_levels * normalized_levels * (3.0 - 2.0 * normalized_levels)
    lightness = normalized_levels * 255.0

    if opts["brightness"]:
        lightness = lightness + opts["brightness"] * 1.2
    if opts["contrast"]:
        lightness = 128.0 + (lightness - 128.0) * (1.0 + opts["contrast"] / 100.0)
    lightness = np.clip(lightness, 0, 255)

    # 去除局部色偏
    a_float = a_chan.astype(np.float32)
    b_float = b_chan.astype(np.float32)
    a_float += (128.0 - float(a_float.mean())) * 0.5
    b_float += (128.0 - float(b_float.mean())) * 0.5

    merged = cv2.merge(
        [
            lightness.astype(np.uint8),
            np.clip(a_float, 0, 255).astype(np.uint8),
            np.clip(b_float, 0, 255).astype(np.uint8),
        ]
    )
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def _binarize(bgr: np.ndarray, options: Optional[dict] = None) -> np.ndarray:
    """在增强结果上做自适应二值化，得到纯净的黑白文档。"""
    enhanced = _enhance_document(bgr, options)
    gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 5, 35, 35)
    block_size = min(51, max(3, (min(gray.shape[:2]) // 2) | 1))
    if block_size % 2 == 0:
        block_size += 1
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        12,
    )
    binary = cv2.medianBlur(binary, 3)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def render_processed(
    source_path: str,
    quad: Optional[Sequence[Tuple[float, float]]],
    mode: str,
    options: Optional[dict] = None,
) -> Image.Image:
    """按指定模式处理源图，输出 A4 比例、原生分辨率的 RGB 图像。"""
    opts = normalize_options(options)
    source = load_image(source_path)
    bgr = pil_to_bgr(source)
    if quad:
        try:
            bgr = _warp_to_standard(bgr, quad, opts["inset"])
        except cv2.error:
            bgr = _standard_fallback(bgr)
    else:
        bgr = _standard_fallback(bgr)

    if mode == MODE_ENHANCE:
        bgr = _enhance_document(bgr, opts)
    elif mode == MODE_BW:
        bgr = _binarize(bgr, opts)

    return bgr_to_pil(bgr)


def process_to_png(
    source_path: str,
    quad: Optional[Sequence[Tuple[float, float]]],
    mode: str,
    output_path: str,
    options: Optional[dict] = None,
) -> Tuple[int, int, float]:
    """处理并写出无损 PNG，返回像素尺寸与 A4 对应的 DPI。"""
    image = render_processed(source_path, quad, mode, options)
    width, height = image.size
    dpi = width / (A4_WIDTH_IN if height >= width else A4_HEIGHT_IN)
    dpi = round(float(dpi), 2)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    image.save(output_path, "PNG", compress_level=6, dpi=(dpi, dpi))
    return width, height, dpi


def write_thumbnail(image_path: str, thumb_path: str, max_edge: int = 420) -> None:
    try:
        with Image.open(image_path) as img:
            save_thumbnail_image(img.convert("RGB"), thumb_path, max_edge)
    except Exception:  # noqa: BLE001 - 缩略图失败不影响主流程
        pass


def save_thumbnail_image(image: Image.Image, thumb_path: str, max_edge: int = 420) -> None:
    try:
        thumb = image.copy()
        thumb.thumbnail((max_edge, max_edge), Image.LANCZOS)
        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
        thumb.save(thumb_path, "JPEG", quality=86, optimize=True)
    except Exception:  # noqa: BLE001
        pass


def rotate_image(img: Image.Image, rotation: int) -> Image.Image:
    """rotation 为 90 的整数倍，使用转置保证无像素损失。"""
    steps = (rotation // 90) % 4
    if steps == 1:
        return img.transpose(Image.ROTATE_270)
    if steps == 2:
        return img.transpose(Image.ROTATE_180)
    if steps == 3:
        return img.transpose(Image.ROTATE_90)
    return img
