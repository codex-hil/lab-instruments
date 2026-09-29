# Instalacja na nowej maszynie / Raspberry Pi

## Wymagania

Raspberry Pi OS Lite Bookworm lub nowszy, Python 3.11+, Ethernet, USBTMC kernel module.
Stare Pi z 1–2 GB wystarczą do niewielkich transferów SCPI. Model Pi wyznacza zgodność
PoE HAT oraz współdzielenie przepustowości Ethernet/USB; należy ją sprawdzić osobno.
Na RPi 3 B+ potwierdzono identyfikację czterech przyrządów przez HTTPS (raport:
`reports/rpi-gateway-2026-09-29/README.md`). Testy fizycznego hotplugu podczas pracy
usługi i transferów binarnych pozostają otwarte. Nie ma wymogu 64-bitowego OS: używamy
standardowych ioctl z typami u32/u8, takich samych dla ARMv7 i ARM64.

## Budowanie

1. Zainstaluj Python 3.11+, git, openssl, usbutils oraz opcjonalnie nftables.
2. Skopiuj/klonuj repozytorium i wybierz konkretny commit/tag.
3. Uruchom `./scripts/bootstrap.sh` jako zwykły użytkownik. Wynik: `dist/labinst.pyz`.
4. Możesz zbudować artefakt na PC i skopiować go na Pi; potrzebuje tam tylko Pythona.

## Wybór roli

- Samo przekazywanie USB i WWW: `examples/rpi-gateway.json`.
- Limity źródeł/obciążeń: `examples/protected.json`, albo własna konfiguracja `control`
  z transportami `usb` dla lokalnych przyrządów.
- `examples/lab.json` jest inwentarzem obecnego stanowiska do identyfikacji, nie gotową
  konfiguracją bezpiecznego serwera sieciowego. Jego urządzenia są na obecnej wspólnej sieci.

## Instalacja usługi (po przeglądzie konfiguracji, jako root)

```sh
sudo ./scripts/install.sh examples/protected.json
sudo ./scripts/make-certificate.sh 192.168.10.20
```

Skrypt instaluje artefakt, użytkownika systemowego i unit systemd. Generuje losowy token.
Nie uruchamia usługi, nie zmienia NIC, sysctl, firewalla ani uprawnień USB.
Przy ponownym uruchomieniu zachowuje istniejącą konfigurację i token.
Certyfikat testowy self-signed ma SAN IP; klient musi zaufać dokładnie temu certyfikatowi
przez `--ca-file`. W docelowej sieci można użyć wewnętrznego CA. Nie wyłączaj weryfikacji TLS.

Root edytuje `/etc/labinst/config.json`, w szczególności:

- IP nasłuchu na NIC klienta; token i ścieżki certyfikatu;
- model, dokładny serial z `*IDN?`, adres i port każdego przyrządu;
- `source_ip` dla TCP, odpowiadający NIC instrumentów;
- limity i `lease_seconds`; początkowo `allow_output:false`, `commissioned:false`;
- usuwa wszystkie urządzenia nieobecne lub należące do innego stanowiska.

Pliki konfiguracji i kluczy: root:labinst 0640; katalog `/etc/labinst`: root:labinst 0750.
Zmienione limity obowiązują po restarcie usługi, który wykonuje OFF. Nie ma częściowego
hot-reloadu podczas aktywnego wyjścia.

## USB i cztery sloty

```sh
./dist/labinst.pyz usb-list
python3 scripts/udev-rule.py --vendor 0699 --product 0353 --serial 1544477
# Alternatywnie dla urządzenia bez unikalnego serialu:
python3 scripts/udev-rule.py --vendor 0699 --product 0353 --topology 1-1.2
```

Administrator zapisuje **sprawdzone** reguły do `/etc/udev/rules.d/70-labinst-usb.rules`,
wykonuje `udevadm control --reload-rules` i ponownie podłącza przyrządy.
Nie nadajemy praw do całego USB ani nie dodajemy użytkownika do szerokich grup.

`usb-list` pokazuje serial USB i `topology`, np. `1-1.2`. Serial USB może różnić się od
serialu SCPI! W konfiguracji `serial` przy profilu oznacza SCPI; `transport.serial`
lub `slots.usb1.serial` oznacza serial USB. Można dodać vendor/product_id do selektora.

