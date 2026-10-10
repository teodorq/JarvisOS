# Audyt przycisków i opcji JARVIS OS

Stan audytu: 2026-10-10  
Zakres: panel właściciela, tryb klienta, ustawienia, Forex PAPER i menu obok zegara.

## Wynik

- Sprawdzono 212 przycisków, 18 list wyboru, 3 karty Forex i 2 polecenia menu obok zegara.
- Każdy przycisk ma nazwę lub opis dostępności oraz przypiętą funkcję.
- Przyciski poleceń pokazują po najechaniu ich dokładny cel i udostępniają ten sam opis
  czytnikom ekranu, bez zmiany działania polecenia.
- Każda aktywna lista wyboru ma co najmniej dwie rzeczywiste możliwości.
- Usunięto 6 niewidocznych skrótów rozmowy, które dublowały menu `NARZĘDZIA`.
- Lista profili z jednym profilem jest teraz nieaktywna i wyjaśnia, jak utworzyć kolejny profil.
- `AKTYWUJ` jest dostępne tylko po wybraniu profilu innego niż aktualnie aktywny.
- Przycisk wysyłania oznaczony symbolem `›` ma teraz opis `Wyślij polecenie`.

Kontrole niszczące lub zmieniające stan nie były wykonywane na prawdziwych danych w ramach
audytu. Sprawdzono ich połączenie, routing, blokadę potwierdzeniem i testy usług. Dzięki temu
audyt nie wyłącza komputera, nie zmienia licencji, nie publikuje wydania i nie otwiera pozycji.

Legenda potrzebności:

- **podstawowa** — potrzebna w zwykłym użyciu;
- **administracyjna** — potrzebna tylko właścicielowi lub podczas utrzymania;
- **specjalistyczna** — potrzebna wyłącznie dla danego modułu;
- **zgodność** — niewidoczna w codziennej pracy, ale nadal używana przez testy gotowości.

## Główna nawigacja

| Przycisk | Cel | Potrzebność |
|---|---|---|
| TRYB KLIENTA | Otwiera prosty interfejs rozmowy po kontroli dostępu właściciela. | podstawowa |
| KONSOLA OPERACYJNA | Polecenia tekstowe i bezpieczne skróty. | podstawowa |
| ORGANIZACJA | Nazwa, wygląd, uruchamianie, wydajność i porządkowanie danych. | administracyjna |
| LICENCJA I ZAUFANIE | Pokazuje licencję, integralność i wymuszoną politykę bezpieczeństwa. | administracyjna |
| PROFILE, LICENCJE I ROLE | Zarządza profilami konfiguracji, licencją offline i rolami. | administracyjna |
| AUDYT, BACKUPY I AKTUALIZACJE | Kontroluje raporty, checkpointy, odzyskiwanie i paczki aktualizacji. | administracyjna |
| WDROŻENIE I RELEASE RC1 | Przygotowuje instalatory i kandydatów wydania. | specjalistyczna |
| PRODUKCJA I SPRZEDAŻ | Obsługuje wersje produkcyjne, dystrybucję i handoff. | specjalistyczna |
| ASYSTENT I CODZIENNA PRACA | Status rozmowy, pulpitu, pamięci, głosu i zadań dnia. | podstawowa |
| CENTRUM INTELIGENCJI | Narzędzia wizji, mózgu, pamięci i autonomii. | specjalistyczna |
| PRODUKTYWNOŚĆ I ORGANIZACJA | Poczta, kalendarz, dokumenty, przypomnienia i raport dnia. | podstawowa |
| STABILNOŚĆ I BUSINESS BETA | Testy, sondy, odzyskiwanie i audyty gotowości. | administracyjna |
| FOREX PAPER | Wyłącznie podgląd symulowanych pozycji i wyników. | specjalistyczna |
| ASYSTENT 1.2 BETA | Kontrola kontekstu i narzędzi nowszego asystenta. | specjalistyczna |
| ASYSTENT ONLINE I RC | Google Workspace i testy gotowości usług online. | specjalistyczna |

