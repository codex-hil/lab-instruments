# Keithley 6487: źródło DC do ±500 V

Rozszerzenie źródła: **UNTRUSTED**, bez fizycznego commissioningu. Obsługa pomiaru
`reading` pozostaje dostępna. `source_state` zwraca nastawy i status, nie zmierzone
napięcie na wyjściu.

## API i protokół

Ten sam `Driver.apply(params, limits)` oraz chronione API `/v1/control` co dla
pozostałych źródeł. Kompletny stan ma postać:

```json
{"channel": 1, "voltage": 500, "current": 0.000025, "enable": false}
```

Jednostki: V i A. `current` oznacza ograniczenie prądu źródła, nie wymuszony prąd.
`enable: false` ustawia napięcie przy wyłączonym wyjściu. Włączenie wymaga jawnego
`enable: true`, dopuszczenia przez politykę, a na serwerze także `commissioned: true`.
Nie ma oddzielnej komendy ON pomijającej walidację kompletnego stanu.

- Limit drivera: −500…+500 V, niezależnie od szerszej polityki administratora.
- Automatyczny zakres: 10 V dla |V| ≤ 10, 50 V dla |V| ≤ 50, inaczej 500 V.
- Limity I: 25 µA, 250 µA, 2,5 mA; 25 mA wyłącznie na zakresie 10 V.
- Niedostępne wartości I są odrzucane, bez zaokrąglania w górę.
- Polityka ogranicza również `abs(voltage) * current`.

Sekwencja SCPI: weryfikacja ID/modelu/numeru seryjnego, `SOUR:VOLT:SWE:ABOR`,
`SOUR:VOLT:STAT OFF` i potwierdzenie, ustawienie ILIM 25 µA, RANG, docelowego ILIM
oraz VOLT. Każda końcowa nastawa i stan zakończenia sweep są odczytywane.
Przed ON driver sprawdza `SOUR:VOLT:INT:FAIL?`; stan aktywny lub nierozpoznany
blokuje włączenie. Po ON sprawdza STAT. Błąd powoduje próbę OFF; brak potwierdzenia
OFF jest zgłaszany jako niepewny stan. Driver nie zmienia ani nie omija interlocka.

OFF w tym modelu oznacza niskoimpedancyjne źródło 0 V z ograniczeniem prądowym,
nie fizyczne rozłączenie zacisków. Potwierdzenie OFF nie jest pomiarem rozładowania DUT.
Odczyt STAT ON również nie potwierdza rzeczywistego napięcia ani braku ograniczenia I.

Transport: TCP przez RS232, w dotychczasowym labie 9600 8N1, odpowiedź zakończona CR.
Zapisany endpoint `192.168.2.201:4001` wymaga ponownej weryfikacji po podłączeniu.
[Instrukcja producenta, sekcja 3 i tabela SOURce sekcji 14](https://www.tek.com/-/media/documents/6487-901-01d_oct2020.pdf).

## Konfiguracja i użycie

`examples/lab.json`, urządzenie `pico`: serial 4563048, `commissioned: false`,
`allow_output: false`, limit 2,5 mA i 1,25 W, lease 10 s. Te blokady pozostają
niezmienione do odbioru sprzętowego. Wdrożenie chronione wymaga root-owned config,
zgodnie z istniejącą architekturą. Bezpośredni Driver jest API dla zaufanego kodu;
nie zastępuje egzekwowania polityki przez serwer.

Odczyt nastaw:

```sh
python3 -m labinstruments read --config examples/lab.json --device pico --operation source_state
```

Po commissioningu przykład ustawienia 10 V / 25 µA **z wyjściem OFF**:

```sh
python3 -m labinstruments client --url https://127.0.0.1:8443 \
  --ca-file /path/to/ca.crt --token-file /path/to/token \
  --device pico --action apply \
  --args '{"channel":1,"voltage":10,"current":0.000025,"enable":false}'
```

Adres/port i pliki TLS należy dopasować do istniejącej konfiguracji serwera.
Lease i watchdog działają jak dla innych źródeł. Utrata połączenia uniemożliwia
zagwarantowanie OFF; watchdog programowy nie zastępuje sprzętowego interlocka.

## Walidacja 2026-10-02

80 testów automatycznych PASS, w tym 8 nowych testów źródła 6487 z transportem
symulowanym: dobór zakresów i polaryzacji, dyskretne limity I, granica 500 V,
polityka mocy/enable, otwarty interlock, timeout/readback mismatch, odczyt bez
zapisu, blokada nieodebranego urządzenia i wymagany numer seryjny.

OPEN ITEM — po odzyskaniu połączenia:

1. Sprawdzić identyfikację, firmware, terminatory i odczyt source_state.
2. Potwierdzić OFF oraz sekwencję ustawiania/odczytu zakresów i limitów bez ON.
3. Przy odpowiednim stanowisku i mierniku rozpocząć od 1–10 V / 25 µA;
   porównać napięcie i ograniczenie I z niezależnym pomiarem.
4. Sprawdzić oba znaki oraz przejścia 10/50/500 V; stopniowo dojść do 500 V
   przy osprzęcie przystosowanym do tego napięcia. Zapisać błędy liczbowe.
5. Sprawdzić odmowę ON przy otwartym interlocku, OFF, abort sweep, wygaśnięcie
   lease oraz zachowanie po utracie komunikacji. Nie omijać interlocka.
6. Zapisać połączenia, obciążenie, numery przyrządów, surowe odpowiedzi i wyniki.
   Dopiero wtedy ocenić commissioning i zaproponować zmianę trust state.

Żadne polecenia sprzętowe nie zostały wysłane w ramach tego rozszerzenia.
