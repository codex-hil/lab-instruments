# USB-TSMC2: przekazanie dostępu do AWG

Stan sprawdzony 2026-11-19. Punkt wejścia dla następnego wątku/agenta:
przeczytaj [AGENTS.md](AGENTS.md), następnie uruchom poniższy check.
To istniejący driver `mp750288` i transport `gateway`, bez osobnego drivera AWG.

## Tożsamość i adresy

| Element | Wartość |
|---|---|
| Host | Raspberry Pi 5 Model B Rev 1.1, `USB-TSMC2` |
| Serial Pi | `7379fa4619d5d5f0` |
| MAC Ethernet | `88:a2:9e:46:54:12` |
| LAN, obserwacja 2026-11-19 | `192.168.2.10` (DHCP; nie traktować jako tożsamości) |
| Panel/API | `https://USB-TSMC2.local:8840/`, alternatywnie `https://192.168.2.10:8840/` |
| SSH | `usbtsmc@USB-TSMC2.local` |
| Usługa | `labinst`, active/enabled, użytkownik systemowy `labinst` |
| Slot API | `mp750288` |
| Model/serial SCPI | `MP750288` / `1944201` |
| Pełna odpowiedź IDN | `FARNELL,MP750288,1944201,SCPI:99.0 FV:V2.6.1` |
| USB VID:PID | `5345:1235` |
| Port przy wdrożeniu | `3-2`, `/dev/usbtmc0` (nie używać numeru węzła jako selektora) |

Ta fizyczna płytka miała wcześniej obraz PQC i inną nazwę. Obecnie uwierzytelnione SSH
potwierdziło `USB-TSMC2`; nie używać historycznych danych PQC/ZeroTier jako dowodu dostępu.
Nie potwierdzono dostępu ZeroTier do obecnego systemu.

## Dostęp przygotowany na Optiplex

Sekrety nie są w repo. Prywatny katalog na Optiplex:
`/home/codex-hil/.config/labinst/usb-tsmc2/` (0700):

- `access.token` (0600): token API;
- `server.crt`: publiczny certyfikat do weryfikacji TLS.

W panelu wklej zawartość `access.token` do pola tokenu. Hasło SSH nie jest tokenem API.
Token obejmuje surowe sterowanie przyrządem; nie loguj go ani nie umieszczaj w URL.
Na innej stacji pliki nie pojawią się automatycznie: pobierz certyfikat przez
uwierzytelnione SSH (`~/labinst-stage/server.crt`) i uzyskaj token z
`/etc/labinst/access.token` przez uprawnionego administratora. Dopasuj ścieżki klienta.
Nie wyłączaj weryfikacji TLS. SHA-256 certyfikatu:

```text
32:84:1E:7D:C2:03:3C:2C:13:4F:87:16:59:03:3B:4B:32:64:D0:BB:99:D7:FA:9E:91:AA:85:2C:4A:8E:DD:C9
```

Ważność: 2026-11-19–2027-11-19 UTC. SAN zawiera nazwę `USB-TSMC2.local` i IP
`192.168.2.10`. Po zmianie IP używaj nazwy mDNS; nowy adres numeryczny wymaga
aktualizacji certyfikatu. Serwer nasłuchuje na `0.0.0.0:8840`, więc zmiana DHCP
nie uniemożliwia startu usługi. Ta konfiguracja obejmuje wszystkie interfejsy IPv4.

## Sprawdzenie z następnego wątku

Z katalogu repozytorium na Optiplex:

```sh
python3 tools/usbtmc2/check_access.py
```

Skrypt używa [konfiguracji klienta](../../examples/usb-tsmc2-client.json), zakłada
obie poniższe blokady, weryfikuje model i serial przez Driver, odczytuje `OUTP1?`
i `OUTP2?`. Nie zmienia nastaw i nie włącza wyjść. Kod 75 oznacza zajętą blokadę.
Nie wywołuj go wewnątrz innego procesu już trzymającego te same blokady.