## Konsola operacyjna

| Przycisk | Cel | Potrzebność |
|---|---|---|
| BUSINESS | Wstawia polecenie sprawdzenia statusu i licencji. | podstawowa |
| AUTONOMIA | Wstawia polecenie statusu centrum autonomii. | administracyjna |
| INCYDENTY | Wstawia polecenie statusu monitorowania incydentów. | administracyjna |
| ODZYSKIWANIE | Wstawia polecenie statusu planów odzyskiwania. | administracyjna |
| WYKONAJ | Przekazuje wpisane polecenie do bezpiecznego routera. | podstawowa |

Skróty tylko przygotowują tekst. Polecenie wykonuje dopiero `WYKONAJ`, więc użytkownik może je
wcześniej przeczytać lub poprawić.

## Organizacja i ustawienia

### Przyciski

| Przycisk | Cel | Potrzebność |
|---|---|---|
| SPRAWDŹ STAN JARVIS | Liczy zajęte miejsce i pokazuje stan danych bez zmian. | administracyjna |
| UPORZĄDKUJ DANE | Usuwa stare cache kodu, testów, audio i zrzuty; zachowuje środowisko, pamięć, ustawienia i trading. | administracyjna |
| SPRAWDŹ | Odczytuje stan autostartu Windows. | administracyjna |
| WŁĄCZ / WYŁĄCZ | Włącza lub wyłącza autostart bez widocznego okna konsoli. | administracyjna |
| PRZYWRÓĆ DOMYŚLNE | Przywraca bezpieczne ustawienia początkowe. | administracyjna |
| ZAPISZ KONFIGURACJĘ | Waliduje i zapisuje ustawienia lokalnie. | podstawowa |

### Listy i pola

| Opcja | Dostępne wartości | Cel | Potrzebność |
|---|---|---|---|
| Środowisko | rozwój, testy, produkcja, demo | Oznacza przeznaczenie instalacji. | administracyjna |
| Kolor akcentu | błękit, cyjan, fiolet, zieleń, bursztyn | Zmienia wygląd. | opcjonalna |
| Skróty poleceń | włączone, wyłączone | Pokazuje lub ukrywa skróty konsoli. | opcjonalna |
| Ekran po uruchomieniu | ostatni, rozmowa, panel właściciela | Wybiera główny tryb startu. | podstawowa |
| Widoczność po uruchomieniu | okno, zasobnik | Pozwala działać bez otwartego okna. | podstawowa |
| Start panelu właściciela | konsola, asystent, produktywność, Forex, stabilność, ustawienia | Wybiera pierwszą zakładkę panelu. | opcjonalna |
| Tryb wydajności | automatyczny, oszczędny, pełna jakość | Dopasowuje obciążenie do urządzenia. | podstawowa |
| Dźwięki interfejsu | włączone, wyłączone | Steruje sygnałami interfejsu. | opcjonalna |
| Powiadomienia Windows | włączone, wyłączone | Steruje powiadomieniami systemowymi. | podstawowa |
| Nazwa produktu, organizacja, kontakt wsparcia | tekst | Uzupełnia nagłówki i raporty. | administracyjna |

## Licencja i zaufanie

| Przycisk | Cel | Potrzebność |
|---|---|---|
| ODŚWIEŻ | Ponownie odczytuje licencję, integralność plików i politykę bezpieczeństwa. | administracyjna |

## Profile, licencje i role

