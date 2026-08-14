from __future__ import annotations


class ClientTheme:
    """Cinematic HUD theme focused on the assistant, not administration."""

    @staticmethod
    def stylesheet() -> str:
        return """
        QWidget#ClientRoot { color: #EAF8FF; font-family: "Segoe UI"; font-size: 14px; }
        QFrame#ClientTopBar { background: transparent; border: 0; }
        QFrame#ClientCard {
            background: transparent; border: 0;
        }
        QFrame#SetupCard {
            background-color: rgba(2, 10, 19, 174);
            border: 1px solid rgba(45, 157, 205, 76); border-radius: 9px;
        }
        QLabel#ClientBrand { color: #DDF8FF; font-size: 16px; font-weight: 800; letter-spacing: 5px; }
        QLabel#ClientSubtitle { color: #477C94; font-size: 8px; letter-spacing: 2px; }
        QLabel#ClientState { color: #BDEEFF; font-size: 13px; font-weight: 700; letter-spacing: 4px; }
        QLabel#ClientMessage { color: #A9C8D8; font-size: 15px; }
        QLabel#ClientResultText {
            color: #9EC7D8; font-size: 12px;
            background: transparent; border: 0;
            padding: 3px 10px;
        }
        QLabel#ClientHint { color: #6F9DB4; font-size: 11px; letter-spacing: 1px; }
        QLabel#ClientHealthy { color: #52F0BB; font-weight: 700; letter-spacing: 1px; }
        QLabel#ClientWarning { color: #FFC16C; font-weight: 700; }
        QLineEdit, QComboBox {
            background-color: rgba(1, 8, 15, 220); color: #EFFBFF;
            border: 1px solid rgba(65, 174, 216, 110); border-radius: 7px;
            padding: 12px 15px; font-size: 15px; selection-background-color: #147CA8;
        }
        QLineEdit:focus, QComboBox:focus { border: 1px solid #4CD8FF; }
        QPushButton { border-radius: 4px; padding: 10px 15px; font-weight: 700; letter-spacing: 1px; }
        QPushButton#ClientPrimary {
            background-color: #38C7F4; color: #011018; border: 1px solid #6EE1FF;
        }
        QPushButton#ClientPrimary:hover { background-color: #70DEFF; }
        QPushButton#ClientSecondary {
            background-color: rgba(5, 25, 41, 150); color: #CFEFFF;
            border: 1px solid rgba(55, 162, 207, 88);
        }
        QPushButton#ClientSecondary:hover {
            border-color: #50D9FF; background-color: rgba(8, 48, 73, 188);
        }
        QFrame#HudEdgeColumn { background: transparent; border: 0; }
        QFrame#HudStatusCard, QFrame#HudMenuPanel, QFrame#HudChatDock {
            background-color: rgba(2, 13, 23, 138); border: 1px solid rgba(55, 181, 224, 62); border-radius: 3px;
        }
        QFrame#HudChatDock { min-height: 260px; max-height: 390px; }
        QFrame#HudCommandBox { background-color: rgba(1, 8, 15, 210); border: 1px solid rgba(65, 190, 230, 68); border-radius: 3px; }
        QLabel#HudPanelTitle { color: #BCEEFF; font-size: 9px; font-weight: 800; letter-spacing: 3px; }
        QLabel#HudStatusKey { color: #507E92; font-size: 8px; letter-spacing: 2px; }
        QLabel#HudStatusValue { color: #4DD9C2; font-size: 9px; font-weight: 700; letter-spacing: 1px; }
        QLabel#HudMicroHint { color: #456F82; font-size: 8px; padding-top: 3px; }
        QLabel#HudChatPlaceholder { color: #567F92; font-size: 11px; padding: 10px 2px; }
        QPushButton#HudMenuAction {
            text-align: left; color: #BDEBFA; background: transparent; border: 0; border-bottom: 1px solid rgba(52, 170, 214, 52); padding: 9px 4px; font-size: 11px; letter-spacing: 2px;
        }
        QPushButton#HudMenuAction:hover { color: #FFFFFF; border-bottom-color: #51D9FF; }
        QPushButton#HudSendAction { color: #DFFAFF; background: #116A8A; border: 1px solid #42CFF5; padding: 8px 11px; font-size: 16px; }
        QPushButton#ClientConfirm { background-color: #126D50; color: #EDFFF8; border: 1px solid #35C78F; }
        QPushButton#ClientCancel { background-color: #672D3B; color: #FFECEF; border: 1px solid #B8576D; }
        QProgressBar#ClientProgress {
            background-color: #020A12; color: #BCEEFF; border: 1px solid #1D627F;
            border-radius: 3px; text-align: center; min-height: 10px; max-height: 10px;
        }
        QProgressBar#ClientProgress::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #177FAF, stop:1 #54E5FF);
        }
        QFrame#ConversationPanel {
            background-color: rgba(2, 12, 21, 205);
            border: 1px solid rgba(40, 143, 187, 80); border-radius: 8px;
        }
        QLabel#ConversationTitle { color: #62C3E8; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
        QPushButton#ConversationClear { color: #6395AA; background: transparent; border: 0; padding: 3px 7px; font-size: 10px; }
        QScrollArea#ConversationScroll, QWidget#ConversationBody { background: transparent; border: 0; }
        QLabel#ConversationUser {
            color: #EAF8FF; background-color: rgba(15, 67, 96, 185); border-radius: 6px; padding: 7px 10px;
        }
        QLabel#ConversationJarvis {
            color: #DDF7FF; background: transparent; border: 0; padding: 0;
        }
        QFrame#ConversationResultCard { background-color: rgba(4, 29, 47, 215); border: 1px solid rgba(49, 157, 201, 100); border-radius: 6px; }
        QLabel#ConversationResultTitle { color: #4ED7C1; font-size: 9px; font-weight: 800; letter-spacing: 2px; background: transparent; border: 0; }
        QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
        QScrollBar::handle:vertical { background: #216481; min-height: 24px; border-radius: 3px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QFrame#ClientToolsPanel {
            background-color: rgba(2, 13, 23, 232); border: 1px solid rgba(62, 187, 229, 88); border-radius: 7px;
        }
        QLabel#ClientToolsTitle { color: #DFF8FF; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
        QLabel#ClientToolsHint { color: #608CA0; font-size: 10px; }
        QLabel#ClientToolsGroup { color: #4ED7C1; font-size: 9px; font-weight: 700; letter-spacing: 2px; }
        QPushButton#ClientToolAction {
            text-align: left; color: #C6EAF7; background: rgba(6, 31, 47, 150);
            border: 1px solid rgba(51, 145, 182, 50); padding: 7px 8px; font-size: 9px; letter-spacing: 1px;
        }
        QPushButton#ClientToolAction:hover { color: #FFFFFF; border-color: #4DD8FF; background: rgba(8, 48, 70, 205); }
        QToolTip { color: #F4FCFF; background: #06121D; border: 1px solid #45CFF5; }
        """
