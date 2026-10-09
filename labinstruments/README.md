# Drivery urządzeń i transporty

Python 3.11+, Linux, biblioteka standardowa. Kod działa z checkoutu lub zipapp;
nie wymaga uruchamiania serwera sterowania. [Budowanie](../README.md#nowa-maszyna--budowanie-offline).

## Modele i protokoły

| Klucz modelu | Przyrząd | Droga komunikacji w laboratorium | Zakres drivera |
|---|---|---|---|
| `psw800-1.44` | GW Instek PSW800-1.44 | SCPI / TCP 2268 | nastawy DC V i limit I, pomiary V/I, ON/OFF |
| `ngp814` | R&S NGP814 | SCPI / TCP 5025 | wybór kanału 1–4, DC V i limit I, pomiary, globalny OFF |
| `b2910bl` | Keysight B2910BL | SCPI / TCP 5025 | źródło DC V z compliance I, local sense, FETCh, HIZ/OFF |
| `smb100a` | R&S SMB100A | SCPI / TCP 5025 | nośna CW, częstotliwość, dBm, RF ON/OFF |
| `afg1062` | Tektronix AFG1062 | SCPI / USBTMC | sinus, częstotliwość, Vpp, offset, kanały 1–2 |
| `mp750288` | Multicomp Pro MP750288 | SCPI / TCP 3000 lub USBTMC | sinus, częstotliwość, Vpp, offset, kanały 1–2 |
| `mso4104` | Tektronix MSO4104 | SCPI / TCP 4000 | immediate frequency/Vpp, kanały 1–4 |
| `mso2002b` | Tektronix MSO2002B | SCPI / USBTMC | podstawowy profil frequency/Vpp, oczekuje na test sprzętowy |
| `dmm7510` | Keithley DMM7510 | SCPI / TCP 5025 | READ? w aktualnie ustawionej funkcji |
| `6487` | Keithley 6487 | SCPI / RS-232 przez TCP 4001 | READ?, wyłączenie źródła napięcia |
| `8550` | B&K Precision 8550 | SCPI / RS-232 przez TCP 4001 | CC w zakresie 3 A, pomiar V/I, input ON/OFF |
| `fca3003` | Tektronix FCA3003 | SCPI / USBTMC, bramka RPi | częstotliwość A/B/C, okres, czas, duty, Vpp; [API i HIL](../docs/fca3003.md) |
| `n9918b` | Keysight FieldFox N9918B | SCPI / TCP 5025 | odczyt istniejącego markera 1 |

Porty TCP to ustawienia profili/stanowiska, można je zmienić. Samo istnienie profilu
nie oznacza pełnej weryfikacji: [macierz HIL i ograniczenia](../reports/hil-2026-09-25/README.md).
MP750288 wymaga retestu po naprawie OFF/0; SMU przetestowano częściowo; 6487 był
nieosiągalny przez bramkę, B&K odłączony, MSO2002B niepodłączony.

## Użycie bez serwera

```python
from labinstruments.transport import Transport
from labinstruments.drivers import Driver

with Transport({"kind": "tcp", "host": "192.168.2.9", "port": 4000}) as io:
    scope = Driver(io, "mso4104", serial="C020817")
    print(scope.identify())
    print(scope.read("frequency", channel=3))
```

`Driver.identify()` sprawdza model i opcjonalny numer seryjny z `*IDN?`.
`read(operation, channel=1)` zwraca surowe odpowiedzi tekstowe; nie jest jeszcze
uniwersalnym wynikiem z jednostką i znacznikiem czasu. READ? miernika może uruchomić
nowy pomiar; FETCh SMU zwraca poprzednią próbkę. Pomiar immediate oscyloskopu zmienia
wybór pomiaru i HEADER. Szczegóły: [profile](../docs/models.md).

`apply(params, limits)` konfiguruje pełny stan, najpierw wyłączając wszystkie wyjścia,
weryfikuje nastawy i opcjonalnie włącza wybrany kanał. `off()` wyłącza wyjścia i sprawdza
potwierdzenie. Parametry: V, A, Hz, Vpp, offset w V, moc RF w dBm; pola opisuje
[API](../docs/protocol.md). Bezpośrednie `Driver.apply` nie ma watchdogu serwera:
skrypt odpowiada za zakończenie pracy i OFF. Limity podane przez skrypt są walidacją,
nie granicą uprawnień roota. Nie ma rezerwacji przyrządu pomiędzy niezależnymi skryptami.

## Warstwa transportu

- `tcp`: surowy strumień TCP; komendy tekstowe domyślnie kończą się LF.
  Odpowiedzi Keithley 6487 kończą się CR: `read_termination: "\r"` (CLI ustawia go
  dla tego profilu). MSO4104 ma dodatkowy padding CR pomiędzy odpowiedziami;
  konstruktor drivera ustawia właściwą obsługę.
- `usb`: Linux `/dev/usbtmcN`, wybór przez serial lub topologię, opcjonalnie VID/PID.
  Koniec wiadomości jest ustalany przez USBTMC EOM, również dla danych binarnych.
- `gateway`: HTTPS do Raspberry Pi; slot, bajty base64 i jawna flaga oczekiwania na
  odpowiedź. [Dokładny protokół](../docs/protocol.md). Nie jest to USB/IP ani VISA.

TCP obsługuje bloki binarne IEEE 488.2 o jawnej długości (`#<liczba cyfr><długość>...`)
z terminatorem po danych. Bloki `#0` są odrzucane. Limit wiadomości: 16 MiB.
`Transport.transaction(data, expect_reply)` przekazuje bajty; `query`/`write` są
metodami tekstowymi. Nie ma automatycznego powtarzania zapisów ani przełączania LAN/USB.

Przesył binarny MSO4104 sprawdzono na 10 000 próbek. Gotowe API zwracające tablice czasu
i napięcia nie jest jeszcze zaimplementowane; podobnie eksport screenshotów.
Nie należy utożsamiać możliwości transportu z gotową metodą drivera.

## Pliki

- [drivers.py](drivers.py): profile, walidacja, komendy i kontrola odpowiedzi.
- [transport.py](transport.py): TCP, USBTMC, klient bramki, framing.
- [service.py](service.py): opcjonalny serwer `control` i bramka `usb-gateway`.
- [client.py](client.py): klient opcjonalnego serwera sterowania.
- [__main__.py](__main__.py): CLI; `python3 -m labinstruments --help`.

Nowy model wymaga weryfikacji dokumentacji, tożsamości, terminatorów i komend, testów
bez sprzętu oraz osobnego raportu próby sprzętowej. Sam podobny panel/rebrand nie
wystarcza. [Źródła dokumentacji producentów](../docs/sources.md).
