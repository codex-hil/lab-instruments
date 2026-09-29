# Raspberry Pi USBTMC → LAN: oprogramowanie i protokoły

Bramka udostępnia przyrządy USBTMC przez jedno API HTTPS. Panel WWW pokazuje stan
USB, uprawnienia procesu, ostatnią identyfikację, czasy i błędy transakcji; pozwala
jawnie wykonać `*IDN?` i pobrać raport JSON. Całość jest w tym repozytorium:
Python 3.11+, biblioteka standardowa, Linux z kernelowym sterownikiem `usbtmc`.

## Warstwy i pliki

```text
Driver / skrypt klienta
  → Transport(kind="gateway")
  → HTTPS + JSON + base64, TCP 8840
  → Gateway / Transport(kind="usb") na Raspberry Pi
  → kernel usbtmc, /dev/usbtmcN, USBTMC EOM
  → SCPI / odpowiedzi tekstowe lub binarne przyrządu
```

| Element | Implementacja |
|---|---|
| Wspólne drivery i profil TBS1022 | [drivers.py](../../labinstruments/drivers.py) |
| TCP, USBTMC, klient HTTPS | [transport.py](../../labinstruments/transport.py) |
| API, autoryzacja, blokada, historia | [service.py](../../labinstruments/service.py) |
| Panel WWW bez zewnętrznych zasobów | [gateway_dashboard.py](../../labinstruments/gateway_dashboard.py) |
| CLI | [__main__.py](../../labinstruments/__main__.py) |
| Instalator, certyfikat, reguły USB | [scripts](../../scripts) |
| Systemd i szablony wdrożenia | [deploy](../../deploy) |
| Testy bramki | [test_gateway.py](../../tests/test_gateway.py) |

To protokół aplikacyjny: nie USB/IP, VXI-11, HiSLIP ani surowy VISA socket. Bramka
przekazuje bajty; drivery pozostają wspólne dla połączeń lokalnych i zdalnych.
Tryb `usb-gateway` nie narzuca limitów źródeł ani watchdogu wyjść. Opcjonalny tryb
`control` ma odrębny [protokół operacji z limitami](../protocol.md).

## Budowanie i uruchomienie

```sh
git clone --branch feature/rpi-gateway https://github.com/codex-hil/lab-instruments.git
cd lab-instruments
./scripts/bootstrap.sh
./dist/labinst.pyz usb-list
```

Build uruchamia testy i tworzy `dist/labinst.pyz` oraz `dist/SHA256SUMS`. Zipapp można
zbudować na PC i przenieść na Pi. Artefakty są generowane ze źródeł, nie commitowane.
Odtworzenie konkretnego commita: `./scripts/replay.sh <commit>`.

Konfiguracja ogólna: [rpi-gateway.json](../../examples/rpi-gateway.json).
Konfiguracja sprawdzonego stanowiska: [rpi-usbtmc.json](../../examples/rpi-usbtmc.json).
Po ustawieniu IP, selektorów USB, certyfikatu i tokenu administrator instaluje usługę,
reguły udev i uruchamia systemd według [instrukcji wdrożenia](../deployment.md).
Instalator zachowuje istniejącą konfigurację i token; nie uruchamia sam usługi.

Na stanowisku działa `RPI-USBTMC`, Raspberry Pi 3 B+, `https://192.168.2.16:8840/`.
Certyfikat pobiera się przez SSH i dodaje do zaufanych; token jest w
`/etc/labinst/access.token`. Tokeny i klucze prywatne nie są częścią repozytorium.

## HTTPS i uwierzytelnianie

- TLS minimum 1.2; klient weryfikuje certyfikat serwera. Dla certyfikatu stanowiska
  użyj `ca_file` w Pythonie / `--cacert` w curl. Nie używaj `curl -k`.
- Wszystkie endpointy `/v1/*` wymagają `Authorization: Bearer <token>`.
- `GET /` zwraca publiczny HTML; dane przyrządów pobierane są dopiero po autoryzacji.
- Żądania POST: `Content-Type: application/json`, JSON UTF-8, jawny `Content-Length`.
  Serwer nie dekoduje requestów HTTP chunked.
