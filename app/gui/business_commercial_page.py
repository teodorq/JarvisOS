from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame,QHBoxLayout,QLabel,QPushButton,QScrollArea,QVBoxLayout,QWidget
from app.core.user_text import naturalize_user_text
from app.gui.business_display import display_status
from app.gui.business_widgets import InfoRow,SectionCard,StatusPill
class BusinessCommercialPage(QWidget):
    command_requested=Signal(str)
    def __init__(self,service):
        super().__init__(); self.service=service; root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(10); root.addWidget(self._toolbar()); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); box=QWidget(); content=QVBoxLayout(box); content.setContentsMargins(0,0,4,0); content.setSpacing(10)
        self.rows={}
        specs=(("B89 — Wersja i kanały produkcyjne",("version","channel","prepared"),(("PRZYGOTUJ","Przygotuj wersję produkcyjną"),("PILOT","Promuj wersję do kanału pilot"),("STABLE","Promuj wersję do kanału stable"))), ("B90 — Aktualizacje klientów",("package_count","valid_package_count","catalog_path"),(("SKANUJ","Skanuj kanały aktualizacji klientów"),("EKSPORTUJ KATALOG","Eksportuj katalog aktualizacji klientów"))), ("B91 — Licencje komercyjne",("issuer_ready","issued_count","public_key_path"),(("INICJALIZUJ WYSTAWCĘ","Inicjalizuj wystawcę licencji komercyjnych"),("WYSTAW DEMO","Wystaw demonstracyjną licencję komercyjną"),("ZWERYFIKUJ","Zweryfikuj licencję komercyjną"))), ("B92 — Ochrona dystrybucji",("verified","file_count","manifest_path"),(("BUDUJ MANIFEST","Zbuduj manifest dystrybucji"),("ZWERYFIKUJ","Zweryfikuj manifest dystrybucji"))), ("B93 — Paczka klienta",("package_count","latest_package","latest_sha256"),(("EKSPORTUJ","Eksportuj paczkę klienta"),("ZWERYFIKUJ","Zweryfikuj paczkę klienta"))), ("B94 — Gotowość sprzedażowa",("sales_ready","latest_bundle","owner_review"),(("EKSPORTUJ HANDOFF","Eksportuj pakiet sprzedażowy"),("POTWIERDŹ PRZEGLĄD","Potwierdź przegląd dokumentów sprzedażowych"))), ("B95 — Wydanie produkcyjne",("version","release_ready","latest_release"),(("EKSPORTUJ 1.0.0","Eksportuj wydanie produkcyjne"),("ZWERYFIKUJ","Zweryfikuj wydanie produkcyjne"))))
        for title,keys,buttons in specs: content.addWidget(self._section(title,keys,buttons))
        content.addStretch(1); scroll.setWidget(box); root.addWidget(scroll,1); self.feedback=QLabel('Gotowy.'); self.feedback.setObjectName('Muted'); root.addWidget(self.feedback); self.refresh()
    def _toolbar(self):
        bar=QFrame(); bar.setObjectName('PageToolbar'); lay=QHBoxLayout(bar); lay.setContentsMargins(14,10,14,10); head=QVBoxLayout(); title=QLabel('PRODUKCJA I SPRZEDAŻ B89–B95'); title.setObjectName('PageTitle'); sub=QLabel('Wersje, aktualizacje klientów, licencje, dystrybucja i techniczne wydanie 1.0.0.'); sub.setObjectName('Muted'); head.addWidget(title); head.addWidget(sub); lay.addLayout(head); lay.addStretch(1); self.overall=StatusPill('SPRAWDZANIE','neutral'); refresh=QPushButton('ODŚWIEŻ'); refresh.setObjectName('SecondaryButton'); refresh.clicked.connect(self.refresh); lay.addWidget(self.overall); lay.addWidget(refresh); return bar
    def _section(self,title,keys,buttons):
        card=SectionCard(title); rows={key:InfoRow(key.replace('_',' ').title()) for key in keys}; self.rows[title[:3]]=rows
        for row in rows.values(): card.content_layout.addWidget(row)
        line=QHBoxLayout()
        for label,command in buttons:
            button=QPushButton(label); button.setObjectName('PrimaryButton' if line.count()==0 else 'SecondaryButton'); button.clicked.connect(lambda _=False,c=command:self.command_requested.emit(c)); line.addWidget(button)
        line.addStretch(1); card.content_layout.addLayout(line); return card
    def refresh(self):
        response=self.service.commercial_platform_status(); stages=dict(response.get('stages',{}) or {})
        for stage,rows in self.rows.items():
            data=dict(stages.get(stage,{}) or {})
            for key,row in rows.items(): row.set_value(display_status(data.get(key)) if isinstance(data.get(key),bool) else data.get(key,'Brak'))
        ready=all(dict(v.get('runtime',{}) or {}).get('phase')=='READY' for v in stages.values()); self.overall.set_status('PLATFORMA GOTOWA' if ready else 'KONFIGURACJA','healthy' if ready else 'accent'); self.feedback.setText(naturalize_user_text(response.get('reason','Gotowy.')))
