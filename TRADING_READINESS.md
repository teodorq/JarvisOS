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
- lokalny import danych OHLCV z CSV, walidacją kolejności i cyfrowym odciskiem
  zbioru;
- właścicielska komenda `Status paper tradingu`.

Domyślne ograniczenia rachunku demo:

- kapitał początkowy: 100 000 PLN;
- pojedyncze zlecenie: maksymalnie 2% kapitału;
- pozycja jednego instrumentu: maksymalnie 5% kapitału;
- łączna ekspozycja: maksymalnie 20% kapitału;
- dzienna strata: maksymalnie 1% kapitału;
- maksymalnie 20 zleceń dziennie;
- maksymalny wiek kwotowania: 30 sekund;
- short selling, dźwignia i prawdziwy trading: wyłączone na stałe w tym etapie.

## Czego jeszcze celowo nie podłączono

- dostawcy danych rynkowych;
- brokera demonstracyjnego;
- strategii decydującej o kupnie lub sprzedaży;
- automatycznych harmonogramów sesji giełdowych;
- podatków, przewalutowania i raportowania właściwego dla wybranego rynku;
- jakiejkolwiek ścieżki do prawdziwego rachunku.

Najpierw trzeba wybrać klasę aktywów (na przykład akcje, ETF-y albo krypto),
rynek, walutę bazową, częstotliwość danych i brokera demonstracyjnego. Dopiero
wtedy można poprawnie zaprojektować kalendarze, typy zleceń, źródło ceny,
opłaty i ograniczenia konkretnego rynku.

## Bramy bezpieczeństwa przed dalszym etapem

Przed rozważeniem prawdziwych zleceń wszystkie poniższe warunki muszą być
spełnione i udokumentowane:

1. Kontrola jakości licencjonowanych danych historycznych i bieżących.
2. Backtest z kosztami, poślizgiem i podziałem na okres treningowy oraz
   całkowicie niewidziany okres testowy.
3. Testy walk-forward i odporności na zmianę parametrów.
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

Powtórzenie identycznego identyfikatora cyklu nie tworzy drugiej pozycji.
Kill switch blokuje nowe wejścia, ale nie usuwa możliwości bezpiecznego
zamknięcia istniejącej pozycji. Sygnały LONG i SHORT są wyłącznie symulowane.

Warstwa danych tylko do odczytu jest przygotowana, lecz domyślnie wyłączona.
Obejmuje cztery rozdzielone role:

- OANDA REST-V20 `practice` — główne kwotowania i zamknięte świece M15;
- Twelve Data — niezależny kurs średni do wykrywania rozbieżności;
- NBP Web API — publiczny dzienny kurs referencyjny USD/PLN;
- FMP Stable Economic Calendar — zaplanowane wydarzenia gospodarcze.

Każdy adres HTTPS i ścieżka są ustalone w kodzie. OANDA ma wyłącznie host
`api-fxpractice.oanda.com`; nie istnieje host live ani ścieżka składania zleceń.
Klucze są pobierane z ignorowanego `config/forex.env`, przekazywane w nagłówkach
i ukryte w reprezentacji obiektów oraz statusie.

Przed każdym wejściem bramka wymaga dwóch świeżych, zgodnych źródeł ceny.
Rozbieżność większa niż 0,2%, brak jednej z siedmiu par, stary kalendarz,
wydarzenie wysokiej ważności w oknie 30 minut, zamknięty rynek albo kurs NBP
starszy niż cztery dni blokują nowe pozycje. Dane NBP są referencją księgową dla
PAPER, a nie drugim źródłem ceny wykonania. Spot Forex nie ma jednego centralnego
wolumenu całego rynku, dlatego tick volume pozostaje tylko jednym z filtrów.

## Uruchomienie danych demonstracyjnych — kolejność

1. Utworzyć osobny rachunek OANDA fxTrade Practice i token API. Dostępność
   REST-V20 zależy od oddziału OANDA.
2. Utworzyć bezpłatny klucz Twelve Data i sprawdzić limit bieżącego planu.
3. Utworzyć klucz FMP oraz potwierdzić dostęp do `stable/economic-calendar`.
4. Skopiować `config/forex.env.example` do lokalnego `config/forex.env`, wkleić
   klucze i ustawić `JARVIS_OS_FOREX_DATA_ENABLED=true`.
5. Wykonać serię cykli obserwacyjnych bez pozycji i sprawdzić świeżość,
   rozbieżności, weekend oraz blokady wydarzeń.
6. Dopiero po zielonej serii uruchomić autonomiczne pozycje PAPER. Rachunek
   prawdziwy, dźwignia i zlecenia live pozostają poza zakresem.

Dokumentacja źródeł: [OANDA REST-V20](https://developer.oanda.com/rest-live-v20/development-guide/),
[Twelve Data](https://twelvedata.com/docs/currencies),
[NBP Web API](https://api.nbp.pl/) i
[FMP Economic Calendar](https://site.financialmodelingprep.com/developer/docs/stable/economics-calendar).