- Odpowiedzi JSON, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`.
- Panel przechowuje token tylko w pamięci strony; nie w URL ani localStorage.

| Metoda i ścieżka | Rola | Wynik |
|---|---|---|
| `GET /` | dowolna | panel HTML |
| `GET /v1/status` | gateway | obiekt `usb`, `slots`, `events`, `gateway` |
| `POST /v1/identify` | gateway | `{"identity":"..."}` |
| `POST /v1/transaction` | gateway | `{"data":"...base64..."}` |
| `POST /v1/control` | control | wynik operacji drivera; w gateway HTTP 404 |

Przykłady curl zakładają chroniony lokalny plik `operator.headers` z linią
`Authorization: Bearer <token>` oraz plik `rpi-usbtmc.crt`. Nie dodawaj pliku
nagłówków do repo. Panel jest prostszą alternatywą do ręcznego przygotowania nagłówka.

```sh
curl --cacert rpi-usbtmc.crt --header @operator.headers \
  https://192.168.2.16:8840/v1/status
```

## GET /v1/status

Przykład skrócony do jednego slotu (czas w sekundach Unix):

```json
{
  "usb": [{"path":"/dev/usbtmc3","topology":"1-1.1.3","serial":"C012657","vendor":"0699","product_id":"03ae","model":"Tektronix TBS1022"}],
  "slots": {
    "tbs1022": {
      "label":"Tektronix TBS1022",
      "connected":true,
      "state":"connected",
      "accessible":true,
      "selectors":{"serial":"C012657","vendor":"0699","product_id":"03ae"},
      "matches":[{"path":"/dev/usbtmc3","topology":"1-1.1.3","serial":"C012657","vendor":"0699","product_id":"03ae","model":"Tektronix TBS1022"}],
      "status":{"transactions":1,"failures":0,"duration_ms":71.5,"error":null,"last_ok":1790694380.0,"identity":"TEKTRONIX,TBS 1022,C012657,CF:91.1CT FV:v26.01","identified_at":1790694380.0}
    }
  },
  "events": [],
  "gateway":{"hostname":"RPI-USBTMC","uptime_seconds":27,"active_slot":null,"serialization":"global","mode":"usb-gateway"}
}
```

- `usb`: aktualna enumeracja węzłów USBTMC, także nieprzypisanych do slotów.
- `state`: `connected` = dokładnie jedno dopasowanie, `disconnected` = zero,
  `ambiguous` = więcej niż jedno. `matches` zawiera wszystkie dopasowania.
- `accessible`: proces ma prawa odczytu i zapisu do jednoznacznie wybranego węzła.
  To nie próba otwarcia ani dowód komunikacji SCPI.
- `status` jest pusty przed pierwszą transakcją. Zawiera ostatni czas trwania w ms,
  liczbę transakcji i błędów, `last_ok`, opcjonalnie `last_error` oraz bieżący `error`.
  Udana transakcja zeruje `error`, ale zachowuje wcześniejszy znacznik `last_error`.
- `identity` i `identified_at` pochodzą z ostatniej udanej operacji `/v1/identify`.
  Mogą być historyczne po odłączeniu. Zwykły raw `*IDN?` nie aktualizuje tych pól.
- `events`: do 40 ostatnich transakcji, najnowsza pierwsza; pola `time`, `slot`,
  `operation` (`identify`/`transaction`), `ok`, `duration_ms`, `tx_bytes`, `rx_bytes`,
  `error`. Bez treści komend i odpowiedzi. Historia i liczniki są w RAM i znikają
  po restarcie. Odrzucone żądania walidacji i zajętej bramki nie są transakcjami USB.
- `active_slot` wskazuje aktualną transakcję lub `null`. Status nie czeka na jej koniec.

Odświeżanie panelu co 5 s nie wysyła komend do przyrządów. Status nie jest gwarancją
aktualnego stanu fizycznych wyjść, poprawności kalibracji ani połączeń kablowych.

## POST /v1/identify

```sh
curl --cacert rpi-usbtmc.crt --header @operator.headers \
  --header 'Content-Type: application/json' \
  --data '{"slot":"tbs1022"}' https://192.168.2.16:8840/v1/identify
