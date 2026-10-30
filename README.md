> SD Wire update 2026-10-27: factory FT200X CBUS0 corrected with backup/readback;
> guarded HOST/DUT/HOST and full image write/readback physically PASS on ZC706.
> SPL/U-Boot/Linux, automatic DDR/dual PLL startup, SSH and external SFP PASS.
> [Workflow, limits and evidence](docs/sdwire-guarded.md). Cold power-cycle NOT_RUN.

# Lab instruments

Sterowniki Python, klient CLI, serwer sterowania z limitami administratora oraz bramka
USBTMC dla Raspberry Pi. Repozytorium samowystarczalne: Python **3.11+**, biblioteka
standardowa, bez pip i zewnętrznych zależności. Linux x86-64 / ARMv7 / ARM64 dla serwera;
USB wymaga linuksowego sterownika `usbtmc`. Windows nie jest obecnie wspierany.

**Wersja 0.1.1: działający fundament, nie certyfikowany system bezpieczeństwa.**
Identyfikacja i małosygnałowe próby aktywnych profili zostały sprawdzone na stanowisku;
[raport HIL](reports/hil-2026-09-25/README.md) rozróżnia PASS, próby częściowe i braki.
Pełny commissioning pod obciążeniem pozostaje wymagany. Przykłady blokują włączanie wyjść.
Nie wdrożono tych usług na bieżącym stanowisku ani nie zmieniono jego sieci.

## Zakres repozytorium i obecny sposób pracy

Obecnie skrypty pomiarowe korzystają **bezpośrednio z driverów**. LAN przyrządu,
Raspberry Pi z USBTMC i Waveshare z RS-232 są drogami transportu. Rozbudowę warstwy
rezerwacji i wirtualnych przyrządów odkładamy. Istniejący tryb `control` jest opcjonalnym
prototypem; nie jest wymagany do bezpośredniego użycia biblioteki.
Jeden skrypt steruje danym przyrządem naraz.

Wszystkie poniższe komponenty są w **tym jednym repozytorium**, nie w osobnych repo:

| Komponent | README / dokumentacja | Zawartość |
|---|---|---|
| Zigbee HIL plug | [CLI i rezerwacje](tools/zigbee-plug/README.md) | SLZB-06p7U + TS011F przez Zigbee2MQTT; ON/OFF, pomiary, rezerwacje wątków |
| MR8875 | [panel i driver](tools/mr8875/README.md) | MR8902 + MR8904, panel WWW, sesje CSV, dokumentacja komend i próby bez sygnałów |
| FCA3003 | [driver licznika Tektronix](docs/fca3003.md) | pomiary SCPI, kanały A/B/C; [pomiar 1 MHz na A/B PASS](reports/fca3003-2026-10-22/README.md) |
| Drivery Python | [README driverów](labinstruments/README.md) | modele, metody, jednostki, przykład bez serwera |
| Raspberry Pi i Waveshare | [README wdrożenia](deploy/README.md) | USBTMC, hotplug, TCP–RS-232, konfiguracja i ograniczenia |
| Profile urządzeń | [modele](docs/models.md) | zakres każdego drivera i protokoły przyrządów |
| Protokół bramki i serwera | [API](docs/protocol.md) | HTTPS, JSON, base64, autoryzacja |
| Budowanie i instalacja | [instrukcja](docs/deployment.md) | bootstrap, zipapp, systemd, udev |
| Próby sprzętowe | [raport HIL](reports/hil-2026-09-25/README.md) | wyniki, błędy, brakujące testy |

Kod driverów, transportów, usługi RPi, skrypty budowania, szablony konfiguracji i raport
HIL są wersjonowane. Lokalne jednorazowe skrypty eksperymentów i kopie panelu Waveshare
nie są częścią repo; nie ma jeszcze uniwersalnego skryptu automatycznej konfiguracji
Waveshare. Konfiguracja konkretnej bramki jest opisana w README wdrożenia.

## Kamery laboratoryjne LABCAM

