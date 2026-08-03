from __future__ import annotations


class BusinessTheme:
    """Centralized visual system for the Business Edition desktop shell."""

    @staticmethod
    def _mix(color: str, target: str, ratio: float) -> str:
        source = color.lstrip("#")
        destination = target.lstrip("#")
        if len(source) != 6 or len(destination) != 6:
            return color
        values = []
        for index in (0, 2, 4):
            start = int(source[index:index + 2], 16)
            end = int(destination[index:index + 2], 16)
            values.append(round(start + (end - start) * ratio))
        return "#" + "".join(f"{value:02X}" for value in values)

    @classmethod
    def stylesheet(cls, accent: str = "#4DA3FF") -> str:
        accent = str(accent or "#4DA3FF").upper()
        accent_hover = cls._mix(accent, "#FFFFFF", 0.22)
        accent_pressed = cls._mix(accent, "#000000", 0.18)
        accent_soft = cls._mix(accent, "#0D1422", 0.77)
        return f"""
            QMainWindow, QWidget#BusinessRoot {{
                background-color: #070B14;
                color: #E8EEF8;
            }}
            QWidget {{
                font-family: "Segoe UI";
                font-size: 14px;
            }}
            QLabel {{ color: #E8EEF8; }}
            QFrame#Header, QFrame#Sidebar, QFrame#Workspace,
            QFrame#MetricCard, QFrame#SecurityCard, QFrame#SectionCard,
            QFrame#PageToolbar, QFrame#QuickPanel {{
                background-color: #0D1422;
                border: 1px solid #22314A;
                border-radius: 12px;
            }}
            QFrame#Header {{
                background-color: #0B1220;
                border-color: #2A3B59;
            }}
            QFrame#Sidebar {{
                background-color: #0A101C;
            }}
            QFrame#MetricCard {{
                background-color: #0C1422;
                border-color: #20324D;
            }}
            QFrame#MetricCard:hover, QFrame#SectionCard:hover {{
                border-color: {accent};
            }}
            QLabel#ProductTitle {{
                color: #F7FAFF;
                font-size: 31px;
                font-weight: 750;
                letter-spacing: 1px;
            }}
            QLabel#ProductSubtitle, QLabel#SectionTitle {{
                color: #8FA5C5;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QLabel#PageTitle {{
                color: #F4F8FF;
                font-size: 17px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            QLabel#MetricValue {{
                color: #F7FAFF;
                font-size: 18px;
                font-weight: 750;
            }}
            QLabel#MetricLabel {{
                color: #7F92B0;
                font-size: 10px;
                font-weight: 700;
            }}
            QLabel#MetricHint {{
                color: #55D98B;
                font-size: 9px;
                font-weight: 700;
            }}
            QLabel#Muted {{ color: #8EA0BB; }}
            QLabel#Healthy {{ color: #55D98B; }}
            QLabel#Danger {{ color: #FF6B7A; }}
            QLabel#InfoLabel {{
                color: #8EA0BB;
                font-size: 12px;
                font-weight: 600;
            }}
            QLabel#InfoValue {{
                color: #EFF5FF;
                font-size: 12px;
                font-weight: 650;
            }}
            QLabel#StatusPill {{
                border: 1px solid #344761;
                border-radius: 9px;
                padding: 5px 10px;
                font-size: 10px;
                font-weight: 800;
            }}
            QLabel#StatusPill[tone="healthy"] {{
                color: #7AE7A8;
                background-color: #10291E;
                border-color: #2C8C58;
            }}
            QLabel#StatusPill[tone="accent"] {{
                color: #EAF4FF;
                background-color: {accent_soft};
                border-color: {accent};
            }}
            QLabel#StatusPill[tone="danger"] {{
                color: #FFABB4;
                background-color: #31131A;
                border-color: #A93B4A;
            }}
            QLabel#StatusPill[tone="neutral"] {{
                color: #C6D2E5;
                background-color: #121C2C;
                border-color: #33445F;
            }}
            QPushButton {{
                border: none;
                border-radius: 10px;
                padding: 10px 16px;
                font-weight: 750;
            }}
            QPushButton#PrimaryButton {{
                background-color: {accent};
                color: #04101F;
            }}
            QPushButton#PrimaryButton:hover {{ background-color: {accent_hover}; }}
            QPushButton#PrimaryButton:pressed {{ background-color: {accent_pressed}; }}
            QPushButton#SecondaryButton {{
                background-color: #142035;
                color: #D9E6F8;
                border: 1px solid #31445F;
            }}
            QPushButton#SecondaryButton:hover {{
                border-color: {accent};
                background-color: #182840;
            }}
            QPushButton#NavigationButton {{
                background-color: transparent;
                color: #AFC0D8;
                border: 1px solid transparent;
                text-align: left;
                padding: 11px 12px;
                font-size: 12px;
                font-weight: 650;
            }}
            QPushButton#NavigationButton:hover {{
                color: #F4F8FF;
                background-color: #111B2C;
                border-color: #263A57;
            }}
            QPushButton#NavigationButton:checked {{
                color: #FFFFFF;
                background-color: {accent_soft};
                border-color: {accent};
            }}
            QPushButton#QuickCommandButton {{
                background-color: #101A2A;
                color: #DCE8F8;
                border: 1px solid #263A57;
                text-align: left;
                padding: 10px 12px;
                font-size: 11px;
                font-weight: 650;
            }}
            QPushButton#QuickCommandButton:hover {{
                background-color: #15243A;
                border-color: {accent};
            }}
            QTextEdit, QLineEdit, QComboBox {{
                background-color: #080E19;
                color: #F0F5FD;
                border: 1px solid #293B56;
                border-radius: 10px;
                padding: 9px 11px;
                selection-background-color: {accent};
            }}
            QTextEdit#OperationsLog {{
                padding: 14px;
                font-size: 14px;
            }}
            QTextEdit#IntegrityDetails {{
                background-color: #080D16;
                color: #C9D6E8;
                font-family: "Cascadia Mono";
                font-size: 11px;
            }}
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
                border-color: {accent};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 28px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #101827;
                color: #EFF5FF;
                border: 1px solid #32445F;
                selection-background-color: {accent_soft};
            }}
            QFrame#InfoRow {{
                background-color: #0A111E;
                border: 1px solid #1D2D45;
                border-radius: 8px;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: #0A101B;
                width: 10px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: #33445F;
                min-height: 30px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {accent}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QToolTip {{
                color: #EEF5FF;
                background-color: #101827;
                border: 1px solid {accent};
                border-radius: 6px;
                padding: 6px 8px;
            }}
        """