```

Body musi zawierać dokładnie pole `slot` (string istniejącego slotu). Bramka wysyła
`*IDN?` z `write_termination` slotu (domyślnie LF). Zwraca tekst ASCII bez zewnętrznych
białych znaków; nietekstowe bajty zastępuje znakiem zastępczym. W statusie zachowuje
maksymalnie 4096 bajtów identyfikacji. To jawne zapytanie, nie inicjalizacja drivera,
reset ani potwierdzenie zgodności modelu. Model/serial sprawdza `Driver.identify()`.
Przycisk „Sprawdź wszystkie” wykonuje te zapytania kolejno.

## POST /v1/transaction

```json
{"slot":"tbs1022","data":"KklETj8K","reply":true}
```

Pola są obowiązkowe i żadne dodatkowe nie są akceptowane:

| Pole | Typ | Znaczenie |
|---|---|---|
| `slot` | string | nazwa z konfiguracji, nie ścieżka `/dev` |
| `data` | string base64 | dokładne bajty do zapisu; powyżej `*IDN?\n` |
| `reply` | boolean | `true`: zapisz i odczytaj jedną wiadomość; `false`: tylko zapisz |

Odpowiedź HTTP 200: `{"data":"..."}` z bajtami odpowiedzi base64. Przy `reply:false`
wynik to `{"data":""}`; oznacza ukończenie zapisu, nie odczyt kontrolny nastawy.

Bramka nie dopisuje LF, nie interpretuje SCPI i nie zgaduje obecności odpowiedzi po
znaku `?`. Terminator jest częścią `data`. Użycie `reply:false` dla zapytania może
pozostawić nieodczytaną odpowiedź; użycie `reply:true` dla komendy bez odpowiedzi
może zakończyć się błędem/timeoutem. Klient musi znać protokół konkretnego przyrządu.

## USBTMC, framing binarny i hotplug

Wybór: `serial` USB lub `topology` (np. `1-1.1.3`), opcjonalnie `vendor` i
`product_id`. Wszystkie podane pola muszą pasować; porównania są dokładne, VID/PID
z sysfs są zapisane małymi literami. Serial USB może różnić się od SCPI.
`serial` śledzi przyrząd, `topology` śledzi port na konkretnej płytce/hubie.
Sam VID/PID, pusty serial ani `/dev/usbtmcN` nie są stabilnym selektorem.

Każda transakcja od nowa enumeruje USB, otwiera wybrany węzeł, zakłada `flock`,
ustawia timeout USB, wykonuje zapis/odczyt i zamyka deskryptor. Brak lub więcej niż
jedno dopasowanie to błąd. Ponowne podłączenie może zmienić numer węzła bez zmiany
slotu. Reguły udev nadają prawa przy każdym podłączeniu; konfiguracja nie jest
automatycznie przeładowywana, a nowy niepasujący serial wymaga jej edycji.

Koniec odpowiedzi wyznacza bit EOM z ioctl `USBTMC_IOCTL_MSG_IN_ATTR`, nie krótki
odczyt, LF ani zawartość payloadu. Bajty binarne, NUL i LF wewnątrz danych są zachowane.
Blok IEEE 488.2 (`#<liczba cyfr><długość><payload>`) nie jest dekodowany przez bramkę.
Parser danych należy do klienta/drivera. Bezpośredni transport TCP ma odrębny parser
bloków definite-length z terminatorem i odrzuca `#0`; USB korzysta z EOM.

Odłączenie podczas operacji kończy się błędem, bez powtórzenia komendy. Nowa jawna
transakcja po powrocie urządzenia ponownie rozwiązuje selektor. Nie ma resetu,
przywracania nastaw ani automatycznego ON. Hotplug jest objęty testami symulowanymi;
odłączenie podczas pracy usługi na fizycznym stanowisku nadal wymaga testu.

## Współbieżność, limity i błędy

Jedna wspólna blokada obejmuje zapis i odczyt; chroni też dwa sloty wskazujące ten sam
przyrząd. Gdy trwa transakcja, następna dostaje HTTP 503 `gateway busy; no command sent`
przed zapisem. Nie ma kolejki ani rezerwacji wielokomendowej sesji. Nie uruchamiaj dwóch
skryptów konfiguracyjnych tego samego przyrządu; także test WWW *IDN? wykonuj między pomiarami.
Atomowość blokady nie oznacza transakcyjnego rollbacku stanu przyrządu.

| Parametr | Wartość |
|---|---|
| Dane USB w jednym żądaniu/odpowiedzi | 1 bajt–16 MiB dla zapisu, maks. 16 MiB odczytu; slot może obniżyć `max_message` |
| Body HTTP | maks. 24 MiB JSON, łącznie z base64 |
| `timeout` USB | domyślnie 4 s, dozwolone >0 i ≤30 s |
| `delay` po zapisie | domyślnie 0.05 s |
| Timeout klienta Python gateway | `timeout + 2` s; konfiguracja klienta niezależna od slotu Pi |
| Obsługiwane jednocześnie połączenia HTTP | do 16; ponad limit połączenie zamykane |

