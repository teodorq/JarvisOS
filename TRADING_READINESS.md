# JARVIS OS — przygotowanie do tradingu

## Obecny stan: PAPER ONLY

JARVIS OS ma broker-neutralny, lokalny fundament do bezpiecznej nauki i testów
tradingowych. Nie ma dostępu do rachunku maklerskiego, danych logowania,
prawdziwych pieniędzy ani interfejsu wysyłającego rzeczywiste zlecenia.

Gotowe elementy:

- ścisłe modele kwotowań, świec, sygnałów i zleceń symulowanych;
- symulator zleceń z poślizgiem, prowizją i idempotencją;
- limity przed każdą symulowaną transakcją;
- lokalna, zapisywana atomowo księga rachunku demo;
- łańcuch audytowy SHA-256 wykrywający zmianę zapisanych zdarzeń;
- wyłącznik awaryjny;
- backtest realizujący sygnał dopiero na następnej świecy, co blokuje prosty
  błąd podglądania przyszłości;
- chronologiczny holdout oddzielający wcześniejsze dane treningowe od późniejszych,
  niewidzianych danych testowych;
- deterministyczny walk-forward z wieloma niepokrywającymi się okresami testowymi,
  izolowanym kapitałem testowym i raportem luki generalizacji;
- lokalny import danych OHLCV z CSV, walidacją kolejności i cyfrowym odciskiem
  zbioru;
- właścicielska komenda `Status paper tradingu`;
- skaner siedmiu głównych par Forex i deterministyczny koordynator decyzji;
- źródła tylko do odczytu: MT5 DEMO, Twelve Data, NBP i kalendarz Forex Factory;
- atomowy eksport zamkniętych świec M15 z MT5 DEMO do siedmiu lokalnych CSV,
  manifest SHA-256 oraz ponowna kontrola każdego odcisku przed badaniem;
- automatyczny obserwator rynku uruchamiany po zalogowaniu do Windows;
- właścicielskie pytania `Ile obserwacji Forex?`, `Status obserwatora Forex`
  oraz `Czy PAPER jest gotowy?` z prawdziwym licznikiem bramki.

Domyślne ograniczenia rachunku demo:

- kapitał początkowy: 100 000 PLN;
- pojedyncze zlecenie: maksymalnie 2% kapitału;
- pozycja jednego instrumentu: maksymalnie 5% kapitału;
- łączna ekspozycja: maksymalnie 20% kapitału;
- dzienna strata: maksymalnie 1% kapitału;
- maksymalnie 20 zleceń dziennie;
- maksymalny wiek kwotowania: 30 sekund;
- short selling, dźwignia i prawdziwy trading: wyłączone na stałe w tym etapie.

## Czego jeszcze celowo nie włączono

- ciągłego wykonywania decyzji PAPER — pozostaje wyłączone do spełnienia i
  ręcznego przeglądu bramki obserwacji;
- zewnętrznego brokera demonstracyjnego do składania zleceń; obecny wykonawca
  PAPER zapisuje wyłącznie lokalną symulację;
- prawdziwego rachunku, dźwigni ani jakiejkolwiek sieciowej ścieżki zleceń;
- podatków oraz raportowania właściwego dla rachunku rzeczywistego.

Wybranym pierwszym rynkiem jest Forex, walutą księgową PLN, a interwałem
decyzyjnym M15. MT5 działa wyłącznie jako główne źródło danych z rachunku DEMO;
nie jest powierzchnią wykonania zleceń.

## Bramy bezpieczeństwa przed dalszym etapem

Przed rozważeniem prawdziwych zleceń wszystkie poniższe warunki muszą być
spełnione i udokumentowane:

1. Kontrola jakości licencjonowanych danych historycznych i bieżących.
2. Uruchomienie gotowego backtestu z kosztami, poślizgiem i chronologicznym
   podziałem na rzeczywistym, sprawdzonym zbiorze historycznym.
3. Uruchomienie gotowego walk-forward na tym zbiorze oraz osobny test odporności
   na zmianę parametrów. Sam mechanizm nie wybiera najlepszego wariantu na
   podstawie przyszłych wyników i jawnie nie uznaje zewnętrznego generatora
   sygnałów za sprawdzony pod kątem podglądania przyszłości.
4. Minimum 30–90 dni ciągłego forward testu na rachunku paper.
5. Testy restartu, opóźnień, brakujących danych, duplikatów, częściowych
   realizacji i zerwanego połączenia.
6. Alarmy, dzienny limit straty, ręczny kill switch i procedura incydentowa.
7. Osobna analiza prawna, podatkowa oraz regulaminu wybranego brokera i rynku.
8. Osobna, jednoznaczna zgoda właściciela na projekt live — obecna zgoda na
   rozwój JARVIS OS nie odblokowuje prawdziwych pieniędzy.