[Wspólny punkt wejścia dla agentów: kamery, CLI i API](tools/labcam/README.md).
Sterownik i aktualny registry są utrzymywane w osobnym repozytorium
[labcam](https://github.com/codex-hil/labcam); nie kopiujemy drivera ani haseł.

## Nowa maszyna — budowanie offline

Na Debianie / Raspberry Pi OS Bookworm lub nowszym administrator instaluje raz:

```sh
sudo apt-get install python3 usbutils openssl nftables
```

Następnie zwykły użytkownik:

```sh
git clone https://github.com/codex-hil/lab-instruments.git
cd lab-instruments
# Dla odtworzenia konkretnego wydania: git checkout <commit-lub-tag>
./scripts/bootstrap.sh
./dist/labinst.pyz models
```

Budowanie uruchamia testy i generuje `dist/labinst.pyz` oraz `SHA256SUMS`.
To jeden przenośny plik Python zipapp, **nie natywny plik ELF**. Nie wymaga kompilatora
ani dostępu do internetu. Archiwum ma ustaloną kolejność, czas i uprawnienia wpisów;
ten sam kod daje identyczny SHA-256. System/Python nie są hermetycznie pinowane;
obsługę wersji interpretera sprawdza CI. Można też używać `python3 -m labinstruments`.

## Model + adres albo nazwa stanowiska

```sh
./dist/labinst.pyz identify --model psw800-1.44 --host 192.168.2.12
./dist/labinst.pyz identify --model mp750288 --host 192.168.2.200 --port 3000
./dist/labinst.pyz usb-list
./dist/labinst.pyz identify --model afg1062 --usb-serial 1544477
./dist/labinst.pyz identify --config examples/lab.json --device scope
./dist/labinst.pyz read --config examples/lab.json --device scope --operation frequency --channel 3
```

Porty domyślne wynikają z profilu, można je nadpisać. Dla 6487 terminator to CR,
a dla pozostałych LF. `examples/lab.json` zawiera adresy i tożsamości naszego laboratorium.
Przykład B&K jest oddzielny: dzieli serwer szeregowy z 6487, lecz fizycznie tylko
jeden z nich może być aktualnie podłączony. Nie zgadujemy brakujących modeli TDS1000/2000.

Stanowisko nazywa się np. `supply`, a transport może być `tcp`, `usb` lub
`gateway` (HTTPS + jawny identyfikator gniazda). **Brak automatycznego ponawiania zapisów
lub przełączania transportu po błędzie**: nie wiadomo wtedy, czy komenda już się wykonała.
Operator wybiera fallback i ponownie sprawdza identyfikację.

## Chronione sterowanie

Klient ma dostęp wyłącznie do HTTPS API serwera. Przyrządy są w odrębnej sieci za drugą
kartą. Konfigurację, limity, listę urządzeń i token kontroluje root.
Pełny projekt: [architektura](docs/architecture.md), [wdrożenie RPi](docs/deployment.md),
[profile i zakres wsparcia](docs/models.md), [protokół](docs/protocol.md).

```sh
./dist/labinst.pyz client --url https://192.168.10.20:8840 \
  --ca-file server.crt --token-file operator.token \
  --device supply --action apply \
  --args '{"channel":1,"voltage":5,"current":0.1,"enable":true}'
```

W przykładach to żądanie zostanie **odrzucone**, dopóki administrator nie wykona
commissioningu i nie ustawi `commissioned: true` oraz `limits.allow_output: true`.
Włączenie dostaje dzierżawę (domyślnie 10 s); klient odnawia ją akcją `renew`, np. co 3 s.
Brak odnowienia powoduje próbę OFF. To programowy watchdog, nie sprzętowy interlock.
Akcja `off` wyłącza wszystkie kanały danego przyrządu. `apply` też zaczyna od OFF wszystkich
kanałów; v0.1 celowo dopuszcza **jeden aktywny kanał na przyrząd**, także NGP814.

Panel WWW pod `/` pokazuje status; token wpisuje się w przeglądarce, nie jest przechowywany
w localStorage. Panel nie oferuje omijającego limity terminala SCPI.

## Bramka USB

Tryb `usb-gateway` obsługuje hotplug, serial/topologię portu, opis USB, status i binarne
wiadomości z EOM. Nie rozpoznaje modelu, nie interpretuje SCPI i **nie egzekwuje limitów**.
Dlatego należy umieścić go w sieci zaufanej. Nie udostępniaj go klientom mającym ograniczony
zakres sterowania. Alternatywnie uruchom na RPi bezpośrednio tryb `control` z transportem
USB — wtedy limity egzekwowane są przy urządzeniu.

Zamiast czterech niejednoznacznych strumieni TCP używamy jednego HTTPS i jawnych slotów
`usb1`..`usb4`. Operacja podaje osobno bajty i informację, czy oczekuje odpowiedzi.
To umożliwia przekazywanie binarnych bloków bez heurystyki „komenda zawiera znak ?”.
Adapter Python `Transport(kind='gateway')` ukrywa ten szczegół. **To nie USB/IP, VXI-11,
HiSLIP ani gotowy VISA socket**; aplikacja producenta nie zobaczy automatycznie zdalnego USB.

## Weryfikacja

```sh
python3 -m unittest discover -s tests -v
python3 scripts/hil-identify.py examples/lab.json
```

Druga komenda dotyka sprzętu, ale wysyła tylko `*IDN?`. Nie resetuje urządzeń ani nie
włącza źródeł. Raport rzeczywistego testu: [HIL](docs/hil-identification.json).
Testy automatyczne sterowania i awarii pracują na emulatorach; wykonane dodatkowo
próby aktywne na urządzeniach opisuje [raport HIL](reports/hil-2026-09-25/README.md).

Przykład skryptu klienta: [power_test.py](examples/power_test.py) (uruchamia źródło,
wyłącznie po commissioningu). Import biblioteki z repo: `from labinstruments.client import Client`.
Sprawdzenie odtwarzalności commitowanego źródła: `./scripts/replay.sh HEAD`.
Szczegółowy zakres testów i brakujących prób sprzętowych: [validation](docs/validation.md).

Bibliotekę można importować również bez instalacji pakietu, prosto z artefaktu:

```sh
PYTHONPATH=dist/labinst.pyz python3 examples/power_test.py --help
```

## Removable Storage HIL

SDWire ma umożliwiać agentowi aktualizowanie SD/microSD bez wyjmowania karty z DUT:
build → HOST → podmiana BOOT.BIN/image.ub → sync/unmount → OFF → TARGET → reset →
UART/boot/health → PASS/FAIL. To kolejny zasób `labinstruments`, z ogólnym API
`RemovableStorage`, backendami i lockingiem całej transakcji; workflow nie zależy
od SDWire ani konkretnej platformy Zynq/RPi/FPGA.

**TESTED / SIMULATED:** mock, CLI, streaming .img/.gz/.xz, identity checks,
recovery, locking i boot workflow z pełnym UART artifact. **REQUIRES HARDWARE:**
dwa zakupione SDWire i realny Zynq. Legacy SDWire nie udostępnia trwałego OFF:
backend realny wykrywa skonfigurowane i fabryczne urządzenia (FT200X),
czyta metadane/status, ale blokuje przełączanie/zapis
z `OFF_UNSUPPORTED`. Wymagany dodatkowy, kwalifikowany mechanizm izolacji.

```sh
./scripts/bootstrap-storage.sh
export HIL_STORAGE_CONFIG="$PWD/examples/storage/mock.json"
local/storage-tools/bin/hil-storage --json list
local/storage-tools/bin/hil-storage zynq_dev status --json
local/storage-tools/bin/hil-storage zynq_dev host --json
local/storage-tools/bin/hil-storage zynq_dev flash image.img.xz --dry-run --json
local/storage-tools/bin/hil-storage zynq_dev off --json
```

Aliasy/USB seriale: [mock config](examples/storage/mock.json),
[DUT config](examples/storage/zynq.json). Szczegóły API, CLI, Nix, fail-closed,
klasyfikacji błędów i ograniczeń: [docs/sdwire.md](docs/sdwire.md).
Pierwsze podłączenie i automatyczny raport:
[docs/sdwire-bringup.md](docs/sdwire-bringup.md).

Pierwszy fizyczny egzemplarz: **DP04I355**, factory `0403:6015`, czytnik USB2640
`0424:4050`, karta 15716057088 bajtów. Topology identity PASS; ownership pozostaje
unknown, bez automatycznego programowania EEPROM-u. Szczegóły wykonanych prób i
ograniczeń: [hardware-2026-10-13](reports/storage/hardware-2026-10-13/README.md).
Aktualne testy software: [121 PASS](reports/storage/software-2026-10-13/README.md).

Po nadaniu tymczasowych ACL: [realny SDWire PASS_READ_ONLY](reports/storage/hardware-2026-10-13-read-pass/README.md)
— odczyt rejestru USB i dwa zgodne odczyty 1MiB karty. Bez zapisów/przełączeń.
Na aktualnej bazie main: [83 testy PASS](reports/storage/software-2026-10-13-main/README.md),
w tym 41 storage; wcześniejsze raporty dotyczą wcześniejszej bazy feature.

### Tektronix DPO4104

DPO4104 C022184: profil `dpo4104`, LAN `192.168.2.10:4000`, identyfikacja i
odczyty frequency/Vpp CH1–4. [Instrukcja dla kolejnych wątków, blokada dostępu,
konfiguracja i zakres walidacji](docs/dpo4104.md).

Konfiguracja DPO4104 obsługuje DHCP: weryfikuje wskazówkę IP i w razie potrzeby
wyszukuje model/serial C022184 w `192.168.2.0/24`. Użyj `examples/dpo4104.json`;
nie trzeba ręcznie aktualizować adresu po zmianie dzierżawy.
