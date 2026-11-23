"""
Combobox UI utilities.

Provides enhanced combobox views with:
- Greyed-out disabled items
- Smart cursor behaviour
- Better UX feedback for selectable vs non-selectable items
"""

from PySide6.QtWidgets import (
    QListView, QStyledItemDelegate, QWidget, QVBoxLayout,
    QSizePolicy, QRadioButton, QSpinBox, QDoubleSpinBox, QPushButton, QScrollArea, QFrame, QLabel, QHBoxLayout
)
from PySide6.QtCore import Qt, QRectF, QRect
from PySide6.QtGui import QColor, QPainterPath, QPen, QFontMetrics, QIcon, QCursor
from osdagbridge.desktop.ui.utils.custom_cursors import pointing_hand_cursor
from PySide6.QtWidgets import QLineEdit, QToolTip
from PySide6.QtCore import Signal, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator

# =================================================================================
#   ITEM DELEGATE FOR DISABLED ITEMS
# =================================================================================

class ComboBoxItemDelegate(QStyledItemDelegate):
    """
    Custom delegate to render disabled combobox items in grey.

    This improves UX by visually distinguishing disabled options
    from selectable ones in dropdown lists.
    """

    def paint(self, painter, option, index):
        model = index.model()
        item = model.item(index.row()) if hasattr(model, "item") else None

        if item and not item.isEnabled():
            # Draw background normally
            painter.fillRect(option.rect, option.palette.base())

            # Draw disabled text in grey
            painter.setPen(QColor(120, 120, 120))
            text = index.data()
            painter.drawText(
                option.rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                f"  {text}",
            )
        else:
            super().paint(painter, option, index)


# =================================================================================
#   SMART COMBOBOX VIEW
# =================================================================================

class SmartCursorComboBoxView(QListView):
    """
    Custom QListView used inside QComboBox.

    Features:
    - Shows pointing hand cursor for enabled items
    - Shows forbidden cursor for disabled items
    - Uses ComboBoxItemDelegate for grey rendering
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Apply custom delegate
        self.setItemDelegate(ComboBoxItemDelegate())

    def mouseMoveEvent(self, event):
        """
        Update cursor depending on whether hovered item is enabled.
        """
        index = self.indexAt(event.pos())

        if index.isValid():
            model = index.model()
            item = model.item(index.row()) if hasattr(model, "item") else None

            if item and not item.isEnabled():
                self.setCursor(Qt.ForbiddenCursor)
            else:
                self.setCursor(pointing_hand_cursor())
        else:
            self.setCursor(pointing_hand_cursor())

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """
        Reset cursor when leaving the dropdown.
        """
        self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)

from PySide6.QtWidgets import QCheckBox, QLabel, QHBoxLayout
from PySide6.QtWidgets import QCheckBox, QStyleOptionButton, QStyle, QApplication
from PySide6.QtGui import QPainter, QTextDocument
from PySide6.QtCore import Qt, QSize, QPoint

#----------------------------------------------------------------------------------
#   To create a checkbox with text that supports HTML formatting (e.g. subscripts)
#----------------------------------------------------------------------------------
class RichCheckBox(QCheckBox):
    def __init__(self, text="", parent=None):
        super().__init__("", parent)  # Keep native text empty
        self._rich_text = text

    def setText(self, text: str):
        self._rich_text = text
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return self._rich_text

    def _doc(self) -> QTextDocument:
        """Build a QTextDocument from the rich text."""
        doc = QTextDocument()
        doc.setDefaultFont(self.font())
        doc.setHtml(self._rich_text)
        return doc

    def sizeHint(self) -> QSize:
        doc = self._doc()
        # Ideal (unconstrained) size of the HTML content
        doc.setTextWidth(-1)
        text_size = doc.size()

        opt = QStyleOptionButton()
        self.initStyleOption(opt)

        # Width of the native checkbox indicator
        indicator_w = self.style().pixelMetric(
            QStyle.PM_IndicatorWidth, opt, self
        )
        spacing = self.style().pixelMetric(
            QStyle.PM_CheckBoxLabelSpacing, opt, self
        )

        w = indicator_w + spacing + int(text_size.width())
        h = max(
            self.style().pixelMetric(QStyle.PM_IndicatorHeight, opt, self),
            int(text_size.height()),
        )
        return QSize(w + 4, h + 4)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        opt = QStyleOptionButton()
        self.initStyleOption(opt)

        # --- 1. Draw ONLY the checkbox indicator (no text) ---
        opt.text = ""
        indicator_rect = self.style().subElementRect(
            QStyle.SE_CheckBoxIndicator, opt, self
        )
        opt.rect = indicator_rect
        self.style().drawControl(QStyle.CE_CheckBox, opt, painter, self)

        # --- 2. Draw rich text with QTextDocument ---
        indicator_w = self.style().pixelMetric(QStyle.PM_IndicatorWidth, opt, self)
        spacing = self.style().pixelMetric(QStyle.PM_CheckBoxLabelSpacing, opt, self)

        text_x = indicator_w + spacing
        text_y = (self.height() - int(self._doc().size().height())) // 2

        painter.save()
        painter.translate(QPoint(text_x, text_y))

        doc = self._doc()
        doc.setTextWidth(self.width() - text_x)
        doc.drawContents(painter)

        painter.restore()

#=================Percentage-bar widget (for OutputDock)==============================================
"""
Usage
    bar = PercentBarWidget(label="Strength Limit State (Flexure)", value=80)
    bar = PercentBarWidget(label="Strength Limit State (Shear)",   value=120)

    # Update at runtime:
    bar.set_value(95)

