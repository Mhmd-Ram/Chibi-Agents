from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QColor, QFont, QGuiApplication, QMouseEvent, QPalette, QPixmap
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QLabel, QMenu, QWidget

from .sprite import Animation, SpriteSheet

LABEL_HEIGHT = 22
BUBBLE_GAP = 10  # vertical gap between bubble window and chibi top
CAPTION_GAP = 6  # vertical gap between chibi bottom and caption window


class BubbleWindow(QWidget):
    """Standalone always-on-top frameless window for the speech bubble.

    Lives as its own top-level so the styled pill background paints reliably
    on Windows — child widgets inside a WA_TranslucentBackground parent often
    fail to render their stylesheet backgrounds.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.SubWindow,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAutoFillBackground(False)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.transparent)
        pal.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.transparent)
        self.setPalette(pal)

        self._label = QLabel("", self)
        self._label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self._label.setFont(font)
        self._label.setStyleSheet(
            "QLabel {"
            "  color: #1c1c1c;"
            "  background-color: rgba(255, 250, 235, 245);"
            "  border: 1px solid rgba(0, 0, 0, 120);"
            "  border-radius: 12px;"
            "  padding: 6px 12px;"
            "}"
        )
        # NO QGraphicsDropShadowEffect — on Windows 11 the effect forces a paint
        # cache the size of the host window rect, and the unused transparent
        # area can leak through as a faint square outline.

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self._chrome_stripped = False
        self._last_anchor: tuple[int, int] | None = None

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._chrome_stripped:
            _strip_win32_chrome(int(self.winId()))
            self._chrome_stripped = True

    def say(self, text: str, anchor_top_center: tuple[int, int], duration_ms: int = 0) -> None:
        """Show a speech bubble. duration_ms<=0 means stay until replaced."""
        text = (text or "").strip()
        if not text:
            self.hide()
            self._last_anchor = None
            self._hide_timer.stop()
            return
        if len(text) > 30:
            text = text[:29].rstrip() + "…"
        self._label.setText(text)
        self._label.adjustSize()
        w = self._label.width()
        h = self._label.height()
        self.setFixedSize(w, h)
        self._label.move(0, 0)
        self._last_anchor = anchor_top_center
        self._reposition()
        self.raise_()
        self.show()
        if duration_ms > 0:
            self._hide_timer.start(duration_ms)
        else:
            self._hide_timer.stop()

    def follow(self, anchor_top_center: tuple[int, int]) -> None:
        """Reposition the bubble to track the chibi during drags."""
        if not self.isVisible():
            return
        self._last_anchor = anchor_top_center
        self._reposition()

    def _reposition(self) -> None:
        if not self._last_anchor:
            return
        ax, ay = self._last_anchor
        self.move(ax - self.width() // 2, ay - self.height() - BUBBLE_GAP)


def _strip_win32_chrome(hwnd: int) -> None:
    """Disable DWM-drawn shadow + rounded corners on a frameless top-level window.

    PyQt6's NoDropShadowWindowHint does not always suppress the Windows 11
    DWM-managed non-client area. We call DwmSetWindowAttribute directly to
    force-disable both shadow rendering and corner rounding.
    """
    if sys.platform != "win32":
        return
    try:
        dwmapi = ctypes.windll.dwmapi
        DWMWA_NCRENDERING_POLICY = 2
        DWMNCRP_DISABLED = 1
        val = ctypes.c_int(DWMNCRP_DISABLED)
        dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(int(hwnd)),
            DWMWA_NCRENDERING_POLICY,
            ctypes.byref(val),
            ctypes.sizeof(val),
        )
        # Windows 11: kill corner rounding.
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_DONOTROUND = 1
        corner = ctypes.c_int(DWMWCP_DONOTROUND)
        dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(int(hwnd)),
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corner),
            ctypes.sizeof(corner),
        )
    except Exception:
        # Older Windows or missing dwmapi — silently skip.
        pass


class CaptionWindow(QWidget):
    """Standalone always-on-top window for the caption pill.

    Sits just below the chibi and can be wider than the sprite — so long
    labels like "Presenting plan" or "Reading window.py" never get clipped.
    """

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.SubWindow,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAutoFillBackground(False)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.transparent)
        pal.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.transparent)
        self.setPalette(pal)

        self._label = QLabel("", self)
        self._label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        self._label.setFont(font)
        self._label.setStyleSheet(
            "QLabel {"
            "  color: white;"
            "  background-color: rgba(0, 0, 0, 210);"
            "  border-radius: 8px;"
            "  padding: 3px 10px;"
            "}"
        )
        # No drop-shadow — see BubbleWindow note (avoids visible host rect).

        self._chrome_stripped = False
        self._last_anchor: tuple[int, int] | None = None  # chibi bottom-center

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._chrome_stripped:
            _strip_win32_chrome(int(self.winId()))
            self._chrome_stripped = True

    def show_text(self, text: str, anchor_bottom_center: tuple[int, int]) -> None:
        text = (text or "").strip()
        if not text:
            self.hide()
            self._last_anchor = None
            return
        self._label.setText(text)
        self._label.adjustSize()
        w = self._label.width()
        h = self._label.height()
        self.setFixedSize(w, h)
        self._label.move(0, 0)
        self._last_anchor = anchor_bottom_center
        self._reposition()
        self.raise_()
        self.show()

    def follow(self, anchor_bottom_center: tuple[int, int]) -> None:
        if not self.isVisible():
            return
        self._last_anchor = anchor_bottom_center
        self._reposition()

    def _reposition(self) -> None:
        if not self._last_anchor:
            return
        ax, ay = self._last_anchor
        self.move(ax - self.width() // 2, ay + CAPTION_GAP)


class ChibiWindow(QWidget):
    close_requested = pyqtSignal()
    close_all_requested = pyqtSignal()
    scale_requested = pyqtSignal(float)
    position_committed = pyqtSignal()  # fired after a drag finishes

    def __init__(self, sheet: SpriteSheet, *, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.SubWindow,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAutoFillBackground(False)
        # NOTE: do NOT setStyleSheet on a top-level translucent widget on
        # Windows — it defeats WA_TranslucentBackground and re-paints a frame.
        # Use the palette instead.
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.transparent)
        pal.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.transparent)
        self.setPalette(pal)

        self._sheet = sheet
        self._scale = max(0.1, float(sheet.scale))
        sw, sh = self._scaled_frame_size()
        self.setFixedSize(sw, sh)

        # Bubble and caption both live as their own top-level windows so they
        # paint reliably (Windows quirk with translucent parents) and can be
        # wider than the chibi sprite.
        self._bubble = BubbleWindow(parent=None)
        self._caption = CaptionWindow()
        self._caption_text = ""

        self._label = QLabel(self)
        self._label.setGeometry(0, 0, sw, sh)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._label.setAutoFillBackground(False)
        self._label.setScaledContents(True)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._anim: Animation = sheet.animation("idle")
        self._frame_idx = 0
        self._drag_offset = None
        self._on_finished = None

        self._apply_frame()
        self._timer.start(sheet.frame_duration_ms)
        self._chrome_stripped = False

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._chrome_stripped:
            _strip_win32_chrome(int(self.winId()))
            self._chrome_stripped = True

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._bubble.close()
        self._caption.close()
        super().closeEvent(event)

    def _scaled_frame_size(self) -> tuple[int, int]:
        return (
            max(1, int(self._sheet.frame_width * self._scale)),
            max(1, int(self._sheet.frame_height * self._scale)),
        )

    def set_scale(self, scale: float) -> None:
        scale = max(0.1, min(4.0, float(scale)))
        if abs(scale - self._scale) < 1e-3:
            return
        old_geo = self.geometry()
        anchor_right = old_geo.right()
        anchor_bottom = old_geo.bottom()
        self._scale = scale
        sw, sh = self._scaled_frame_size()
        self.setFixedSize(sw, sh)
        self._label.setGeometry(0, 0, sw, sh)
        self.move(anchor_right - sw + 1, anchor_bottom - sh + 1)
        self._apply_frame()
        if self._caption_text:
            self.set_caption(self._caption_text)

    def scale(self) -> float:
        return self._scale

    @pyqtSlot(str)
    def play(self, anim_name: str, *, on_finished=None) -> None:
        anim = self._sheet.animation(anim_name)
        if anim is self._anim and anim.loop:
            return
        self._anim = anim
        self._frame_idx = 0
        self._on_finished = on_finished
        self._apply_frame()

    def current_animation(self) -> str:
        return self._anim.name

    @pyqtSlot(str)
    def set_caption(self, text: str) -> None:
        text = (text or "").strip()
        self._caption_text = text
        self._caption.show_text(text, self._caption_anchor())

    def _caption_anchor(self) -> tuple[int, int]:
        geo = self.geometry()
        return (geo.left() + self.width() // 2, geo.bottom())

    def _bubble_anchor(self) -> tuple[int, int]:
        geo = self.geometry()
        return (geo.left() + self.width() // 2, geo.top())

    def say(self, text: str, duration_ms: int = 0) -> None:
        """Show a speech bubble above the chibi. 0 = sticky until replaced."""
        self._bubble.say(text, self._bubble_anchor(), duration_ms)

    def anchor_bottom_right(self, margin: int = 32, x_offset: int = 0) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.right() - self.width() - margin - x_offset
        y = geo.bottom() - self.height() - margin
        self.move(x, y)

    def _advance(self) -> None:
        self._frame_idx += 1
        if self._frame_idx >= len(self._anim.frames):
            if self._anim.loop:
                self._frame_idx = 0
            else:
                self._frame_idx = len(self._anim.frames) - 1
                self._timer.stop()
                finished = self._on_finished
                self._on_finished = None
                if self._anim.next:
                    self.play(self._anim.next)
                    self._timer.start(self._sheet.frame_duration_ms)
                if finished:
                    finished(self)
                return
        self._apply_frame()

    def _apply_frame(self) -> None:
        idx = self._anim.frames[self._frame_idx]
        pix: QPixmap = self._sheet.pixmap(idx)
        self._label.setPixmap(pix)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self._bubble.follow(self._bubble_anchor())
            self._caption.follow(self._caption_anchor())
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        was_dragging = self._drag_offset is not None
        self._drag_offset = None
        if was_dragging:
            self.position_committed.emit()

    def _show_context_menu(self, global_pos) -> None:
        menu = QMenu(self)
        size_menu = menu.addMenu("Size")
        for label, factor in (("Tiny (25%)", 0.25), ("Small (50%)", 0.5), ("Medium (75%)", 0.75),
                              ("Original (100%)", 1.0), ("Large (150%)", 1.5), ("Huge (200%)", 2.0)):
            act = QAction(label, size_menu)
            act.setCheckable(True)
            if abs(factor - self._scale) < 1e-3:
                act.setChecked(True)
            act.triggered.connect(lambda _checked=False, f=factor: self.scale_requested.emit(f))
            size_menu.addAction(act)
        menu.addSeparator()
        close_one = QAction("Close this chibi", menu)
        close_one.triggered.connect(self.close_requested.emit)
        close_all = QAction("Close all chibis", menu)
        close_all.triggered.connect(self.close_all_requested.emit)
        menu.addAction(close_one)
        menu.addSeparator()
        menu.addAction(close_all)
        menu.exec(global_pos)
