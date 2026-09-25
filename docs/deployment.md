# Instalacja na nowej maszynie / Raspberry Pi

## Wymagania

Raspberry Pi OS Lite Bookworm lub nowszy, Python 3.11+, Ethernet, USBTMC kernel module.
Stare Pi z 1–2 GB wystarczą do niewielkich transferów SCPI. Model Pi wyznacza zgodność
PoE HAT oraz współdzielenie przepustowości Ethernet/USB; należy ją sprawdzić osobno.
Nie wykonano jeszcze testu na fizycznym RPi. Nie ma wymogu 64-bitowego OS: używamy
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
```

Administrator zapisuje **sprawdzone** reguły do `/etc/udev/rules.d/70-labinst-usb.rules`,
wykonuje `udevadm control --reload-rules` i ponownie podłącza przyrządy.
Nie nadajemy praw do całego USB ani nie dodajemy użytkownika do szerokich grup.

`usb-list` pokazuje serial USB i `topology`, np. `1-1.2`. Serial USB może różnić się od
serialu SCPI! W konfiguracji `serial` przy profilu oznacza SCPI; `transport.serial`
lub `slots.usb1.serial` oznacza serial USB. Można dodać vendor/product_id do selektora.

Dla role `usb-gateway` wpisz cztery faktyczne topologie z danej płytki zamiast placeholderów.
Podłączenie czterech urządzeń naraz daje cztery wpisy; panel odświeża je co 5 sekund.
Każda transakcja na nowo rozwiązuje selektor: nie polega na numerze `/dev/usbtmcN`.
Odłączenie w trakcie transakcji daje błąd, bez automatycznego ponowienia. Kolejna próba
po powrocie urządzenia otwiera je na nowo. Duplikaty serialu są odrzucane, nie wybieramy
pierwszego pasującego urządzenia. Topologia może zmienić się po zmianie huba/OS — zweryfikuj.

Bramka serializuje wszystkie transakcje (prostsza ochrona także przed aliasami USB), więc
cztery urządzenia są obsługiwane, ale długie transfery blokują pozostałe. Jest to świadomy
kompromis v0.1; dla większej przepustowości można później wprowadzić kolejki per tożsamość.
Nie odpytuje automatycznie `*IDN?` w tle — nie wtrąca komend w cudzy protokół. Model i serial
w panelu pochodzą z deskryptorów USB; aktywną identyfikację wykonuje klient jawnie.

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
