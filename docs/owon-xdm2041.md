# OWON XDM2041 przez WIZnet — przekazanie

Uruchomiono 2026-11-13: **OWON XDM2041, serial 25510487, firmware V3.3.0,3**.
WIZ752SR-12x firmware 2.0.0, MAC **00:08:DC:83:61:ED** (poprzednia bramka ma EE).
Nowa bramka była na fabrycznym 192.168.11.2, IM0. Ustawiono IM1 (DHCP), zapisano
SV i zrestartowano RT. Odczyt po restarcie potwierdził DHCP i **192.168.2.27**.
Nie zmieniano routera, firmware ani parametrów samego miernika.

Miernik działa na drugim porcie bramki: **TCP 5001**, RS232 **115200 8N1**, bez
flow control. TCP 5000 nie odpowiedział na IDN. Oba porty zachowały fabryczne
parametry szeregowe. LF kończy zapytania, CRLF odpowiedzi. Odpowiedź może być
rozbita na kilka pakietów TCP — używać Transport, nie pojedynczego recv().

## CLI i API

Kod: gałąź `feature/owon-xdm2041` publicznego repo lab-instruments.
Konfiguracja: `examples/owon-xdm2041.json`, alias `owon_dmm1`; dodany też do examples/lab.json.

```sh
flock -n /home/codex-hil/.cache/wiznet-0008dc8361ed.lock \
 python3 -m labinstruments identify --config examples/owon-xdm2041.json --device owon_dmm1
flock -n /home/codex-hil/.cache/wiznet-0008dc8361ed.lock \
 python3 -m labinstruments read --config examples/owon-xdm2041.json --device owon_dmm1 --operation function
flock -n /home/codex-hil/.cache/wiznet-0008dc8361ed.lock \
 python3 -m labinstruments read --config examples/owon-xdm2041.json --device owon_dmm1 --operation reading
```

Python: `Driver(io, 'xdm2041', '25510487')` na istniejącym `Transport`.
`read('function')` używa FUNC1?, `read('reading')` MEAS1? (główny wyświetlacz).
Obie metody zwracają tekst. Jednostki wynikają z funkcji, np. "VOLT" to DC V.
To odczyt wyświetlanego wyniku, bez gwarancji nowej konwersji przy każdym zapytaniu.
Nie wysyłamy READ?, nie zmieniamy funkcji/range/triggera. Kanał API=1, nie port bramki.
Zmiana funkcji, drugi wyświetlacz i ustawianie zakresu nie są zaimplementowane.

Wspólny kooperatywny lock obejmuje obie strony bramki: utrzymać go przez całą
sesję, również discovery/konfigurację. Driver nie pozyskuje go automatycznie.
Nie usuwać locka ani nie omijać aktywnego właściciela.

## DHCP i odtwarzanie bramki

IP jest wskazówką. `python3 tools/wiznet/discover.py` odczytuje urządzenia WIZnet
przez UDP broadcast 255.255.255.255:50001 i wypisuje JSON. Wymaga wolnego lokalnego
UDP 50001. Wybrać MAC ED, zaktualizować host, potem zweryfikować ID/serial miernika.
Skrypt nie zapisuje konfiguracji i nie pokazuje hasła/search ID. Nie ma automatycznego
wyszukiwania WIZnet w Transport; po zmianie DHCP aktualizacja IP jest jawna.

Protokół konfiguracji: MA + sześć binarnych bajtów MAC + CRLF, PW + spacja + CRLF,
następnie dwuznakowe komendy zakończone CRLF. Zapisy wysyłać tylko do dokładnego
MAC, nigdy broadcast MAC. IM1=DHCP, SV=save, RT=restart; BR12/EB12=115200,
DB1/ED1=8 bitów, PR0/EP0=none, SB0/ES0=1 stop, FL0/EF0=no flow control.
Istniejący stan: OP1/QO1 TCP server, LP5000/QL5001. Pełny odczyt w raporcie.
Restart bramki wymaga wyłącznego dostępu, zrywa oba połączenia.

## Walidacja i źródła

[ID i trzy odczyty](../reports/owon-xdm2041-20261113.json),
[stan bramki](../reports/wiznet-8361ed-20261113.json).
Funkcja przed/po: "VOLT"; odczyty ok. −91…−69 µV. Nie znamy połączeń wejścia,
więc nie jest to walidacja dokładności ani potwierdzenie zera. Komunikacja PASS;
porównanie ze wzorcem i pełna walidacja metrologiczna NOT_RUN.

- [Instrukcja programowania OWON](https://www.owon.co.jp/download/01a0bfb3-ea45-7e96-9701-3b58f51ed344/)
- [Instrukcja użytkownika, RS232](https://files.owon.com.cn/probook/XDM2041_USER_MANUAL.pdf)
- [Protokół konfiguracji WIZnet](https://docs.wiznet.io/Product/Modules/Serial-to-Ethernet-Module/WIZ752SR-125/command-manual-EN)

## Nazwy egzemplarzy

- **OWON DMM1**, alias `owon_dmm1`: serial **25510487**, obecnie TCP **5001**.
- **OWON DMM2**, alias `owon_dmm2`: serial **25510466**, TCP **5000**.

Oba egzemplarze zidentyfikowano jednocześnie 2026-11-13; oba firmware V3.3.0,3.
DMM2 dodano do obu konfiguracji. Te same komendy powyżej działają z
`--device owon_dmm2`. Utrzymać wspólny lock całej bramki.
[Raport identyfikacji i odczytów DMM2](../reports/owon-dmm2-20261113.json).
Nazwy podążają za egzemplarzami, nie portami. Zamiana kabli wymaga aktualizacji
portów, a kontrola serialu chroni przed użyciem innego miernika. Dawny alias
`owon_dmm` zastąpiono `owon_dmm1` — zaktualizować wcześniejsze skrypty.