Wynik odbioru: poprawne IDN, CH1=`0`, CH2=`0` (OFF).
[Dowód odczytu](../../reports/usbtmc2-20261119/access-check.json).

## Rezerwacja wielokomendowej pracy

Wspólne blokady na Optiplex (flock, nonblocking, kolejność leksykograficzna):

1. `/home/codex-hil/.cache/instrument-mp750288-1944201.lock`
2. `/home/codex-hil/.cache/rpi-7379fa4619d5d5f0.lock`

Utrzymuj je przez identyfikację, cały eksperyment i przywrócenie nastaw. Blokada
przyrządu obowiązuje także przy alternatywnej drodze TCP/USB do tego samego serialu.
Blokady są kooperacyjne i lokalne; klient z innej maszyny musi uzgodnić dostęp z
właścicielem Optiplex. Bramka serializuje tylko pojedyncze transakcje, nie rezerwuje
sesji wielu komend. Przy zajętej bramce zwraca 503 przed wysłaniem nowej komendy.
Nie usuwaj locków ani nie przejmuj zajętej rezerwacji. Panelowe testy *IDN? również
mogą kolidować z eksperymentem; wykonuj je tylko poza sesją sterującą.

## Sterowanie i ograniczenia

Konfiguracja klienta celowo ma `commissioned:false`; samo przekazanie dostępu nie
upoważnia do włączenia wyjść w nieznanym układzie. Zanim użyjesz `Driver.apply`,
potwierdź obciążenie/okablowanie i limity eksperymentu. `apply` wyłącza oba kanały,
konfiguruje wybrany i sprawdza readback; `off` wyłącza oba. Przy bezpośrednim użyciu
Driver nie ma serwerowego watchdogu/lease. Skrypt odpowiada za cleanup i odczyt OFF.
Raw gateway nie egzekwuje `commissioned` ani limitów; plik klienta nie jest barierą
uprawnień. Nie wysyłaj *RST ani ON w celu samego sprawdzenia dostępu.

Wcześniejsze mapowanie z 2026-09-29 (MP CH1→TBS CH2, MP CH2→MSO CH2) jest historyczne.
Po przeniesieniu USB na Pi5 połączenia analogowe NIE zostały ponownie potwierdzone.
Nie używaj starej mapy do automatycznego włączania sygnałów.

## Wdrożenie i diagnostyka

Konfiguracja serwera: [usb-tsmc2-server.json](../../examples/usb-tsmc2-server.json).
Na Pi `/etc/labinst/config.json`; prawa USB tylko dla serialu 1944201, VID:PID
5345:1235, grupa labinst, tryb 0660. Kolejne przyrządy wymagają slotu i reguły udev.

```sh
ssh usbtsmc@USB-TSMC2.local 'systemctl status labinst --no-pager'
ssh usbtsmc@USB-TSMC2.local 'journalctl -u labinst -n 60 --no-pager'
```

HTTP 401 oznacza brak/błędny token. Obecność USB nie gwarantuje odpowiedzi SCPI.
Odłączenie nie powoduje automatycznego ponowienia; następna transakcja ponownie
wybiera przyrząd po serialu. Fizyczny hotplug Pi5 i restart zasilania NIE były testowane.

Wdrożony kod: commit `e098080` (gałąź feature/rpi-gateway), artefakt SHA-256
`d325dd9488a3eccb8ffac9ddf4c78971977206c76cd51b6afe193802a15d524a`.
[Pełny protokół wdrożonej bramki](https://github.com/codex-hil/lab-instruments/blob/e098080/docs/gateway/README.md).
README przekazania nie oznacza scalenia całej gałęzi bramki do main; klient używa
istniejącego kompatybilnego Transport/Driver z main.

72 testy buildu PASS; fizyczne HTTPS po IP i mDNS, weryfikacja TLS, 401 bez tokenu,
identyfikacja przez `/v1/identify` i `/v1/transaction` PASS. Wyjść nie włączano.
[Pełny raport instalacji](../../reports/usbtmc2-20261119/deployment-result.json).
