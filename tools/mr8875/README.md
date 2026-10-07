# Hioki MR8875 — materiały do drivera

Zebrano 2026-10-07. Połączenie LAN potwierdzone 2026-10-07: `192.168.2.13:8802`. Identyfikacja i wyposażenie zapisane w [evidence/lan_identification.json](evidence/lan_identification.json). Nie uruchamiano pomiaru.

## Działające narzędzie laboratoryjne

Panel: **http://192.168.2.107:8875/** (komputer stanowiska), urządzenie: `192.168.2.13:8802`.

Pierwsza wersja działa bez dodatkowych pakietów Python, na Pythonie 3.10 lub nowszym. Kod jest w `hioki_lab/`. W repozytorium projekt znajduje się w `tools/mr8875/`. Panel jest obsługiwany przez usługę użytkownika `hioki-lab.service`. Na czas przerwy usługa została zatrzymana i wyłączono automatyczny start; nie uruchamia ona samodzielnie rejestracji w MR8875.

```sh
cd tools/mr8875
python3 -m hioki_lab.server --host 192.168.2.13 --bind 127.0.0.1 --port 8876
```

Powyższe polecenie jest alternatywą do testowania drugiej instancji; pracując z jednym urządzeniem używać tylko jednej instancji do sterowania. Domyślny zapis sesji: `/srv/codex-hil-data/hioki-mr8875/sessions/`. Każda sesja ma `data.csv` i `metadata.json` (identyfikacja, moduły, tryby, zakresy, jednostki/skaling, kanały, czasy, flaga próby bez sygnałów).

Obsługa usługi:

```sh
systemctl --user start hioki-lab.service
systemctl --user status hioki-lab.service
systemctl --user restart hioki-lab.service
systemctl --user stop hioki-lab.service
```

Funkcje pierwszej wersji:

- Rozpoznanie modelu, firmware i modułów, automatyczne ponawianie odczytu po błędzie komunikacji.
- Bieżące odczyty wybranych kanałów przez `MEMory:GETReal` / `MEMory:REAL?`, około raz na sekundę. Wykres pokazuje historię 300 odczytów; każdy kanał ma osobną skalę.
- Zapis sesji podglądu na komputerze; przerwy komunikacji są zapisane w metadanych, stare wartości nie są dopisywane jako nowe próbki.
- Konfiguracja MR8902: napięcie/temperatura, zakres /div, typ termopary i włączenie kanału. Tryb cyfrowego filtra, RJC i wykrywanie przerwania termopary pozostają ustawieniami urządzenia.
- Konfiguracja okresu próbkowania (0,01–3 s) i długości przebiegu (5–1000 działek), z odczytem rzeczywistej wartości zaakceptowanej przez urządzenie.
- START/STOP rejestracji w MR8875. START używa aktualnego trybu wyzwalania/powtarzania; panel nie zmienia go automatycznie. Nie modyfikuje definicji ani ustawień nadawania CAN.
- Pobranie zakończonego przebiegu wybranych włączonych kanałów komendą `MEMory:VDATa?`, w blokach do 2000 próbek; limit 100 000 próbek/kanał. Eksport CSV zawiera wartości fizyczne zwrócone przez urządzenie.
- Oś czasu przebiegu jest liczona od pierwszej zapisanej próbki. Gdy rejestracja została rozpoczęta przez ten driver, metadane używają konfiguracji sprzed START. Dla wcześniejszego przebiegu lub po restarcie aplikacji `sample_time_source=current_settings_unverified`: aktualny okres próbkowania może różnić się od okresu starego przebiegu. W takiej sytuacji sprawdzić ustawienia źródłowe przed interpretacją czasu.

Kanały CAN w tej wersji korzystają z definicji przygotowanych w MR8904/CAN Editor. Import DBC, konfiguracja magistrali i nadawanie CAN nie są zaimplementowane. Kanały logiczne CAN i wewnętrzne kanały logiczne nie są obecnie wyświetlane w panelu.

## Odtworzenie po przerwie

1. Sklonować repozytorium i wejść do `tools/mr8875`.
2. Uruchomić testy z sekcji poniżej. Do testów programowych nie trzeba urządzenia.
3. Po podłączeniu MR8875 sprawdzić IP oraz włączone komendy LAN (port 8802).
4. Uruchomić `python3 -m hioki_lab.server --host ADRES_IP --storage /ścieżka/do/sesji`. Na innym komputerze zmienić IP; domyślnie panel nasłuchuje na `127.0.0.1:8875`.
5. Szablon `hioki-lab.service` wymaga dopasowania `WorkingDirectory` i `ExecStart` do lokalizacji checkoutu. Na obecnym stanowisku skonfigurowano oryginalną ścieżkę `/home/codex-hil/hioki-mr8875`.

Kopie sesji testowych są w `evidence/sessions/`. Wszystkie zostały wykonane bez sygnałów; nie są danymi kalibracyjnymi. Pełny manifest CD opisuje także pliki niewersjonowane w repozytorium. `SHA256SUMS` zawiera również sumę lokalnego obrazu CD; nie da się zweryfikować tego jednego wpisu z samego checkoutu.