| Przycisk lub opcja | Cel | Potrzebność |
|---|---|---|
| ODŚWIEŻ | Ponownie odczytuje profile, licencję i rolę. | administracyjna |
| UTWÓRZ SNAPSHOT | Zachowuje bieżącą konfigurację jako nowy profil. | administracyjna |
| Lista profili | Wybiera zapisany profil; wyłączona, gdy istnieje tylko jeden. | administracyjna |
| AKTYWUJ | Wczytuje inny wybrany profil; wyłączone dla profilu aktywnego. | administracyjna |
| EKSPORTUJ | Eksportuje aktywny profil do JSON. | administracyjna |
| URUCHOM TRIAL 14 DNI | Tworzy lokalny okres próbny. | specjalistyczna |
| EKSPORTUJ WNIOSEK | Tworzy wniosek aktywacyjny powiązany z komputerem. | specjalistyczna |
| DEZAKTYWUJ PLIK LICENCJI | Usuwa lokalny plik aktywacyjny; wymaga świadomego użycia. | specjalistyczna |
| AKTYWUJ PAKIET OFFLINE | Waliduje i zapisuje wklejony pakiet aktywacyjny. | specjalistyczna |
| Rola | OWNER, ADMIN, OPERATOR, AUDITOR, VIEWER | Wybiera zakres lokalnych uprawnień. | administracyjna |
| ZASTOSUJ ROLĘ | Zapisuje wybraną rolę z audytem decyzji. | administracyjna |

## Audyt, backupy i aktualizacje

| Przycisk | Cel | Potrzebność |
|---|---|---|
| ODŚWIEŻ | Odświeża stan modułu. | administracyjna |
| EKSPORTUJ RAPORT AUDYTU | Tworzy raport kontroli. | administracyjna |
| POKAŻ STATUS | Pokazuje status centrum audytu. | administracyjna |
| UTWÓRZ CHECKPOINT | Przygotowuje punkt przywracania. | administracyjna |
| ZWERYFIKUJ | Sprawdza ostatni checkpoint. | administracyjna |
| PRZYGOTUJ RESTORE | Przygotowuje pakiet odzyskiwania. | administracyjna |
| SKANUJ | Szuka dostępnych paczek aktualizacji. | administracyjna |
| PRZYGOTUJ STAGING | Przygotowuje aktualizację w obszarze testowym. | administracyjna |
| EKSPORTUJ INSTALLER | Buduje instalator aktualizacji. | specjalistyczna |

## Wdrożenie i release

| Przycisk | Cel | Potrzebność |
|---|---|---|
| ODŚWIEŻ | Odświeża gotowość wydania. | specjalistyczna |
| INICJALIZUJ | Przygotowuje stan pierwszego uruchomienia. | specjalistyczna |
| EKSPORTUJ INSTALATOR / DEINSTALATOR | Buduje paczki instalacji lub usunięcia. | specjalistyczna |
| POKAŻ STATUS (instalacja) | Pokazuje stan instalatora. | specjalistyczna |
| EKSPORTUJ RC1 | Buduje kandydata wydania. | specjalistyczna |
| ZWERYFIKUJ RC1 | Sprawdza integralność kandydata. | specjalistyczna |
| POKAŻ STATUS (RC1) | Pokazuje stan kandydata wydania. | specjalistyczna |

## Produkcja i sprzedaż

| Przyciski | Cel | Potrzebność |
|---|---|---|
| ODŚWIEŻ | Odświeża stan całego procesu komercyjnego. | specjalistyczna |
| PRZYGOTUJ, PILOT, STABLE | Przygotowują wersję i wybierają kontrolowany kanał. | specjalistyczna |
| SKANUJ, EKSPORTUJ KATALOG | Kontrolują paczki i katalog aktualizacji. | specjalistyczna |
| INICJALIZUJ WYSTAWCĘ, WYSTAW DEMO, ZWERYFIKUJ | Obsługują lokalny urząd licencyjny i testową licencję. | specjalistyczna |
| BUDUJ MANIFEST, ZWERYFIKUJ | Budują i sprawdzają manifest dystrybucji. | specjalistyczna |
| EKSPORTUJ, ZWERYFIKUJ | Przygotowują i sprawdzają pakiet klienta. | specjalistyczna |
| EKSPORTUJ HANDOFF, POTWIERDŹ PRZEGLĄD | Przygotowują przekazanie sprzedażowe i zapisują przegląd. | specjalistyczna |
| EKSPORTUJ 1.0.0, ZWERYFIKUJ | Budują i sprawdzają wydanie produkcyjne. | specjalistyczna |