Visual behaviour
----------------
  value < 100  →  green fill, proportional width (scale 0–150), "XX%" text to the right
  value >= 100 →  red   fill, proportional width (scale 0–150), "XX%" text to the right
  value >= 150 →  red   fill, full width
"""

# -- Colours -------------------------------------------------------------------
COLOR_GREEN      = QColor("#90AF13")   # matches dock accent
COLOR_RED        = QColor("#CC2222")
COLOR_TRACK      = QColor("#D8D8D8")   # unfilled portion

BAR_HEIGHT       = 6           # px — height of the progress track
PCT_LABEL_WIDTH  = 46          # px — fixed width reserved for "120%" text
LABEL_STYLE      = "QLabel { font-size:13px; color:#222; background:transparent; }"
PCT_LABEL_STYLE  = "QLabel { font-size:12px; font-weight:bold; color:#444; background:transparent; }"


# -- Inner bar widget ----------------------------------------------------------

class _BarPainter(QWidget):
    """Custom-painted progress track."""

    def __init__(self, value: float, parent=None):
        super().__init__(parent)
        self._value = max(0.0, float(value))
        self.setFixedHeight(BAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value: float):
        self._value = max(0.0, float(value))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        radius = h / 2.0

        exceeded   = self._value >= 100.0
        fill_ratio = min(self._value / 150.0, 1.0)
        fill_w     = w * fill_ratio

        painter.setPen(Qt.NoPen)

        # -- Full rounded track pill -------------------------------------------
        track_path = QPainterPath()
        track_path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
        painter.setBrush(COLOR_TRACK)
        painter.drawPath(track_path)

        # -- Fill clipped to track shape ---------------------------------------
        if fill_w > 0:
            fill_color = COLOR_RED if exceeded else COLOR_GREEN
            fill_rect_path = QPainterPath()
            fill_rect_path.addRect(QRectF(0, 0, fill_w, h))
            clipped = track_path.intersected(fill_rect_path)
            painter.setBrush(fill_color)
            painter.drawPath(clipped)
        
        # Marker line at 100% threshold
        marker_x = w * (100.0 / 150.0)

        pen = QPen(QColor("#222222"))
        pen.setWidth(2)

        painter.setPen(pen)

        painter.drawLine(
            int(marker_x),
            -1,
            int(marker_x),
            h + 1
        )
        painter.end()


# -- Public widget -------------------------------------------------------------

#----Percentage Bar Widget with label-------------------------------------------
class PercentBarWidget(QWidget):
    """
    [Label (wraps, constrained to bar width)]
    [bar ---------------------------------- ] XX%
    """

    def __init__(self, label: str = "", value: float = 0.0, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        # -- Label — max-width kept in sync with bar via resizeEvent -----------
        lbl = QLabel(label)
        lbl.setStyleSheet(LABEL_STYLE)
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._lbl = lbl
        root.addWidget(lbl)
        lbl.setVisible(bool(label))
        # Don't call .setVisible on a widget that has no parent yet, call after adding the widget to the layout, otherwise it can show flickering pop ups

        # -- Bar row -----------------------------------------------------------
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(0, 0, 0, 0)
        bar_row.setSpacing(8)

        self._bar = _BarPainter(value)
        bar_row.addWidget(self._bar, 1)

        self._pct_label = QLabel(self._fmt(value))
        self._pct_label.setStyleSheet(PCT_LABEL_STYLE)
        self._pct_label.setFixedWidth(PCT_LABEL_WIDTH)
        self._pct_label.setAlignment(Qt.AlignCenter)
        bar_row.addWidget(self._pct_label)

        root.addLayout(bar_row)

    def resizeEvent(self, event):
        """Keep label max-width aligned to the bar column (excludes pct label)."""
        super().resizeEvent(event)
        bar_w = self.width() - PCT_LABEL_WIDTH - 8  # 8 = bar_row spacing
        if bar_w > 0:
            self._lbl.setMaximumWidth(bar_w)

    # -- Public API ------------------------------------------------------------

    def set_value(self, value: float):
        self._bar.set_value(value)
        self._pct_label.setText(self._fmt(value))

    @staticmethod
    def _fmt(value: float) -> str:
        return f"{int(round(value))}%"

# -- Custom Green Radio Button -----------------------------------------------
class CustomRadioButton(QRadioButton):
 
    INDICATOR_SIZE = 15
    DOT_SIZE       = 9
    SPACING        = 8
    PEN_WIDTH      = 2
    V_PADDING      = 6
 
    def __init__(self, text="", parent=None):
        super().__init__("", parent)   # always pass empty string to Qt
        self._rich_text = text         # store our own text (may contain HTML)
        self.setStyleSheet("""
            QRadioButton::indicator {
                width: 0px;
                height: 0px;
                image: none;
                border: none;
                background: none;
            }
        """)
 
    # ── Public text API (mirrors QAbstractButton) ────────────────────────────
 
    def setText(self, text: str):
        self._rich_text = text
        self.updateGeometry()
        self.update()
 
    def text(self) -> str:
        return self._rich_text
 
    # ── Rich-text document helper ────────────────────────────────────────────
 
    def _is_rich(self) -> bool:
        """True when the stored text contains HTML tags."""
        return "<" in self._rich_text and ">" in self._rich_text
 
    def _doc(self) -> QTextDocument:
        doc = QTextDocument()
        doc.setDefaultFont(self.font())
        doc.setHtml(self._rich_text)
        return doc
 
    # ── Paint ────────────────────────────────────────────────────────────────
 
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
 
        s      = self.INDICATOR_SIZE
        pw     = self.PEN_WIDTH
        offset = pw // 2 + 1
        cy     = self.height() // 2
 
        circle_rect = QRect(offset, cy - s // 2, s, s)
 
        # ── Circle ───────────────────────────────────────────────────────────
        if self.isChecked():
            painter.setBrush(QColor("#2e7d32"))
            painter.setPen(QPen(QColor("#2e7d32"), pw))
            painter.drawEllipse(circle_rect)
 
            d = self.DOT_SIZE
            dot_rect = QRect(
                circle_rect.x() + (s - d) // 2,
                circle_rect.y() + (s - d) // 2,
                d, d
            )
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(dot_rect)
 
        else:
            painter.setBrush(QColor("#ffffff"))
            border = QColor("#2e7d32") if self.underMouse() else QColor("#9e9e9e")
            painter.setPen(QPen(border, pw))
            painter.drawEllipse(circle_rect)
 
        # ── Text ─────────────────────────────────────────────────────────────
        text_x = offset + s + self.SPACING
 
        if self._is_rich():
            doc = self._doc()
            doc.setTextWidth(self.width() - text_x)
            text_h = int(doc.size().height())
            text_y = (self.height() - text_h) // 2
 
            painter.save()
            painter.translate(QPoint(text_x, text_y))
            if not self.isEnabled():
                painter.setOpacity(0.4)
            doc.drawContents(painter)
            painter.restore()
 
        else:
            text_rect = QRect(text_x, 0, self.width() - text_x, self.height())
            painter.setPen(QColor("#1a1a1a") if self.isEnabled() else QColor("#9e9e9e"))
            painter.setFont(self.font())
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self._rich_text)
 
        painter.end()
 
    # ── Size ─────────────────────────────────────────────────────────────────
 
    def sizeHint(self) -> QSize:
        s      = self.INDICATOR_SIZE
        pw     = self.PEN_WIDTH
        offset = pw // 2 + 1
 
        if self._is_rich():
            doc = self._doc()
            doc.setTextWidth(-1)
            text_size = doc.size()
            text_w = int(text_size.width())
            text_h = int(text_size.height())
        else:
            fm     = QFontMetrics(self.font())
            text_w = fm.horizontalAdvance(self._rich_text)
            text_h = fm.height()
 
        total_width  = offset + s + self.SPACING + text_w + offset
        total_height = max(s + pw * 2, text_h) + self.V_PADDING
        return QSize(total_width, total_height)
 
    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()
 
#---Custom toolbar widget with scroll area (for main screen)--------------------------------------
class ToolBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(30)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)

        # Your QSS
        self.scroll_area.setStyleSheet("""
            QScrollArea { background:transparent; padding:0px 0px;
                          border-top:1px solid #909090; border-bottom:1px solid #909090; }
            QScrollArea QScrollBar:vertical { border:none; background:#f0f0f0; width:8px; }
            QScrollArea QScrollBar::handle:vertical { background:#c0c0c0; border-radius:4px; min-height:20px; }
            QScrollArea QScrollBar::handle:vertical:hover { background:#a0a0a0; }
            QScrollArea QScrollBar::add-line:vertical,
            QScrollArea QScrollBar::sub-line:vertical { border:none; background:none; }
        """)

        container = QWidget()
        self.layout = QHBoxLayout(container)
        self.layout.setContentsMargins(5, 0, 5, 0)
        self.layout.setSpacing(6)

        icon_size = QSize(20, 20)

        # Button style with subtle hover
        button_qss = """
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(150, 150, 150, 60);
            }
            QPushButton:checked {
                background-color: #1565C0;
                border-radius: 4px;
            }
            QPushButton:checked:hover {
                background-color: #0D47A1;
            }
        """

        def create_button(icon_path, tooltip):
            btn = QPushButton()
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(icon_size)
            btn.setToolTip(tooltip)
            btn.setFixedSize(24, 24)
            btn.setCursor(pointing_hand_cursor())
            btn.setStyleSheet(button_qss)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            return btn

        def add_separator():
            sep = QFrame()
            sep.setFrameShape(QFrame.VLine)
            sep.setFrameShadow(QFrame.Plain)
            sep.setFixedHeight(24)
            sep.setStyleSheet("""
                QFrame {
                    color: #999999;
                    margin: 0px;
                    margin-left: 10px;
                    margin-right: 10px;
                }
            """)
            return sep

        # ---- Buttons ----
        # Zoom group
        self.btn_zoom_fit = create_button(":/vectors/tool_bar/zoom_fit_light.svg", "Zoom Fit")
        self.btn_zoom_window = create_button(":/vectors/tool_bar/zoom_window_light.svg", "Zoom Window")
        self.btn_zoom_in = create_button(":/vectors/tool_bar/zoom_in_light.svg", "Zoom In")
        self.btn_zoom_out = create_button(":/vectors/tool_bar/zoom_out_light.svg", "Zoom Out")
        self.layout.addWidget(self.btn_zoom_fit)
        self.layout.addWidget(self.btn_zoom_window)
        self.layout.addWidget(self.btn_zoom_in)
        self.layout.addWidget(self.btn_zoom_out)

        self.layout.addWidget(add_separator())  # after zoom

        # Navigation group
        self.btn_pan = create_button(":/vectors/tool_bar/pan_light.svg", "Pan")
        self.btn_rotate = create_button(":/vectors/tool_bar/rotate_light.svg", "Rotate")
        self.btn_pan.setCheckable(True)
        self.btn_rotate.setCheckable(True)
        self.layout.addWidget(self.btn_pan)
        self.layout.addWidget(self.btn_rotate)

        self.layout.addWidget(add_separator())  # after rotate

        # Node group
        self.btn_show_node = create_button(":/vectors/tool_bar/node_light.svg", "Node")
        self.btn_show_node.setCheckable(True)
        self.btn_show_node_number = create_button(":/vectors/tool_bar/Node_Number.svg", "Node Number")
        self.btn_show_node_number.setCheckable(True)
        self.btn_show_element_number = create_button(":/vectors/tool_bar/Element_number.svg", "Element Number")
        self.btn_show_element_number.setCheckable(True)
        self.layout.addWidget(self.btn_show_node)
        self.layout.addWidget(self.btn_show_node_number)
        self.layout.addWidget(self.btn_show_element_number)
        self.layout.addWidget(add_separator())  # after element number

        # Model display group
        self.layout.addWidget(create_button(":/vectors/tool_bar/grillage_view_light.svg", "Grillage View"))

        self.layout.addWidget(create_button(":/vectors/tool_bar/show_axis_light.svg", "Axis"))
        self.layout.addWidget(create_button(":/vectors/tool_bar/legend_icon.svg", "Legends"))
        self.layout.addWidget(create_button(":/vectors/tool_bar/show_grid_lines_light.svg", "Grid Lines"))
        self.layout.addWidget(create_button(":/vectors/tool_bar/show_support_light.svg", "Supports"))
        self.layout.addWidget(create_button(":/vectors/tool_bar/show_load_light.svg", "Loads"))
        self.btn_show_girder_label = create_button(":/vectors/tool_bar/Girder_label.svg", "Girder Labels")
        self.btn_show_girder_label.setCheckable(True)
        self.layout.addWidget(self.btn_show_girder_label)

        self.layout.addWidget(add_separator())  # after girder label

        # Scale
        self.scale_label = QLabel("Scale:")
        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(0.0, 10.0)
        self.spin_scale.setSingleStep(0.1)
        self.spin_scale.setDecimals(2)
        self.spin_scale.setValue(1.0)
        self.spin_scale.setFixedWidth(74)
        self.spin_scale.setKeyboardTracking(False)
        self.spin_scale.setToolTip("Display scale")
        self.spin_scale.setStyleSheet("""
            QDoubleSpinBox {
                border: 1px solid #aaa;
                border-radius: 4px;
                padding-right: 10px; /* space for BOTH buttons */
                background: #f8f8f8;
                margin: 0px;
            }

            QDoubleSpinBox:hover {
                border: 1px solid #888;
                background: #ffffff;
            }

            QDoubleSpinBox:focus {
                border: 1px solid #555;
                background: #ffffff;
            }

            /* UP BUTTON (right-top → shifted left) */
            QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 15px;
                right: 18px;   /* move LEFT */
                height: 20px;
                border: none;
                background: transparent;
            }

            /* DOWN BUTTON (right-most) */
            QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 15px;
                right: 3px;
                height: 20px;
                border: none;
                background: transparent;
            }

            QDoubleSpinBox::up-arrow {
                image: url(:/vectors/arrow_up_light.svg);
                width: 15px;
                height: 15px;
            }

            QDoubleSpinBox::down-arrow {
                image: url(:/vectors/arrow_down_light.svg);
                width: 15px;
                height: 15px;
            }

            QDoubleSpinBox::up-button:hover,
            QDoubleSpinBox::down-button:hover {
                background: rgba(150,150,150,60);
                border-radius: 3px;
            }
        """)

        self.layout.addWidget(self.scale_label)
        self.layout.addWidget(self.spin_scale)

        self.layout.addStretch()

        container.setLayout(self.layout)
        self.scroll_area.setWidget(container)

        main_layout.addWidget(self.scroll_area)
 

#---------Inline label editing for QPainter-drawn CAD canvases--------------------------------
class CADLabelEditor(QLineEdit):
    """Temporary line-edit that replaces a painted CAD label while it is being edited.

    Enter, or a click outside the box, commits the typed text; Esc cancels.
    Exactly one of ``committed`` / ``cancelled`` is emitted per edit session.
    """

    committed = Signal(str, str)   # (parameter key, typed text)
    cancelled = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._key = None
        self._active = False
        self.setAlignment(Qt.AlignCenter)
        # Only plain positive decimals can be typed (the field is numeric by design).
        self.setValidator(QRegularExpressionValidator(QRegularExpression(r"^\d{0,6}(\.\d{0,3})?$"), self))
        self.setStyleSheet(
            "QLineEdit { background: #ffffff; color: #000000; border: 1.5px solid #90AF13;"
            " border-radius: 3px; font: 9pt 'Arial'; padding: 0px 2px;"
            " selection-background-color: #90AF13; selection-color: #ffffff; }"
        )
        self.hide()

    def start(self, key: str, text: str, anchor: QRectF, tooltip: str = "") -> None:
        """Show the editor on top of ``anchor`` (the painted label's rectangle)."""
        self._key = key
        self._active = True
        self.setText(text)
        self.setToolTip(tooltip)

        width = max(80, int(anchor.width()) + 12)
        height = max(24, int(anchor.height()) + 6)
        bounds = self.parentWidget().rect()
        x = int(anchor.center().x() - width / 2)
        y = int(anchor.center().y() - height / 2)
        x = max(0, min(x, bounds.width() - width))
        y = max(0, min(y, bounds.height() - height))

        self.setGeometry(x, y, width, height)
        self.show()
        self.raise_()
        self.setFocus(Qt.OtherFocusReason)
        self.selectAll()

    def cancel(self) -> None:
        """Close the editor without applying anything (no-op when it is not open)."""
        self._finish(commit=False)

    def _finish(self, commit: bool) -> None:
        if not self._active:      # guards against Enter + focus-out firing twice
            return
        self._active = False
        key, text = self._key, self.text().strip()
        self.hide()
        if commit and text:
            self.committed.emit(key, text)
        else:
            self.cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._finish(commit=True)
        elif event.key() == Qt.Key_Escape:
            self._finish(commit=False)
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        # Switching windows or opening the context menu must not commit a half-typed value.
        if event.reason() in (Qt.ActiveWindowFocusReason, Qt.PopupFocusReason):
            super().focusOutEvent(event)
            return
        super().focusOutEvent(event)
        self._finish(commit=True)


class CADLabelEditMixin:
    """Double-click editing of painted dimension labels. List it *before* QWidget in the bases.

    The host widget provides:
        label_edited         = Signal(str, str)   # (KEY_*, typed text), emitted after a commit
        CAD_EDITABLE_LABELS  = {KEY_*: (params_name, divisor, "Label", "unit")}
        CAD_LOCKED_LABELS    = {KEY_*: "Label"}   # derived values - shown as read-only
    and paints each interesting label through ``draw_text_with_background(..., edit_key=KEY_*)``,
    which calls :meth:`_record_label_zone` so a double-click can be mapped back to its parameter.
    """

    CAD_EDITABLE_LABELS: dict = {}
    CAD_LOCKED_LABELS: dict = {}

    def _init_label_editing(self) -> None:
        self.label_editing_enabled = False   # switched on only for the main-page canvases
        self.label_edit_zones = []           # [(QRectF, KEY_*)] rebuilt on every paint
        self._label_hover_key = None
        self._label_editor = CADLabelEditor(self)
        self._label_editor.committed.connect(self.label_edited)

    # -- hit zones -------------------------------------------------------------------
    def _record_label_zone(self, rect: QRectF, key: str) -> None:
        self.label_edit_zones.append((QRectF(rect), key))

    def _label_zone_at(self, pos):
        for rect, key in reversed(self.label_edit_zones):
            if rect.adjusted(-3, -3, 3, 3).contains(pos):
                return rect, key
        return None

    def _locked_hint(self, key: str) -> str:
        return (f"{self.CAD_LOCKED_LABELS[key]} is a derived value and is read-only. "
                f"Edit the values it is derived from instead.")

    # -- hover feedback --------------------------------------------------------------
    def _update_label_hover(self, pos) -> None:
        if not getattr(self, "label_editing_enabled", False):
            return
        hit = self._label_zone_at(pos)
        key = hit[1] if hit else None
        if key == self._label_hover_key:
            return
        self._label_hover_key = key
        if key in self.CAD_EDITABLE_LABELS:
            self.setCursor(pointing_hand_cursor())
            label, unit = self.CAD_EDITABLE_LABELS[key][2:4]
            QToolTip.showText(self.mapToGlobal(pos.toPoint()), f"Double-click to edit {label} ({unit})", self)
        elif key in self.CAD_LOCKED_LABELS:
            self.setCursor(Qt.ForbiddenCursor)
            QToolTip.showText(self.mapToGlobal(pos.toPoint()), self._locked_hint(key), self)
        else:
            self.unsetCursor()
            QToolTip.hideText()

    # -- editing ---------------------------------------------------------------------
    def mouseDoubleClickEvent(self, event):
        if getattr(self, "label_editing_enabled", False) and event.button() == Qt.LeftButton:
            hit = self._label_zone_at(event.position())
            if hit is not None:
                rect, key = hit
                if key in self.CAD_EDITABLE_LABELS:
                    self._begin_label_edit(rect, key)
                    event.accept()
                    return
                if key in self.CAD_LOCKED_LABELS:
                    QToolTip.showText(event.globalPosition().toPoint(), self._locked_hint(key), self)
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)

    def _begin_label_edit(self, rect: QRectF, key: str) -> None:
        param, divisor, label, unit = self.CAD_EDITABLE_LABELS[key]
        value = self.params.get(param)
        text = "" if value is None else f"{float(value) / divisor:.3f}".rstrip("0").rstrip(".")
        self._label_editor.start(key, text, rect, f"{label} ({unit}) - Enter to apply, Esc to cancel")

    def _cancel_label_edit(self) -> None:
        self._label_editor.cancel()


#---------Standalone-Testing------------------------------------
import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

if __name__ == "__main__":
    app = QApplication(sys.argv)
 
    win = QWidget()
    win.setWindowTitle("PercentBar Test")
    win.setMinimumWidth(480)
    win.setStyleSheet("background-color: white;")
 
    layout = QVBoxLayout(win)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)
 
    layout.addWidget(PercentBarWidget("Strength Limit State (Flexure)", 80))
    layout.addWidget(PercentBarWidget(
        "Strength Limit State (Shear) — Very Long Label That Should Wrap Here", 120
    )),
    layout.addWidget(PercentBarWidget(
        "Strength Limit State (Shear) — Very Long Label That Should Wrap Here", 100
    )),
    layout.addWidget(PercentBarWidget("Strength Limit State (Flexure)", 99.9))
    layout.addWidget(PercentBarWidget("Strength Limit State (Flexure)", 99.4))

    rb1 = CustomRadioButton("Option A", parent=win)
    rb1.setChecked(True)
    rb1.adjustSize()
    rb1.move(20, 25)
    layout.addWidget(rb1)

    rb2 = CustomRadioButton("Option A very long label here", parent=win)
    rb2.adjustSize()
    rb2.move(20, 65)
    layout.addWidget(rb2)

    layout.addStretch()
 
    win.show()
    sys.exit(app.exec())

#--------------------------------------------------------------------