Dla roli `usb-gateway` zastąp wszystkie placeholdery w `examples/rpi-gateway.json`.
Przykład przypisuje usb1/usb2 po serialu USB (urządzenie może zmienić port), a usb3/usb4
po topologii (slot podąża za fizycznym portem). Każdy slot może używać dowolnego z tych
selektorów. Jeśli podasz oba, muszą pasować jednocześnie. Puste selektory i selektory
wyłącznie vendor/product_id są odrzucane przy uruchomieniu.
Podłączenie czterech urządzeń naraz daje cztery wpisy; panel odświeża je co 5 sekund.
Każda transakcja na nowo rozwiązuje selektor: nie polega na numerze `/dev/usbtmcN`.
Odłączenie w trakcie transakcji daje błąd, bez automatycznego ponowienia. Kolejna próba
po powrocie urządzenia otwiera je na nowo. Duplikaty serialu są odrzucane, nie wybieramy
pierwszego pasującego urządzenia. Topologia może zmienić się po zmianie huba/OS — zweryfikuj.

Panel pokazuje karty slotów: `connected`, `disconnected` lub `ambiguous`, selektor,
deskryptory i bieżący węzeł USB oraz wynik ostatniej transakcji. Obecność w sysfs nie
potwierdza praw dostępu ani odpowiedzi SCPI. Ostatni błąd transakcji pozostaje widoczny
do udanej transakcji, także po ponownym podłączeniu. Brak dostępu do API usuwa stare
karty z panelu. Szczegóły JSON i pełna lista USB są dostępne pod „Inwentarz USB i pełny status”.
Panel pokazuje uprawnienia procesu do węzła (nie testuje otwarcia), czas ostatniej transakcji,
liczniki transakcji/błędów oraz ostatnie 40 transakcji. Historia nie zawiera komend ani
danych pomiarowych i jest zerowana przy restarcie usługi. Raport JSON nie zawiera tokenu.

Bramka serializuje wszystkie transakcje (prostsza ochrona także przed aliasami USB), więc
cztery urządzenia są obsługiwane kolejno. W trakcie transakcji nowe żądanie otrzymuje
HTTP 503 „gateway busy; no command sent”, zanim zostanie wysłana jakakolwiek komenda.
Status WWW pozostaje dostępny. Klient decyduje o kolejnej próbie; transport nie ponawia jej
automatycznie. Dla większej przepustowości można później wprowadzić blokady per tożsamość.
Nie odpytuje automatycznie `*IDN?` w tle — nie wtrąca komend w cudzy protokół. Model i serial
w panelu pochodzą z deskryptorów USB; aktywną identyfikację wykonuje klient jawnie
przyciskiem „Sprawdź *IDN?” lub „Sprawdź wszystkie”. Drugi przycisk odpytuje sloty kolejno.
Odpowiedź SCPI jest oznaczona datą ostatniego testu; nie jest dowodem bieżącej komunikacji.

### Test odbiorczy bramki na Raspberry Pi — częściowo wykonany

Testy automatyczne (`python3 -m unittest discover -s tests -v`) symulują enumerację USB,
odłączenie podczas odczytu i ponowne podłączenie pod innym numerem węzła. Nie zastępują
testów kernela, udev, zasilania USB ani czterech fizycznych przyrządów.

1. Zainstaluj usługę z `examples/rpi-gateway.json`, skonfiguruj TLS, token, selektory
   i reguły udev. Uruchom jako użytkownik `labinst`, zapisz PID usługi.
2. Podłącz cztery przyrządy. Sprawdź cztery karty oraz zgodność seriali/topologii z `usb-list`.
3. Przez istniejący transport `gateway` wykonaj jawne zapytanie identyfikacyjne każdego
   przyrządu i sprawdź odpowiedź. Sprawdź też odczyt binarny, jeśli przyrząd go obsługuje.
4. Odłącz jeden przyrząd w spoczynku i podczas odczytu. Panel ma wykryć brak urządzenia;
   przerwana transakcja ma zakończyć się błędem bez automatycznego ponowienia.
5. Podłącz ponownie, wymuszając zmianę numeracji `/dev/usbtmcN`. Powtórz zapytanie bez
   restartu Pi/usługi; potwierdź niezmieniony PID oraz działanie pozostałych trzech slotów.
6. Przenieś przyrząd wybrany po serialu do innego portu, a wybrany po topologii odłącz
   i podłącz do tego samego portu. Potwierdź oczekiwane przypisania i uprawnienia udev.
7. Zanotuj model Pi, OS/kernel, hub/zasilanie, deskryptory czterech przyrządów, commit,
   wyniki i czasy błędów. Do tego momentu zgodność sprzętowa pozostaje niepotwierdzona.


## Panel na RPI-USBTMC

