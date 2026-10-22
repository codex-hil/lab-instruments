# FCA3003 po naprawie FPGA — 2026-10-22

Rzeczywiste pomiary przez USBTMC na RPi `192.168.2.36`, istniejącą klasą
`FCA3003` z tego repozytorium; `simulated: false`. FCA3003 `442678`,
firmware `V1.31 06 Mar 2015 12:55`; AFG1062 `1544477`, firmware V1.0.1.

Użytkownik zgłosił przelutowanie FPGA oraz powrót wyjścia 10 MHz i pomiarów A/B.
Wskazuje to na problem połączeń lutowanych, ale konkretnego połączenia nie ustalono.
Wcześniej self-test zwracał 0 mimo timeoutów pomiarów i zgłaszanego braku 10 MHz.

## Wyniki

AFG: oba wyjścia włączone, 1 MHz; CH1 SIN, amplituda odczytana 1.001 V,
CH2 SQU, amplituda 1.000 V, offset obu 0 V. Nie zmieniano nastaw generatora.
Odczyt amplitudy nastawy nie jest pomiarem napięcia na złączu ani dowodem impedancji obciążenia.

| Wejście FCA | Pomiar 1 [Hz] | Pomiar 2 [Hz] | Pomiar 3 [Hz] |
|---|---:|---:|---:|
| A | 1000000.1554 | 1000000.1609 | 1000000.1617 |
| B po przełożeniu przewodu | 1000000.1609 | 1000000.1623 | 1000000.1618 |

Pierwsza seria przy sygnale na A zawiera także timeout na B, zanim użytkownik
przełożył przewód. Potem dodatkowy odczyt A wyniósł 1000000.1576 Hz,
z kolejką błędów `0, "No error"`. Po przełożeniu przewodu wszystkie trzy pomiary B
przeszły, kolejka błędów również `0, "No error"`. Obie sesje zakończono
USBTMC GOTO_LOCAL, pozostawiając licznik na ostatnio testowanym wejściu.

Surowe raporty pobrane z RPi:

- [Pierwsza seria: A PASS, B jeszcze bez sygnału](hil-after-reflow-20261022.json)
- [Druga seria: B PASS po przełożeniu przewodu](hil-input-b-after-reflow-20261022.json)

Zakres potwierdzenia: identyfikacja AFG/FCA i skalarny pomiar częstotliwości
około 1 MHz na A/B. Odchylenie od nastawy generatora około +0.16 Hz;
bez niezależnego wzorca nie rozstrzyga o błędzie generatora lub licznika.
To nie jest kalibracja ani pełna weryfikacja wszystkich funkcji. Wejście C,
kanał referencji 6 oraz udany pomiar przez HTTPS pozostają niezweryfikowane po naprawie.
Driver AFG1062 jest istniejącym profilem `Driver` w `labinstruments/drivers.py`;
w tej sesji potwierdzono komunikację i odczyty nastaw, bez nowej próby zmiany wyjść.

## Sprawdzenie oprogramowania

`python3 -m unittest discover -s tests -q`: 83 testy, OK, 1 pominięty.
Komunikaty ERROR testów negatywnych są oczekiwane; końcowy wynik zestawu to OK.
Nie były potrzebne zmiany kodu driverów po naprawie sprzętu.
