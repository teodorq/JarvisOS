from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.core.user_text import naturalize_user_text


class ElidedLabel(QLabel):
    """Single-line label that keeps full text in a tooltip."""

    def __init__(
        self,
        text: str = "",
        mode: Qt.TextElideMode = Qt.ElideMiddle,
    ) -> None:
        super().__init__()
        self._full_text = ""
        self._elide_mode = mode
        self.setText(text)

    @property
    def full_text(self) -> str:
        return self._full_text

    def setText(self, text: str) -> None:  # noqa: N802 - Qt API compatibility
        self._full_text = naturalize_user_text(text)
        self.setToolTip(self._full_text)
        self._refresh_elision()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API compatibility
        super().resizeEvent(event)
        self._refresh_elision()

    def _refresh_elision(self) -> None:
        width = max(20, self.contentsRect().width())
        shown = self.fontMetrics().elidedText(
            self._full_text,
            self._elide_mode,
            width,
        )
        QLabel.setText(self, shown)
        self.setToolTip(self._full_text if shown != self._full_text else "")


class MetricCard(QFrame):
    """Compact live metric tile used by the Business dashboard."""

    def __init__(self, label: str, value: str = "—", hint: str = "LIVE") -> None:
        super().__init__()
        self.setObjectName("MetricCard")
        self.setMinimumWidth(150)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(3)

        top = QHBoxLayout()
        caption = QLabel(label.upper())
        caption.setObjectName("MetricLabel")
        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("MetricHint")
        top.addWidget(caption)
        top.addStretch(1)
        top.addWidget(self.hint_label)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addLayout(top)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(str(value))

    def set_hint(self, value: str) -> None:
        self.hint_label.setText(str(value).upper())


class StatusPill(ElidedLabel):
    """Small status badge with a semantic tone and safe text elision."""

    def __init__(self, text: str, tone: str = "neutral") -> None:
        super().__init__(text, Qt.ElideRight)
        self.setObjectName("StatusPill")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumWidth(76)
        self.setMaximumWidth(210)
        self.set_tone(tone)

    def set_status(self, text: str, tone: str = "neutral") -> None:
        self.setText(text)
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)


class NavigationButton(QPushButton):
    """Checkable sidebar navigation button."""

    def __init__(self, text: str, page_name: str) -> None:
        super().__init__(text)
        self.page_name = page_name
        self.setObjectName("NavigationButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)


class SectionCard(QFrame):
    """Reusable bordered panel with a title and content area."""

    def __init__(self, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.setObjectName("SectionCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(10)

        heading = QLabel(naturalize_user_text(title).upper())
        heading.setObjectName("SectionTitle")
        outer.addWidget(heading)
        if subtitle:
            description = QLabel(naturalize_user_text(subtitle))
            description.setObjectName("Muted")
            description.setWordWrap(True)
            outer.addWidget(description)

        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(8)
        outer.addLayout(self.content_layout)


class InfoRow(QFrame):
    """Label/value row with elision for long fingerprints and identifiers."""

    def __init__(self, label: str, value: str = "—") -> None:
        super().__init__()
        self.setObjectName("InfoRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(12)
        caption = QLabel(naturalize_user_text(label))
        caption.setObjectName("InfoLabel")
        self.value_label = ElidedLabel(value)
        self.value_label.setObjectName("InfoValue")
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setMinimumWidth(150)
        layout.addWidget(caption)
        layout.addStretch(1)
        layout.addWidget(self.value_label, 1)

    def set_value(self, value: object) -> None:
        self.value_label.setText(str(value))


class QuickCommandButton(QPushButton):
    """Command shortcut that only prepares text; it never bypasses safety."""

    def __init__(self, title: str, command: str, subtitle: str = "") -> None:
        visible_title = naturalize_user_text(title)
        visible_subtitle = naturalize_user_text(subtitle)
        text = (visible_title if not visible_subtitle else
                f"{visible_title}\n{visible_subtitle}")
        super().__init__(text)
        self.command = command
        self.setObjectName("QuickCommandButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(58)