Timeout USB dotyczy operacji kernela, nie całkowitego czasu wieloczęściowej odpowiedzi.
Klient może więc stracić odpowiedź, gdy serwer jeszcze pracuje. Brak odpowiedzi HTTP
nie oznacza niewykonania komendy. Program nie ponawia transakcji automatycznie.

| HTTP | Przykładowa przyczyna |
|---|---|
| 200 | poprawnie zakończona operacja |
| 400 | niepoprawny JSON/pola, slot, base64, długość; także `ValueError` w transporcie |
| 401 | brak tokenu lub błędny token |
| 404 | nieznana ścieżka lub endpoint niedostępny w danym trybie |
| 503 | zajęta bramka, brak/niejednoznaczny USB, brak uprawnień, timeout lub inny błąd I/O |

Body błędu: `{"error":"opis"}`. HTTP 400/503 nie stanowi ogólnej gwarancji, że nic
nie zapisano — błąd odczytu/rozmiaru odpowiedzi może wystąpić już po zapisie.
Jawne `gateway busy; no command sent` jest wyjątkiem: nic nie zostało wysłane.

## Klient Python i drivery

```python
from labinstruments.transport import Transport
from labinstruments.drivers import Driver

with Transport({
    "kind": "gateway", "url": "https://192.168.2.16:8840",
    "slot": "tbs1022", "token_file": "operator.token",
    "ca_file": "rpi-usbtmc.crt", "timeout": 4,
}) as io:
    scope = Driver(io, "tbs1022", serial="C012657")
    print(scope.identify())
    # Wybiera pomiar immediate; kanał musi być wyświetlany i mieć poprawną akwizycję.
    print(scope.read("frequency", channel=1))
    print(scope.read("vpp", channel=1))
```

`io.query()` i `io.write()` dopisują skonfigurowany terminator (domyślnie LF).
`io.transaction(b"...", expect_reply=True)` zwraca surowe bajty. Dla danych binarnych
używaj `transaction`, nie tekstowego `query`. Przykład wymaga checkoutu na PYTHONPATH
lub `PYTHONPATH=dist/labinst.pyz`; nie wymaga instalacji pip.

## Potwierdzone stanowisko i dalsze testy

Cztery USBTMC, HTTPS, identyfikacja i klient Python sprawdzone na RPi 3 B+:
[raport wdrożenia](../../reports/rpi-gateway-2026-09-29/README.md).
Aktywne pomiary przez bramkę potwierdziły następujące kable:

| Generator / wyjście | Oscyloskop / wejście |
|---|---|
| AFG1062 CH1 | TBS1022 CH1 |
| AFG1062 CH2 | MSO2002B CH1 |
| MP750288 CH1 | TBS1022 CH2 |
| MP750288 CH2 | MSO2002B CH2 |

[Raport mapowania](../../reports/rpi-wiring-2026-09-29/README.md) zawiera dwie
częstotliwości potwierdzające każdą trasę oraz kontrolę przywrócenia nastaw/OFF.
Pozostają testy fizycznego hotplugu działającej usługi, binarnych przebiegów przez Pi,
długotrwałego obciążenia i autostartu po ponownym uruchomieniu Pi.

## Testy bez sprzętu i test panelu

`./scripts/bootstrap.sh` uruchamia unittest i buduje artefakt bez dostępu do przyrządów.
Do interaktywnego obejrzenia panelu z zapisanymi danymi służy loopback-only fixture:

```sh
mkdir -p local
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > local/fixture.token
python3 scripts/gateway-browser-fixture.py --token-file local/fixture.token
```

Otwórz `http://127.0.0.1:8841/` i wklej token testowy. Fixture nie otwiera USB;
`*IDN?` zwraca zapisane odpowiedzi. Opcjonalny
[gateway-browser-smoke.py](../../scripts/gateway-browser-smoke.py) sprawdza karty,
przyciski, układ mobilny i autoryzację. Wymaga osobnej instancji Firefox uruchomionej
z `--marionette` i preferencją `marionette.port=2832`, po czym:

```sh
python3 scripts/gateway-browser-smoke.py --token-file local/fixture.token
```

Nie używaj tokenu produkcyjnego do testów fixture. Test przeglądarkowy wysyła `*IDN?`;
przekierowanie go na fizyczną bramkę wymaga wolnego stanowiska.
