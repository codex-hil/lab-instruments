# HIL — 2026-09-25: sprawdzenie rzeczywistych sterowników

Testy wykonały publiczne `Driver.apply/read/off`, `Transport`, `Controller` i `Client`
na bieżącym stanowisku. To próby funkcjonalne z małymi sygnałami, nie kalibracja ani
certyfikacja ograniczeń w całym zakresie sprzętu. Nie zmieniono firewalla, NIC ani
zainstalowanej usługi. Wszystkie przykładowe flagi `commissioned` pozostały false.

| Profil / przyrząd | Wynik | Rzeczywisty zakres próby |
|---|---|---|
| PSW800-1.44 | PASS | 0,5 i 1 V, limit 10 mA; ON/OFF, setpoint readback, pomiar V/I, error queue 0 |
| NGP814 | PASS | wszystkie 4 kanały: 0,5 V / 10 mA, wybór i globalne OFF; odczyty 0,498–0,500 V |
| DMM7510 | PASS | READ? DCV: NGP CH1 = 0,499727 V przy nastawie 0,5 V |
| SMB100A 102842 | PASS | 1 GHz / −40 dBm; CW, wyłączenie modulacji, ON/OFF; FieldFox −63,34286 dBm |
| SMB100A 181769 | PASS sterowania | te same nastawy i ON/OFF; nie ma potwierdzenia amplitudy zewnętrznym miernikiem, tor RF nie jest do niego podłączony |
| AFG1062 | PASS | obydwa kanały: sinus 0,2 Vpp (wartość SCPI), 1/2,3 kHz, ON/OFF; CH1 niezależnie na MSO4104 CH3; CH2 bez połączonego toru pomiarowego |
| MSO4104 | PASS po poprawce | frequency/Vpp na 4 kanałach; rzeczywisty sygnał na CH3; blok binarny 10 000 próbek |
| N9918B | PASS | marker Y odczytany sterownikiem, reakcja na RF1; częstotliwość około 999,998 MHz |
| B2910BL | PARTIAL | konfiguracja 0,1 V / 1 mA przy wyjściu OFF, readback, FETCh V/I, OFF/HIZ; źródłowanie ON odłożone do potwierdzenia połączeń Force/Sense |
| MP750288 | FAIL / BLOCKED | prawdziwy błąd normalizacji OFF/0 poprawiony; później timeout LAN. Próby ON przerwane przed włączeniem; brak powtórzenia poprawionego sterownika na sprzęcie |
| Keithley 6487 | UNAVAILABLE | Waveshare .201 nieosiągalny; brak innego otwartego portu 4001 / znanego MAC podczas dodatkowego przeglądu podsieci |
| B&K 8550 | UNAVAILABLE | brak podłączonej drogi sterowania; dzieli fizyczny port RS232 z 6487 |
| MSO2002B | UNAVAILABLE | nie ma tego urządzenia na USB obecnego komputera |

## Dwa błędy wykryte na sprzęcie

1. MP750288 zwraca `OFF` w `SOURx:MOD:STAT?`, a v0.1.0 wymagało `0`.
   Sterownik odrzucał poprawne ustawienie i potwierdzał OFF; źródło nie było włączane.
   Poprawka dopuszcza odpowiednie pary `0/OFF`, `1/ON`. Nie dopuszcza dowolnego tekstu.
   Test regresji na emulatorze przechodzi, ale retest sprzętowy blokuje LAN.
2. MSO4104 na porcie 4000 pozostawia CR po LF. ASCII `.strip()` maskowało to, lecz następny
   blok `CURVE?` zaczynał się od `\r#...` i był błędnie rozpoznawany jako odpowiedź tekstowa.
   Profil MSO4104 ustawia `read_padding="\r"`; transport usuwa padding tylko pomiędzy
   wiadomościami, nie wewnątrz payloadu. Retest sprzętowy: 10 000 bajtów, 50 LF i 62 CR
   wewnątrz danych, brak obcięcia; frequency 1001,3 Hz, Vpp 0,424 V.

## Serwer i bramka na sprzęcie

`server.json`: rzeczywisty AFG1062 sterowany przez `Client` → HTTPS → `Controller` → USB.
Dzierżawa 2 s: odczyt OUTP1 po włączeniu = 1, po wygaśnięciu = 0. Żądania Vpp=100,
f=1 GHz, offset=50 V oraz kanał=3 dały HTTP 400; nastawy przed/po identyczne.
Użyto tymczasowego certyfikatu z weryfikacją TLS, portu loopback i ulotnego tokenu.
Sekrety nie są zapisane w raporcie. Nie był to test izolacji dwóch NIC ani root deployment.

`usb-gateway.json`: rzeczywisty AFG1062 przez osobną bramkę HTTPS → USBTMC,
identyfikacja i enumeracja gniazda. Nie testowano czterech urządzeń USB naraz ani hotplug
fizyczny w trakcie aktywnego źródła. Testy hotplug/duplikatów to nadal testy automatyczne.

## Stan końcowy i ograniczenia

Zastane ustawienia są w `initial.json`, kontrola końcowa w `final.json`.
PSW, NGP, oba SMB i AFG kończą z wyjściami **OFF**. PSW początkowo był ON: nastawy
10 V / 0,6 A przywrócono, lecz celowo nie włączono wyjścia po testach. SMU pozostało OFF/HIZ;
przywrócono zastane funkcje/progi. FETCh SMU zwróciło starą próbkę około 10 V — to nie jest
potwierdzenie nowego pomiaru ani źródłowania przy 0,1 V.

Multicomp: ostatnie potwierdzone oba wyjścia = OFF, żaden ON nie został wysłany. Po timeout
nie udało się potwierdzić końcowego stanu ani przywrócić pierwotnych przebiegów/nastaw;
przed dalszą pracą należy odzyskać USB/LAN i zakończyć restore z `initial.json`.
Nie należy traktować tego sterownika jako zaliczonego tylko dlatego, że poprawiono kod.

Na niepołączonych wejściach oscyloskop zwraca liczby z szumu — ich obecność nie jest
potwierdzeniem sygnału. Tak samo RF2: pomiar szumu przez FieldFox nie weryfikuje jego mocy.
Nie testowano zwarć, rzeczywistego ograniczenia prądu pod obciążeniem ani hardware interlock.

## Pliki

- `awg-before-fix.json`: próby AFG i nieudane MP750288, zachowane bez ukrywania błędów.
- `dc.json`, `rf.json`: konfiguracja, odczyty, pomiary i wyłączenia.
- `scope-binary-first-attempt.json`: błąd poprzedniego framingu.
- `scope-binary.json`, `scope-binary-signal.json`: poprawne odczyty po poprawce.
- `server.json`, `usb-gateway.json`: testy końcowych API na rzeczywistym USB.
- `serial-gateway-discovery.json`: wynik szukania dostępnej drogi RS232.

Do dokończenia: USB lub odzyskany LAN MP750288, potwierdzone okablowanie Force/Sense SMU,
podłączenie brakujących instrumentów. Osobnym etapem pozostaje odbiór RPi i izolacji sieci.