## Asystent i codzienna praca

| Przyciski | Cel | Potrzebność |
|---|---|---|
| ODŚWIEŻ | Odświeża status modułów asystenta. | podstawowa |
| POKAŻ STATUS, WYCZYŚĆ KONTEKST | Kontrolują bieżącą rozmowę. | podstawowa |
| STATUS PULPITU | Pokazuje gotowość sterowania pulpitem. | administracyjna |
| STATUS PAMIĘCI, DODAJ JARVIS OS | Sprawdzają pamięć i zapisują wpis demonstracyjny. | specjalistyczna |
| STATUS GŁOSU, WŁĄCZ CIĄGŁY, WYŁĄCZ CIĄGŁY | Kontrolują wejście głosowe. | podstawowa |
| STATUS PRACY, UTWÓRZ DEMO, URUCHOM, NASTĘPNY KROK | Obsługują plan codziennej pracy. | podstawowa |
| DODAJ PRZYPOMNIENIE | Dodaje przykładowe przypomnienie po zatwierdzeniu. | podstawowa |
| EKSPORTUJ RAPORT | Zapisuje raport codziennej pracy. | administracyjna |

## Centrum inteligencji

| Przyciski | Cel | Potrzebność |
|---|---|---|
| ODŚWIEŻ | Odświeża status modułów inteligencji. | specjalistyczna |
| POKAŻ STATUS, ZAPISZ DEMO | Sprawdzają Vision 3.0 i zapisują demonstrację. | specjalistyczna |
| STATUS BRAIN 2, PLAN DEMO | Sprawdzają mózg i przygotowują plan. | specjalistyczna |
| STATUS DESKTOP 2 | Pokazuje gotowość agenta pulpitu. | specjalistyczna |
| STATUS PAMIĘCI 2, ZAPISZ DEMO, ZNAJDŹ DEMO | Testują zapis i wyszukiwanie pamięci. | specjalistyczna |
| STATUS, UTWÓRZ DEMO, URUCHOM, NASTĘPNY ETAP | Obsługują kontrolowaną autonomię. | specjalistyczna |
| WSTRZYMAJ, WZNÓW, ANULUJ | Sterują cyklem autonomii. | administracyjna |

## Produktywność

| Przyciski | Cel | Potrzebność |
|---|---|---|
| ODŚWIEŻ | Odświeża status zestawu produktywności. | podstawowa |
| Poczta: STATUS, UTWÓRZ DEMO, OZNACZ GOTOWY, EKSPORTUJ EML | Kontrolują lokalne szkice wiadomości. | specjalistyczna |
| Kalendarz: STATUS, DODAJ DEMO, SPRAWDŹ KONFLIKTY | Kontrolują zdarzenia i kolizje terminów. | podstawowa |
| Dokumenty: STATUS, UTWÓRZ DEMO, SKANUJ, ZNAJDŹ JARVIS | Kontrolują lokalne dokumenty i wyszukiwanie. | podstawowa |
| Przypomnienia: STATUS, DODAJ DEMO, ZAKOŃCZ | Kontrolują listę przypomnień. | podstawowa |
| Raport: STATUS, GENERUJ RAPORT | Pokazują i tworzą raport dnia. | podstawowa |

## Stabilność