## Weryfikacja pierwszej wersji

2026-10-07, rzeczywisty MR8875 V2.20, **bez sygnałów na wejściach**:

- odczyt konfiguracji 30 kanałów i bieżących wartości;
- zmiana zakresu MR8902 z 500 µV/div na 1 mV/div i przywrócenie;
- pojedyncza rejestracja z okresem 10 ms, długością 5 działek; pobrano 501 próbek dla czterech kanałów MR8902 i sprawdzono CSV;
- przywrócenie wcześniejszych ustawień czasu, długości i trybu wyzwalania;
- zapis i zakończenie sesji podglądu, pobranie CSV i metadanych przez HTTP;
- testy w Chromium: wartości na żywo, zapis sesji, wybór kanałów, widok komputerowy i mobilny, brak błędów JavaScript;
- testy drivera: dzielone odpowiedzi TCP, nagłówki, zerwane połączenie, blokowanie zmiany ustawień podczas pomiaru, odczyt przebiegu przekraczającego pojedynczy blok.

Dowody: `evidence/hardware_smoke_test.json`, `evidence/panel_api_smoke_test.json`, początkowa konfiguracja w `evidence/initial_configuration.json`. Odczyty z otwartych wejść nie potwierdzają dokładności. Pomiar znanego napięcia/termopary, CAN i zachowanie podczas rzeczywistego zerwania LAN nadal wymagają prób sprzętowych.

```sh
python3 -m unittest discover -s tests -v
```

## Pobrane dokumenty producenta

PDF-y są w `materials/pdf/`; odpowiedniki tekstowe z zachowaniem układu stron w `materials/text/`.

| Plik | Zastosowanie |
| --- | --- |
| [MR8875_instruction_manual_EN_v11.pdf](materials/pdf/MR8875_instruction_manual_EN_v11.pdf) | MR8875A982-11: ustawienia pomiarów, LAN/TCP, FTP, HTTP, USB, specyfikacje MR8901/MR8902, format CSV |
| [MR8904_CAN_instruction_manual_EN_v04.pdf](materials/pdf/MR8904_CAN_instruction_manual_EN_v04.pdf) | MR8904A981-04, październik 2025: CAN Editor, dekodowanie, przypisanie kanałów, import bazy CAN, konfiguracja odbioru i nadawania |
| [MR8901_MR8902_modules_instruction_manual_EN_v03.pdf](materials/pdf/MR8901_MR8902_modules_instruction_manual_EN_v03.pdf) | MR8901A980-03: wspólna instrukcja instalacji modułów, japoński/angielski; szczegółowe specyfikacje są w instrukcji głównej |
| [MR8875_measurement_guide_EN_v02.pdf](materials/pdf/MR8875_measurement_guide_EN_v02.pdf) | Przykłady konfiguracji i obsługi pomiarów |
| [MR8875_brochure_EN.pdf](materials/pdf/MR8875_brochure_EN.pdf) | Zestawienie parametrów i ograniczeń urządzenia, modułów i CAN Editor |

[Manifest](materials/manifest.json) zawiera adresy źródłowe, wyniki pobierania, rozmiary i SHA-256. Zachowano również strony producenta w `materials/sources/`. Nie uruchamiano ani nie instalowano oprogramowania, nie zmieniano firmware.

## Materiały z dostarczonej płyty CD

2026-10-07 skopiowano całą płytę HIOKI (UDF 1.02, data utworzenia woluminu 2022-04-15). Kopia zawiera 3227 plików, 272 875 376 bajtów. Sprawdzono obecność i rozmiary wszystkich plików względem katalogu UDF; zapisano SHA-256 każdego pliku i całego obrazu płyty.

Ze względu na pełną partycję systemową dane są na `/srv/codex-hil-data/hioki-mr8875/`. Na stanowisku `materials/cd` jest dowiązaniem do pełnej kopii. W repozytorium zachowano tylko katalog `materials/cd/MR8875/english` z dokumentacją komend i przykładami drivera; pozostałe programy z CD i jego obraz są w lokalnym archiwum. Nie uruchamiano instalatorów ani przykładów EXE; napęd czytano bezpośrednio, bez montowania.