Uruchomione stanowisko: `https://192.168.2.16:8840/`, usługa `labinst` (autostart systemd).
Konfiguracja stanowiska bez sekretów: `examples/rpi-usbtmc.json`. Sloty: `afg1062`,
`mp750288`, `mso2002b`, `tbs1022`; każdy używa serialu USB oraz VID:PID.

Certyfikat self-signed skopiuj z Pi przez uwierzytelnione SSH i dodaj do zaufanych
certyfikatów przeglądarki/systemu. Publiczna kopia do pobrania jest w
`/home/usbtmc/labinst-stage/server.crt`; klucz prywatny pozostaje w `/etc/labinst/`.
Token odczytaj przez SSH, a następnie wklej w panelu:

```sh
scp usbtmc@192.168.2.16:labinst-stage/server.crt ./rpi-usbtmc.crt
ssh -t usbtmc@192.168.2.16 'sudo cat /etc/labinst/access.token'
```

Token daje także dostęp do surowego transportu. Panel przechowuje go wyłącznie w pamięci
strony, nie w URL ani localStorage. Przycisk „Wyczyść token” usuwa go z formularza.

Jawna diagnostyka API: `POST /v1/identify`, body `{"slot":"tbs1022"}`, nagłówek
`Authorization: Bearer <token>`. Odpowiedź: `{"identity":"TEKTRONIX,..."}`.
Endpoint istnieje tylko w trybie `usb-gateway` i używa tego samego transportu/blokady
co `POST /v1/transaction`. Nie wykonuje resetów ani inicjalizacji drivera.

Przykład użycia istniejącego klienta Python (CA i token w lokalnych plikach):

```python
from labinstruments.transport import Transport

with Transport({"kind": "gateway", "url": "https://192.168.2.16:8840",
                "slot": "tbs1022", "token_file": "access.token",
                "ca_file": "rpi-usbtmc.crt"}) as io:
    print(io.query("*IDN?"))
```

Test przeglądarkowy: `scripts/gateway-browser-smoke.py --token-file <plik>` wymaga
osobnej instancji Firefox z Marionette na porcie 2832; domyślnie używa lokalnego fixture
na porcie 8841. Test wykonuje jawne identyfikacje — rzeczywista bramka musi być wolna.

## Dwa NIC i firewall

Przykładowo NIC klienta `192.168.10.20/24`, NIC przyrządów `192.168.50.1/24` bez gateway,
przyrządy `192.168.50.10–99`. Obecne adresy laboratorium nie są automatycznie przenoszone.

Przejrzyj `deploy/firewall.nft.example`, ustaw nazwy interfejsów, podsieć klientów i
rzeczywisty UID z `id -u labinst`. Najpierw `nft -c -f <plik>`, potem root ładuje reguły
i zapewnia ich odtworzenie po restarcie. Szablon nie zawiera `flush ruleset` i nie zastępuje
istniejącego firewalla, lecz wymaga integracji z nim. Nie otwiera SSH ani nie zmienia jego reguł.
Skopiuj `deploy/90-labinst-isolation.conf` do sysctl.d tylko po potwierdzeniu, że host nie
pełni innej funkcji routera. Sprawdź także IPv6 i ewentualne bridge/VPN.

Dopiero po sprawdzeniu izolacji:

```sh
sudo systemctl enable --now labinst
sudo journalctl -u labinst -f
```

## Odbiór stanowiska

- Potwierdź serial każdego źródła i brak alternatywnej drogi sieciowej/USB z klienta.
- Sprawdź stronę WWW oraz uwierzytelnianie; surowy endpoint musi zwracać 404 w `control`.
- Z `allow_output:false` sprawdź odrzucenie żądania ON i błędnych pól.
- Przy obciążeniu testowym/niezależnym mierniku sprawdź granice, readback, OFF,
  wygaśnięcie lease, odpięcie kabla, restart procesu i zachowanie po zasilaniu przyrządu.
- Zweryfikuj OVP/OCP/OPP i sprzętowe odcięcie właściwe dla eksperymentu.
- Dopiero root zatwierdza profil przez `commissioned:true` i `allow_output:true`.

## Aktualizacja

Zbuduj i przetestuj nowy commit jako zwykły użytkownik. Zatrzymaj usługę (OFF), wykonaj
`install.sh` ponownie, zachowując policy/token, uruchom usługę i zweryfikuj identyfikację.
Zachowaj poprzedni `.pyz` i jego hash do rollbacku. Nie aktualizuj w trakcie eksperymentu.
