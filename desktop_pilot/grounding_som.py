"""Per-Monitor DPI-Aware UIA Set-of-Mark & Vision Grid Grounding (Pain Point #3)."""

from __future__ import annotations

import sys
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class UIElementBox:
    mark_id: int
    name: str
    control_type: str
    left: int
    top: int
    right: int
    bottom: int
    dpi_scale: float = 1.0
    source: str = "uia"

    @property
    def center(self) -> Tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)

    @property
    def area(self) -> int:
        return max(0, self.right - self.left) * max(0, self.bottom - self.top)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["center"] = list(self.center)
        return data


def enable_per_monitor_dpi_awareness() -> str:
    if sys.platform != "win32":
        return "non-windows"
    try:
        import ctypes

        res = ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        if res:
            return "PER_MONITOR_AWARE_V2"
    except Exception:
        pass
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return "PROCESS_PER_MONITOR_DPI_AWARE"
    except Exception:
        return "DPI_UNAWARE_FALLBACK"


def normalize_dpi_point(
    x: int,
    y: int,
    source_scale: float = 1.0,
    target_scale: float = 1.0,
) -> Tuple[int, int]:
    if source_scale <= 0 or target_scale <= 0 or abs(source_scale - target_scale) < 1e-4:
        return (int(x), int(y))
    ratio = target_scale / source_scale
    return (int(round(x * ratio)), int(round(y * ratio)))


def deduplicate_boxes(
    boxes: List[UIElementBox],
    iou_threshold: float = 0.85,
    max_elements: int = 80,
) -> List[UIElementBox]:
    filtered: List[UIElementBox] = []
    for box in boxes:
        if box.area <= 4:
            continue
        is_dup = False
        for existing in filtered:
            inter_l = max(box.left, existing.left)
            inter_t = max(box.top, existing.top)
            inter_r = min(box.right, existing.right)
            inter_b = min(box.bottom, existing.bottom)
            inter_area = max(0, inter_r - inter_l) * max(0, inter_b - inter_t)
            union_area = box.area + existing.area - inter_area
            if union_area > 0 and (inter_area / union_area) >= iou_threshold:
                is_dup = True
                break
        if not is_dup:
            filtered.append(box)
        if len(filtered) >= max_elements:
            break

    for idx, item in enumerate(filtered, start=1):
        item.mark_id = idx
    return filtered


def build_grid_fallback_elements(
    screen_width: int = 1920,
    screen_height: int = 1080,
    rows: int = 6,
    cols: int = 8,
    dpi_scale: float = 1.0,
) -> List[UIElementBox]:
    grid_boxes: List[UIElementBox] = []
    cell_w = screen_width // cols
    cell_h = screen_height // rows
    mark = 1
    for r in range(rows):
        row_label = chr(ord("A") + r)
        for c in range(cols):
            cell_name = f"Grid-{row_label}{c + 1}"
            left = c * cell_w
            top = r * cell_h
            right = screen_width if c == cols - 1 else (c + 1) * cell_w
            bottom = screen_height if r == rows - 1 else (r + 1) * cell_h
            grid_boxes.append(
                UIElementBox(
                    mark_id=mark,
                    name=cell_name,
                    control_type="VisionGridCell",
                    left=left,
                    top=top,
                    right=right,
                    bottom=bottom,
                    dpi_scale=dpi_scale,
                    source="grid_fallback",
                )
            )
            mark += 1
    return grid_boxes


class GroundingEngine:
    def __init__(self, max_elements: int = 80, grid_fallback_threshold: int = 4) -> None:
        self.max_elements = max_elements
        self.grid_fallback_threshold = grid_fallback_threshold
        self.dpi_mode = enable_per_monitor_dpi_awareness()

    def ground_screen(
        self,
        raw_uia_boxes: Optional[List[UIElementBox]] = None,
        screen_size: Tuple[int, int] = (1920, 1080),
        dpi_scale: float = 1.0,
    ) -> Dict[str, Any]:
        uia_clean = deduplicate_boxes(
            raw_uia_boxes or [],
            max_elements=self.max_elements,
        )
        if len(uia_clean) >= self.grid_fallback_threshold:
            return {
                "mode": "uia_som",
                "dpi_mode": self.dpi_mode,
                "dpi_scale": dpi_scale,
                "elements": [e.to_dict() for e in uia_clean],
            }

        grid_boxes = build_grid_fallback_elements(
            screen_width=screen_size[0],
            screen_height=screen_size[1],
            dpi_scale=dpi_scale,
        )
        return {
            "mode": "vision_grid_fallback",
            "dpi_mode": self.dpi_mode,
            "dpi_scale": dpi_scale,
            "uia_detected_count": len(uia_clean),
            "elements": [e.to_dict() for e in grid_boxes],
        }
