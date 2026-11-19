"""项目库：本地项目管理、页面记录与无损导出。"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence

from PIL import Image

from . import imaging
from .pdf_export import write_pdf


APP_NAME = "FreeScan"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def default_library_root() -> Path:
    override = os.environ.get("FREESCAN_LIBRARY")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        try:
            import ctypes

            buffer = ctypes.create_unicode_buffer(260)
            # CSIDL_PERSONAL：正确的“文档”路径（兼容 OneDrive 重定向）
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0 and buffer.value:
                return Path(buffer.value) / APP_NAME
        except Exception:  # noqa: BLE001
            pass
    documents = Path.home() / "Documents"
    if not documents.exists():
        documents = Path.home()
    return documents / APP_NAME


def _safe_filename(name: str, fallback: str = "未命名") -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n]+', "_", name).strip().strip(".")
    return cleaned or fallback


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{time.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"


@dataclass
class Page:
    id: str
    source: str
    processed: str
    thumb: str
    original_name: str = ""
    mode: str = imaging.MODE_ENHANCE
    rotation: int = 0
    width: int = 0
    height: int = 0
    dpi: float = 300.0
    adjustments: dict = field(default_factory=dict)
    quad: Optional[List[List[float]]] = None
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "processed": self.processed,
            "thumb": self.thumb,
            "original_name": self.original_name,
            "mode": self.mode,
            "rotation": self.rotation,
            "width": self.width,
            "height": self.height,
            "dpi": self.dpi,
            "adjustments": self.adjustments,
            "quad": self.quad,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Page":
        return cls(
            id=data["id"],
            source=data["source"],
            processed=data["processed"],
            thumb=data.get("thumb", ""),
            original_name=data.get("original_name", ""),
            mode=data.get("mode", imaging.MODE_ENHANCE),
            rotation=int(data.get("rotation", 0)),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            dpi=float(data.get("dpi", 300.0)),
            adjustments=imaging.normalize_options(data.get("adjustments")),
            quad=data.get("quad"),
            created_at=data.get("created_at", _now_iso()),
        )


@dataclass
class Project:
    id: str
    name: str
    root: Path
    pages: List[Page] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    @property
    def metadata_path(self) -> Path:
        return self.root / "project.json"

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def cover_path(self) -> Optional[Path]:
        if self.pages:
            thumb = self.root / self.pages[0].thumb
            if thumb.exists():
                return thumb
            processed = self.root / self.pages[0].processed
            if processed.exists():
                return processed
        return None

    def to_dict(self) -> dict:
        return {
            "schema": 1,
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pages": [page.to_dict() for page in self.pages],
        }

    def save(self) -> None:
        self.updated_at = _now_iso()
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.metadata_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.metadata_path)


class ProjectLibrary:
    """管理项目目录，所有修改自动写入 project.json。"""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root else default_library_root()
        self.root.mkdir(parents=True, exist_ok=True)

    # ---------- 项目 ----------
    def list_projects(self) -> List[Project]:
        projects: List[Project] = []
        for entry in self.root.iterdir():
            if not entry.is_dir():
                continue
            meta = entry / "project.json"
            if not meta.exists():
                continue
            try:
                projects.append(self._load_project(entry, meta))
            except Exception:  # noqa: BLE001
                continue
        projects.sort(key=lambda p: p.updated_at, reverse=True)
        return projects

    def _load_project(self, folder: Path, meta: Path) -> Project:
        data = json.loads(meta.read_text(encoding="utf-8"))
        return Project(
            id=data["id"],
            name=data["name"],
            root=folder,
            pages=[Page.from_dict(item) for item in data.get("pages", [])],
            created_at=data.get("created_at", _now_iso()),
            updated_at=data.get("updated_at", _now_iso()),
        )

    def get(self, project_id: str) -> Optional[Project]:
        folder = self.root / project_id
        meta = folder / "project.json"
        if not meta.exists():
            return None
        return self._load_project(folder, meta)

    def create(self, name: str) -> Project:
        project = Project(id=_new_id(), name=name.strip() or "未命名项目", root=Path())
        project.root = self.root / project.id
        (project.root / "sources").mkdir(parents=True, exist_ok=True)
        (project.root / "pages").mkdir(parents=True, exist_ok=True)
        (project.root / ".thumbs").mkdir(parents=True, exist_ok=True)
        project.save()
        return project

    def rename(self, project: Project, name: str) -> None:
        project.name = name.strip() or project.name
        project.save()

    def delete(self, project: Project) -> None:
        shutil.rmtree(project.root, ignore_errors=True)

    # ---------- 页面 ----------
    def add_page(
        self,
        project: Project,
        source_path: str,
        mode: str = imaging.MODE_ENHANCE,
        options: Optional[dict] = None,
    ) -> Page:
        page_id = _new_id()
        extension = Path(source_path).suffix.lower() or ".png"

        sources_dir = project.root / "sources"
        pages_dir = project.root / "pages"
        thumbs_dir = project.root / ".thumbs"
        for folder in (sources_dir, pages_dir, thumbs_dir):
            folder.mkdir(parents=True, exist_ok=True)

        stored_source = sources_dir / f"{page_id}{extension}"
        shutil.copy2(source_path, stored_source)

        image = imaging.load_image(str(stored_source))
        quad = imaging.detect_document(image)
        adjustments = imaging.normalize_options(options)
        processed_path = pages_dir / f"{page_id}.png"
        width, height, dpi = imaging.process_to_png(
            str(stored_source), quad, mode, str(processed_path), adjustments
        )
        thumb_path = thumbs_dir / f"{page_id}.jpg"
        imaging.write_thumbnail(str(processed_path), str(thumb_path))

        page = Page(
            id=page_id,
            source=str(stored_source.relative_to(project.root)).replace("\\", "/"),
            processed=str(processed_path.relative_to(project.root)).replace("\\", "/"),
            thumb=str(thumb_path.relative_to(project.root)).replace("\\", "/"),
            original_name=os.path.basename(source_path),
            mode=mode,
            rotation=0,
            width=width,
            height=height,
            dpi=dpi,
            adjustments=adjustments,
            quad=[[x, y] for x, y in quad] if quad else None,
        )
        project.pages.append(page)
        project.save()
        return page

    def reprocess(
        self,
        project: Project,
        page: Page,
        mode: str,
        options: Optional[dict] = None,
    ) -> None:
        source = project.root / page.source
        processed = project.root / page.processed
        if options is not None:
            page.adjustments = imaging.normalize_options(options)
        else:
            page.adjustments = imaging.normalize_options(page.adjustments)
        width, height, dpi = imaging.process_to_png(
            str(source),
            page.quad,
            mode,
            str(processed),
            page.adjustments,
        )
        page.mode = mode
        page.width = width
        page.height = height
        page.dpi = dpi
        image = self.render_page(project, page)
        imaging.save_thumbnail_image(image, str(project.root / page.thumb))
        project.save()

    def rotate(self, project: Project, page: Page, delta: int) -> None:
        page.rotation = (page.rotation + delta) % 360
        image = self.render_page(project, page)
        imaging.save_thumbnail_image(image, str(project.root / page.thumb))
        project.save()

    def remove_page(self, project: Project, page: Page) -> None:
        self.remove_pages(project, [page])

    def remove_pages(self, project: Project, pages: Iterable[Page]) -> None:
        targets = list(pages)
        target_ids = {page.id for page in targets}
        project.pages = [item for item in project.pages if item.id not in target_ids]
        for page in targets:
            for relative in (page.source, page.processed, page.thumb):
                if not relative:
                    continue
                try:
                    (project.root / relative).unlink(missing_ok=True)
                except OSError:
                    pass
        project.save()

    def reorder(self, project: Project, page_ids: Sequence[str]) -> None:
        by_id = {page.id: page for page in project.pages}
        ordered = [by_id[pid] for pid in page_ids if pid in by_id]
        if len(ordered) == len(project.pages):
            project.pages = ordered
            project.save()

    # ---------- 导出 ----------
    def render_page(self, project: Project, page: Page) -> Image.Image:
        path = project.root / page.processed
        with Image.open(path) as img:
            img.load()
            img = img.convert("RGB")
        return imaging.rotate_image(img, page.rotation)

    def export_images(
        self,
        project: Project,
        pages: Iterable[Page],
        destination: Path,
        fmt: str = "PNG",
        progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Path]:
        destination.mkdir(parents=True, exist_ok=True)
        pages = list(pages)
        outputs: List[Path] = []
        extension = ".png" if fmt.upper() == "PNG" else ".tif"
        base_name = _safe_filename(project.name)

        for index, page in enumerate(pages, start=1):
            image = self.render_page(project, page)
            target = destination / f"{base_name}_{index:03d}{extension}"
            dpi = float(page.dpi or imaging.OUTPUT_DPI)
            if fmt.upper() == "PNG":
                if page.rotation % 360 == 0:
                    shutil.copyfile(project.root / page.processed, target)
                else:
                    image.save(
                        target,
                        "PNG",
                        compress_level=6,
                        dpi=(dpi, dpi),
                    )
            else:
                image.save(
                    target,
                    "TIFF",
                    compression="tiff_deflate",
                    dpi=(dpi, dpi),
                )
            outputs.append(target)
            if progress:
                progress(index, len(pages), target.name)
        return outputs

    def export_pdf(
        self,
        project: Project,
        pages: Iterable[Page],
        destination: Path,
        dpi: int = 300,
        progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> Path:
        images: List[Image.Image] = []
        pages = list(pages)
        for index, page in enumerate(pages, start=1):
            images.append(self.render_page(project, page))
            if progress:
                progress(index, len(pages), f"正在准备第 {index} 页")
        write_pdf(images, str(destination), dpi=dpi, title=project.name)
        return destination