9. Osobne sekrety, minimalne uprawnienia i początkowo bardzo niskie limity.

Wynik paper tradingu lub backtestu nie przewiduje wyniku na prawdziwym rynku.
Symulatory nie odwzorowują w pełni wpływu zlecenia na rynek, kolejki, opóźnień,
poślizgu i częściowych realizacji.

## Podstawa projektowa

- [EU 2017/589 — kontrole przedtransakcyjne, monitoring i funkcja awaryjnego anulowania](https://eur-lex.europa.eu/eli/reg_del/2017/589/oj/eng)
- [Alpaca — paper trading i jego ograniczenia](https://docs.alpaca.markets/us/docs/paper-trading)
- [Interactive Brokers — ograniczenia środowiska paper](https://www.interactivebrokers.com/docs/tws-api/doc/notes-limitations/limitations/paper-trading)

Ten dokument opisuje projekt techniczny, a nie poradę inwestycyjną.

## Wieloparowy Forex PAPER ONLY

Pierwszy koszyk Forex obejmuje siedem głównych par:

- EUR/USD, GBP/USD, USD/JPY i USD/CHF;
- AUD/USD, USD/CAD i NZD/USD.

Lokalny cykl autonomiczny wykonuje kolejno:

1. Sprawdzenie świeżości kwotowania, kolejności świec, luk, spreadu i
   dostępności tick volume.
2. Kontrolę sesji, kalendarza gospodarczego, drugiego źródła ceny oraz
   przelicznika do PLN.
3. Ocenę trendu wszystkich siedmiu par i ranking nowych sygnałów.
4. Pierwszeństwo zamknięcia istniejącej pozycji przed nowym wejściem.
5. Obliczenie wielkości pozycji z limitu ryzyka 0,25% kapitału demo.
6. Kontrolę maksymalnie dwóch pozycji, łącznego ryzyka oraz skumulowanej
   ekspozycji na każdą walutę.
7. Ponowną kontrolę ryzyka bezpośrednio w lokalnym wykonawcy PAPER.
8. Atomowy zapis cyklu, otwarcia lub zamknięcia i łańcucha audytowego.
9. Wyłącznie odczytowe wyliczenie wyniku średniego, profit factor, obsunięcia
   zamkniętej krzywej i serii strat z operacji zgodnych z audytem oraz saldem.

Powtórzenie identycznego identyfikatora cyklu nie tworzy drugiej pozycji.
Kill switch blokuje nowe wejścia, ale nie usuwa możliwości bezpiecznego
zamknięcia istniejącej pozycji. Sygnały LONG i SHORT są wyłącznie symulowane.
Próg 20 zamkniętych transakcji oznacza jedynie próbkę gotową do ręcznego
przeglądu. Nie uruchamia optymalizacji, zmiany strategii ani promocji LIVE.
Wyniki są również rozdzielane na siedem par. Dodatkowy raport kohortowy przypina
rzeczywiste otwarcia V1 do decyzji zamrożonego filtra V2: `zachowane` albo
`odfiltrowane`. Nie jest to symulacja alternatywnego portfela V2, ponieważ jego
przyszła ekspozycja mogłaby różnić się od faktycznego portfela V1.
Ukryty observer zapisuje również atomowy heartbeat do
`data/trading/forex_observer_status.json`. Status właściciela odróżnia dzięki temu
prawidłowe oczekiwanie przy zamkniętym rynku od nieaktualnego lub niedziałającego
procesu, bez uruchamiania MT5 i bez zużywania limitu danych poza oknem handlowym.

Warstwa danych tylko do odczytu jest przygotowana, lecz domyślnie wyłączona.
Obejmuje cztery rozdzielone role:

- lokalny MetaTrader 5 połączony wyłącznie z rachunkiem DEMO — główne
  kwotowania i zamknięte świece M15;
- Twelve Data — niezależny kurs średni do wykrywania rozbieżności;
- NBP Web API — publiczny dzienny kurs referencyjny USD/PLN;
- publiczny tygodniowy eksport Forex Factory — zaplanowane wydarzenia
  gospodarcze.

Adapter MT5 przed pierwszym odczytem sprawdza połączenie i pole
`ACCOUNT_TRADE_MODE_DEMO`. Rachunek realny oraz konkursowy są odrzucane, a kod
nie zawiera funkcji wysyłania, zmiany ani zamykania zleceń. Alternatywny adapter
OANDA REST-V20 `practice` pozostaje dostępny dla oddziałów obsługujących v20;
OANDA TMS w Polsce korzysta z MT5. Klucz Twelve Data jest pobierany z ignorowanego
`config/forex.env` i ukryty w reprezentacji obiektów oraz statusie.
Observer przed pełnym cyklem lokalnie potwierdza świeżość ticków i zamkniętych
świec wszystkich siedmiu par. Sonda nie odpytuje zewnętrznych dostawców i nie
ma powierzchni do składania zleceń.

Przed każdym wejściem bramka wymaga dwóch świeżych, zgodnych źródeł ceny.
Rozbieżność większa niż 0,2%, brak jednej z siedmiu par, stary kalendarz,
wydarzenie wysokiej ważności w oknie 30 minut, zamknięty rynek albo kurs NBP
starszy niż cztery dni blokują nowe pozycje. Dane NBP są referencją księgową dla
PAPER, a nie drugim źródłem ceny wykonania. Spot Forex nie ma jednego centralnego
wolumenu całego rynku, dlatego tick volume pozostaje tylko jednym z filtrów.
Wpis `Holiday` blokuje pary zawierające wskazaną walutę przez cały lokalny dzień
źródła. Blokada wejść usuwa wszystkie instrukcje otwarcia, ale może przepuścić
wyłącznie zweryfikowane zamknięcie istniejącej pozycji PAPER.

Narzędzie `tools/export_mt5_history.py` pobiera wyłącznie zamknięte świece M15,
zaczynając od pozycji 1 API MT5. Dane trafiają do ignorowanego katalogu
`data/trading/history/`; manifest nie zapisuje loginu ani danych konta. Opcja
`--verify-latest` ponownie przelicza odcisk każdego CSV i blokuje zmieniony zbiór.
Raport sprawdza również identyczną oś czasu siedmiu par, udział dodatniego tick
volume oraz oddziela regularne luki weekendowe od braków wewnątrz sesji.

## Bramka obserwacji przed PAPER

Obserwator wykonuje ten sam odczyt danych, skan i plan, który będzie używany w
PAPER, ale zatrzymuje się przed wykonaniem. Bramka wymaga jednocześnie:

- co najmniej 20 kwalifikowanych obserwacji przy otwartym rynku;
- kompletu zgodnych danych dla wszystkich siedmiu par;
- obserwacji z co najmniej 3 różnych dni rynkowych;
- prawidłowego łańcucha audytowego dziennika.

Spełnienie progów nie uruchamia PAPER automatycznie. Status zmienia się jedynie
na `GOTOWA DO PRZEGLĄDU`; właściciel musi najpierw przejrzeć dowody, a ciągły
wykonawca nadal pozostaje wyłączony. Pytanie `Ile obserwacji Forex?` pokazuje
bieżący licznik i brakującą część obu progów bez ujawniania sekretów.

Polecenie `Raport obserwacji Forex` wykonuje dokładniejszy audyt tylko do
odczytu: podsumowuje wszystkie wpisy, przyczyny blokad, proponowane lecz
niewykonane decyzje, pokrycie siedmiu par i niezmienność pozycji. Wykrycie
zmiany pozycji, flagi zlecenia, sieci zleceń, niepełnego pokrycia lub uszkodzenia
łańcucha blokuje gotowość do przeglądu. Sam raport nie może włączyć PAPER.

## Uruchomienie danych demonstracyjnych — kolejność

1. Utworzyć rachunek demonstracyjny OANDA TMS, zainstalować desktopowy MT5 i
   zalogować terminal wyłącznie do rachunku DEMO. Nie wpłacać pieniędzy.
2. Zainstalować oficjalny lokalny moduł z `requirements_trading_mt5.txt`.
3. Utworzyć bezpłatny klucz Twelve Data i sprawdzić limit bieżącego planu.
4. Potwierdzić dostępność publicznego tygodniowego eksportu Forex Factory.
5. Skopiować `config/forex.env.example` do lokalnego `config/forex.env`, wkleić
   klucze i ustawić `JARVIS_OS_FOREX_DATA_ENABLED=true`.
6. Wykonać serię cykli obserwacyjnych bez pozycji i sprawdzić świeżość,
   rozbieżności, weekend oraz blokady wydarzeń.
7. Dopiero po zielonej serii uruchomić autonomiczne pozycje PAPER. Rachunek
   prawdziwy, dźwignia i zlecenia live pozostają poza zakresem.

Dokumentacja źródeł: [MetaTrader 5 Python](https://www.mql5.com/en/docs/python_metatrader5),
[OANDA REST-V20](https://developer.oanda.com/rest-live-v20/development-guide/),
[Twelve Data](https://twelvedata.com/docs/currencies),
[NBP Web API](https://api.nbp.pl/) i
[Forex Factory Calendar](https://www.forexfactory.com/calendar).