- [Dokumentacja komend MR8875, angielska](materials/cd/MR8875/english/index.htm) — pełna instrukcja interfejsu w HTML, wraz z ilustracjami i stronami szczegółowymi.
- [Tekst dokumentacji komend](materials/text/MR8875_communication_manual_CD_EN.txt) — wyciąg z HTML z nagłówkami wskazującymi ścieżki źródłowe. Kolejność plików jest leksykograficzna; w razie niejasności sprawdzić oryginalne tabele HTML.
- Przykłady źródłowe Visual Basic LAN: `materials/cd/MR8875/english/Files/04/VB_LAN/Sample1`–`Sample4`.
- Przykłady źródłowe Visual Basic USB: `materials/cd/MR8875/english/Files/04/VB_USB/Sample1`–`Sample4`.
- CAN Editor i jego instrukcja: `materials/cd/MR8904 CAN Editor/ENGLISH/`. Instrukcja z CD jest v03; pobrana wcześniej v04 pozostaje nowszym źródłem.
- WaveViewer: `materials/cd/wv/ENGLISH/`.
- Sterownik USB i instrukcja instalacji: `materials/cd/Driver/` (m.in. `HiokiUsbCdcDriver.msi`). Dokumentacja interfejsu MR8875 potwierdza USB Communication Device Class (CDC); zachowanie pod Linuksem pozostaje do sprawdzenia na sprzęcie.
- [Manifest CD](materials/cd-manifest.json), [sumy kontrolne CD](materials/CD-SHA256SUMS), obraz płyty lokalnie: `/srv/codex-hil-data/hioki-mr8875/HIOKI-application-cd.udf`.

Brak pełnej dokumentacji komend jest rozwiązany. Osobne pakiety MATLAB V3.01 (`matalb_e.zip`) i LabVIEW V1.00 (`LVMR8875V100ENG.zip`) nie występują na tej płycie; ich pobranie internetowe nadal wymaga my HIOKI. Źródła Visual Basic z CD są dostępne jako przykłady do implementacji.

Oficjalne strony: [Application Disk Rev46](https://www.hioki.com/us-en/support/download/software/versionup/detail/id_n11161), [MATLAB](https://www.hioki.com/us-en/support/download/software/versionup/detail/id_n9950), [LabVIEW](https://www.hioki.com/us-en/support/download/software/versionup/detail/id_n9695). Nie przypisano płycie konkretnego numeru rewizji bez potwierdzenia w jej zawartości.

## Miejsca przydatne podczas implementacji

Numery stron poniżej są drukowanymi numerami instrukcji, a nie indeksami stron PDF.

- Instrukcja główna, rozdział 12.1: ustawienia sieci i połączenie LAN.
- Rozdziały 12.2–12.3: pobieranie i wysyłanie plików przez FTP.
- Rozdział 12.4, strony 295–299: HTTP, zdalny panel, START/STOP/ABORT, pobieranie przebiegów w binary/text oraz wybrany zakres kursorów. ABORT pomija obliczenia po pomiarze i automatyczny zapis.
- Rozdział 12.6, strona 305: transport komend przez TCP, domyślny port 8802; końcowa cyfra portu jest stała. Odpowiedzi LF lub CR+LF, opcjonalny nagłówek.
- Rozdziały 12.7–12.9: rozróżnienie USB Drive i USB command communication; Instrukcja interfejsu z CD potwierdza USB CDC; sterownik i zachowanie pod Linuksem trzeba zweryfikować sprzętowo.
- Rozdziały 14.4–14.5: zakresy, dokładności, szybkości i ograniczenia MR8901/MR8902.
- Dodatek 2, strona A11: format tekstowy CSV, metadane kanałów, jednostki, czas wyzwolenia, skalowanie i próbki. Parser musi respektować ustawienia separatora i znaku dziesiętnego.
- Instrukcja MR8904, rozdział 5.4: tworzenie definicji i przypisania kanałów, konfiguracja ramek do wysyłania.
- Rozdział 6.4: rozpoczęcie wysyłania wraz z pomiarem lub ręcznie; ręczne włączenie działa podczas trwającego pomiaru.
- Rozdział 7.1, strona 57: nadawanie One Shot, Interval, Response, Program; interwały 10 ms–99,99 s. Aktualna instrukcja jednoznacznie potwierdza nadawanie CAN, mimo sprzecznego starszego FAQ.

## Założenia i weryfikacja po podłączeniu

Preferowany pierwszy transport: LAN/TCP do komend oraz FTP/HTTP do plików. Dostęp do danych przebiegów bezpośrednio przez komendy, ich format i wydajność ustalić z instrukcji komend skopiowanej z CD, następnie sprawdzić sprzętowo.

MR8901 rejestruje do 500 kS/s na kanał; nie jest to obietnica ciągłego streamingu do komputera. MR8902 aktualizuje dane co 10 ms tylko z wyłączonym filtrem i wykrywaniem przerwania termopary; inne ustawienia dają 20 ms, 500 ms lub 2 s.

MR8904 udostępnia wybrane zdekodowane sygnały CAN jako kanały przebiegów. Nie zakładać kompletnego logu surowych ramek z timestampami ani funkcji interfejsu SocketCAN. Instrukcja ostrzega o możliwym pominięciu wiadomości w czasie do 200 µs przetwarzania. Brak CAN FD.

Po podłączeniu: ustalić model i firmware, pozycje modułów, ustawienia portu i delimitera; zweryfikować sesję odczytową, odpowiedzi i timeouty, następnie krótki kontrolowany pomiar i pobranie danych z metadanymi. Test nadawania CAN wykonać osobno na ustalonym stanowisku.