| Przyciski | Cel | Potrzebność |
|---|---|---|
| ODŚWIEŻ | Odświeża stan niezawodności. | administracyjna |
| STATUS / URUCHOM TESTY | Kontrolują zestaw scenariuszy stabilności. | administracyjna |
| STATUS / URUCHOM SONDĘ / UPORZĄDKUJ | Mierzą wydajność i porządkują wyniki. | administracyjna |
| STATUS / SYMULUJ ZAWIESZENIE / ODZYSKAJ | Testują kontrolowane odzyskiwanie. | administracyjna |
| STATUS / PRZYGOTUJ / WYKONAJ | Kontrolują bezpieczny restart. | administracyjna |
| STATUS / AUDYT BETA / POTWIERDŹ BETA | Sprawdzają gotowość wersji beta. | zgodność |

## Forex PAPER

| Kontrolka | Cel | Potrzebność |
|---|---|---|
| ODŚWIEŻ | Odczytuje bieżący stan symulacji; nie wysyła zleceń. | specjalistyczna |
| OTWARTE POZYCJE | Pokazuje kierunek, cenę, SL, TP i ryzyko pozycji PAPER. | specjalistyczna |
| HISTORIA ZDARZEŃ | Pokazuje trwałe powiadomienia obserwatora. | specjalistyczna |
| WYNIKI PAR | Porównuje próbki siedmiu par bez automatycznego wyboru. | specjalistyczna |

## Asystent 1.2 i usługi online

### Asystent 1.2

`ODŚWIEŻ`; rozmowa: `STATUS`, `MÓJ DZIEŃ`, `TEST DOPYTANIA`; kontekst:
`STATUS`, `WYCZYŚĆ`; narzędzia: `STATUS POCZTY`, `KALENDARZ`, `DOKUMENT`,
`PRZYPOMNIENIA`; postęp: `STATUS POSTĘPU`, `RAPORT DNIA`; gotowość:
`STATUS`, `AUDYT 1.2`, `POTWIERDŹ 1.2`.

Wszystkie są potrzebne tylko do rozwoju i kontroli nowszego asystenta; codzienna rozmowa nie
wymaga otwierania tej strony.

### Online i RC

`ODŚWIEŻ`; połączenie: `STATUS`, `POŁĄCZ GOOGLE`, `ROZŁĄCZ`; Gmail: `NAJNOWSZE`,
`PRIORYTETOWE`, `SZKIC DEMO`; kalendarz: `DZISIAJ`, `KONFLIKTY`; Dysk Google:
`SZUKAJ JARVIS`, `ZAPISZ RAPORT`; dzień: `POKAŻ MÓJ DZIEŃ`; gotowość:
`AUDYT RC`, `POTWIERDŹ RC`; wersja 1.3: `STATUS 1.3`, `TEST SESJI`, `GMAIL`,
`TYDZIEŃ`, `TERMINY`, `AUDYT B135`, `POTWIERDŹ`.

Te funkcje są potrzebne po połączeniu Google Workspace. Przed połączeniem mają wartość
diagnostyczną i nie powinny udawać, że dane online są dostępne.

## Tryb klienta

### Widoczne sterowanie

| Przycisk | Cel | Potrzebność |
|---|---|---|
| NARZĘDZIA | Otwiera przeszukiwalny zestaw codziennych funkcji. | podstawowa |
| USTAWIENIA | Otwiera prostą konfigurację klienta, nie panel właściciela. | podstawowa |
| WYJDŹ | Zamyka JARVIS po rozpoznaniu intencji zamknięcia. | podstawowa |
| MÓW | Rozpoczyna obsługę głosową albo pokazuje bezpieczną wskazówkę. | podstawowa |
| › | Wysyła wpisane polecenie; ma opis dostępności. | podstawowa |
| WYCZYŚĆ | Czyści lokalną historię widoczną w rozmowie. | podstawowa |
| TAK, WYKONAJ / NIE, ANULUJ | Obsługują wyłącznie aktywne potwierdzenie. | podstawowa |

### Narzędzia codzienne

