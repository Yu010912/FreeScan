"""无损 PDF 写入：像素数据直接以 FlateDecode 原样嵌入，不做 JPEG 重编码。"""
from __future__ import annotations

import os
import zlib
from typing import Iterable, List

from PIL import Image

A4_WIDTH = 595.276
A4_HEIGHT = 841.89


def _pdf_text(value: str) -> bytes:
    """输出 PDF 字符串；非 ASCII 使用 UTF-16BE 十六进制字符串。"""
    cleaned = value.replace("\r", " ").replace("\n", " ")
    try:
        cleaned.encode("ascii")
        escaped = cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return f"({escaped})".encode("ascii")
    except UnicodeEncodeError:
        return b"<FEFF" + cleaned.encode("utf-16-be").hex().upper().encode("ascii") + b">"


def _stream_object(data: bytes, extra: bytes = b"") -> bytes:
    return (
        b"<< " + extra + b" /Length " + str(len(data)).encode("ascii") + b" >>\nstream\n"
        + data
        + b"\nendstream"
    )


def _page_layout(width: int, height: int, dpi: int) -> tuple:
    """按图片比例选择 A4 横/竖版，返回页面尺寸与绘制矩形。"""
    portrait = height >= width
    page_width = A4_WIDTH if portrait else A4_HEIGHT
    page_height = A4_HEIGHT if portrait else A4_WIDTH

    image_width_pt = width / float(dpi) * 72.0
    image_height_pt = height / float(dpi) * 72.0
    scale = min(page_width / image_width_pt, page_height / image_height_pt)
    draw_width = image_width_pt * scale
    draw_height = image_height_pt * scale
    offset_x = (page_width - draw_width) / 2.0
    offset_y = (page_height - draw_height) / 2.0
    return page_width, page_height, draw_width, draw_height, offset_x, offset_y


def write_pdf(
    images: Iterable[Image.Image],
    destination: str,
    dpi: int = 300,
    title: str = "FreeScan",
) -> str:
    images: List[Image.Image] = list(images)
    if not images:
        raise ValueError("没有可导出的页面")

    page_ids = []
    content_ids = []
    image_ids = []
    for index in range(len(images)):
        base = 3 + index * 3
        page_ids.append(base)
        content_ids.append(base + 1)
        image_ids.append(base + 2)
    info_id = 3 + len(images) * 3

    objects: List[bytes] = [b"<placeholder-catalog>", b"<placeholder-pages>"]

    for index, image in enumerate(images):
        if image.mode != "RGB":
            image = image.convert("RGB")
        width, height = image.size
        raw = image.tobytes()
        compressed = zlib.compress(raw, 6)

        page_width, page_height, draw_width, draw_height, offset_x, offset_y = _page_layout(
            width, height, dpi
        )

        image_object = _stream_object(
            compressed,
            (
                f"/Type /XObject /Subtype /Image /Width {width} /Height {height} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode"
            ).encode("ascii"),
        )

        content = (
            f"q\n{draw_width:.3f} 0 0 {draw_height:.3f} {offset_x:.3f} {offset_y:.3f} cm\n"
            f"/Im0 Do\nQ\n"
        ).encode("ascii")
        content_object = _stream_object(content)

        page_object = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width:.3f} {page_height:.3f}] "
            f"/Resources << /XObject << /Im0 {image_ids[index]} 0 R >> >> "
            f"/Contents {content_ids[index]} 0 R >>"
        ).encode("ascii")

        objects.append(page_object)
        objects.append(content_object)
        objects.append(image_object)

    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[1] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"
    ).encode("ascii")

    info = (
        b"<< /Title " + _pdf_text(title or "FreeScan")
        + b" /Producer " + _pdf_text("FreeScan 1.0.0")
        + b" /Creator " + _pdf_text("FreeScan by Yu010912")
        + b" >>"
    )
    objects.append(info)

    buffer = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (len(objects) + 1)
    for index, body in enumerate(objects, start=1):
        offsets[index] = len(buffer)
        buffer += f"{index} 0 obj\n".encode("ascii")
        buffer += body
        buffer += b"\nendobj\n"

    xref_offset = len(buffer)
    buffer += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    buffer += b"0000000000 65535 f \n"
    for index in range(1, len(objects) + 1):
        buffer += f"{offsets[index]:010d} 00000 n \n".encode("ascii")
    buffer += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info {info_id} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")

    folder = os.path.dirname(os.path.abspath(destination))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(destination, "wb") as handle:
        handle.write(buffer)
    return destination