| Grupa | Przyciski | Cel |
|---|---|---|
| JARVIS | STATUS JARVIS, STAN KOMPUTERA, STATUS GŁOSU, POGODA | Stan asystenta i otoczenia. |
| MÓJ DZIEŃ | PODSUMOWANIE DNIA, NAJWAŻNIEJSZE TERAZ, PLAN NA JUTRO, OSTATNIE DZIAŁANIA, RACHUNKI, CO POTRAFIĘ | Planowanie i podsumowanie. |
| POCZTA | NAJNOWSZE, WAŻNE, NIEPRZECZYTANE | Odczyt Gmail po połączeniu konta. |
| KALENDARZ | DZISIAJ, TEN TYDZIEŃ, NOWE WYDARZENIE | Odczyt oraz prowadzone tworzenie wydarzenia. |
| PLIKI I PAMIĘĆ | OSTATNI DOKUMENT, SZUKAJ DOKUMENTU, NOWE PRZYPOMNIENIE, INTEGRACJE | Pliki, pamięć i przypomnienia. |
| Kontekst | 3 zmienne propozycje oraz ZAMKNIJ | Podpowiedzi zależne od pory dnia i zamknięcie menu. |

Wszystkie bezpośrednie akcje klienta przechodzą test polityki uprawnień i istniejącego routingu.
Reklamy, trading i podsumowania właściciela pozostają w trybie klienta zablokowane.

### Ustawienia klienta

| Kontrolka | Cel | Potrzebność |
|---|---|---|
| ZAPISZ I URUCHOM JARVISA / ZAPISZ USTAWIENIA | Zapisuje imię, głos, sposób rozmowy i ustawienia działania. | podstawowa |
| WRÓĆ | Wraca do rozmowy bez wejścia w panel właściciela. | podstawowa |
| Głos | włączony lub wyłączony | podstawowa |
| Rozmowa | głos i tekst albo tylko tekst | podstawowa |
| Wydajność | automatyczna, oszczędna, pełna jakość | podstawowa |
| Dźwięki, powiadomienia | włączone lub wyłączone | opcjonalna |
| Start, widoczność | ostatni/rozmowa/panel oraz okno/zasobnik | podstawowa |
| SPRAWDŹ STAN / UPORZĄDKUJ DANE | Kontrola miejsca i bezpieczne sprzątanie. | administracyjna |
| WŁĄCZ / WYŁĄCZ | Steruje autostartem. | administracyjna |

### Niewidoczne kontrolki zgodności

- Ukryty dostęp właściciela — zastąpiony skrótem `Ctrl+Shift+F12`, ale zachowany jako punkt
  zgodności audytu dostępu.
- Trzy ukryte przyciski gotowości 1.1, 1.2 Beta i Stable RC — nie zaśmiecają interfejsu,
  ale nadal są używane przez moduły potwierdzania historycznych bramek wydania.

## Menu obok zegara

| Opcja | Cel | Potrzebność |
|---|---|---|
| Pokaż JARVIS OS | Przywraca właściwe okno klienta lub właściciela. | podstawowa |
| Zamknij JARVIS OS | Kończy aplikację świadomie; autostart nie uruchamia jej natychmiast ponownie. | podstawowa |

## Automatyczna ochrona przed regresją

Test `tests/test_ui_control_integrity.py` sprawdza przy każdej zmianie, że:

1. każdy przycisk ma zrozumiałą tożsamość;
2. każdy przycisk ma odbiorcę kliknięcia;
3. aktywna lista nie udaje wyboru, gdy ma tylko jedną wartość;
4. karty mają rzeczywiste alternatywy;
5. wybór profilu nie pozwala ponownie aktywować już aktywnego profilu;
6. każdy przycisk polecenia pokazuje pełny cel w podpowiedzi i opisie dostępności;
7. stary ukryty rząd skrótów rozmowy nie wróci przypadkiem.

Wynik pełnego uruchomienia po audycie: **3045 testów i 372 warianty
zaliczone, 2 testy warunkowo pominięte, 0 błędów**. Pozostało 9 ostrzeżeń
zależności, głównie o zgodności `speech_recognition` z Pythonem 3.13.
