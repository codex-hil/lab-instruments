> Update 2026-10-27: a separate [guarded HOST/DUT API](sdwire-guarded.md)
> supports the actual v1 topology without requiring OFF. It requires verified,
> continuously held DUT stop and mandatory readback. The historical isolated
> API below remains read-only; new physical commissioning is pending USB access.

# Removable Storage HIL / SDWire

Status: **TESTED** oznacza test oprogramowania; **SIMULATED** oznacza model
karty/DUT, nigdy pomiar fizyczny; **REQUIRES HARDWARE** oznacza brak kwalifikacji
na kupionych dwóch egzemplarzach. Żaden realny SDWire ani dysk nie był zapisany.

## Najważniejszy wynik researchu

**Legacy 3mdeb SDWire v1.4 nie zapewnia sterowalnego, trwałego OFF.** Nie możemy
spełnić wymaganej sekwencji HOST → OFF → DUT samym software. Backend celowo
odmawia wszystkich zmian własności i zapisów (`OFF_UNSUPPORTED`, exit 5).
Nie utożsamiamy odpięcia sterownika USB, usunięcia /dev/sdX, odmontowania,
wyłączenia zasilania DUT ani ustawienia CBUS jako wejścia z izolacją karty.

Schemat publikowany przez 3mdeb pokazuje FT200XD CBUS0 → SOCKET_SEL, wspólny
wybór obu banków TS3A27518E i EN multipleksera podłączony do GND. Zasilanie karty
wybierają Q3/Q4, także sterowane tym samym sygnałem przez inwerter. USB2640 jest
czytnikiem i hubem USB. Nie ma niezależnej linii programowego odłączenia
wszystkich sygnałów i zasilania SD. Schemat jest v1.4; zgodność zakupionych
rewizji trzeba sprawdzić na sprzęcie.
[Specyfikacja 3mdeb](https://docs.dasharo.com/transparent-validation/sd-wire/specification/),
[schemat](https://docs.dasharo.com/images/SD-wire_scheme-1.png).

Break-before-make wewnątrz układu analogowego i trwały stan OFF to różne wymagania.
Nie uznajemy nanosekundowej przerwy muxa za wymagane OFF z oczekiwaniem.
Możliwa dalsza droga: dodatkowy, sprzętowo kwalifikowany interlock odłączający
sygnały i zasilanie karty albo mux z rzeczywistym OFF. To wymaga osobnego backendu,
readbacku izolacji i integracji z zatrzymaniem DUT. Nie ma flagi omijającej tę blokadę.

## Zweryfikowane źródła, nie tylko README

Analiza 2026-10-08/09:

| Źródło | Rewizja / ustalenie |
|---|---|
| [3mdeb/sd-mux](https://github.com/3mdeb/sd-mux/tree/9dd189d973da64e033a0c5c2adb3d94b23153d94) | `9dd189d973da64e033a0c5c2adb3d94b23153d94`; przypięty build C++/libftdi/popt |
| [main.cpp](https://github.com/3mdeb/sd-mux/blob/9dd189d973da64e033a0c5c2adb3d94b23153d94/src/main.cpp) | `selectTarget`: CBUS bitmode 0x20, mask 0xF0 DUT / 0xF1 HOST; tylko jeden bit wyboru |
| ten sam kod: `showStatus`, `prepareDevice` | `ftdi_read_pins`, bit 0: TS=host, DUT=target; dla SDWire pomija zwykły bitbang |
| ten sam kod: `openDevice`, `setSerial` | wybór po VID/PID/serial; odczyt EEPROM/product; `setSerial` przebudowuje EEPROM i VID/PID — NIE używamy do aliasów |
| [3mdeb/SDWire](https://github.com/3mdeb/SDWire) | repo opisywane jako schematy, ale dostępne drzewo zawiera również kontroler; sam opis repo nie jest dowodem schematu |
| [Badger-Embedded/sdwire-cli](https://github.com/Badger-Embedded/sdwire-cli/tree/a700a21e63281187a607a30cba0b38420da16559) | `a700a21e63281187a607a30cba0b38420da16559`; `backend/utils.py` jawnie odrzuca OFF dla legacy/SDWireC/SDWire3, mimo komendy w README |
| [użycie 3mdeb](https://docs.dasharo.com/transparent-validation/sd-wire/usage-validation/) | `sd-mux-ctrl --device-serial=... --ts/--dut/--status`; nie oznacza kwalifikacji naszego stanowiska |

`sd-mux-ctrl` nie jest firmware SDWire: steruje FTDI przez USB/libftdi. SDWire nie
ma UART do tego protokołu. Kontroler po konfiguracji ma VID/PID `04e8:6001`, product
`sd-wire`; fabryczny FTDI może mieć `0403:6001`. Sam VID/PID FTDI nie wystarcza:
wymagamy także dokładnego product i jednego urządzenia o zadanym serialu.
Nie sterujemy po indeksie enumeracji. Zmienny /dev/sdX jest wyłącznie wynikiem
bieżącej identyfikacji, nigdy konfiguracją celu zapisu.

Kontroler i czytnik to różne urządzenia USB. Serial FTDI nie jest serialem
czytnika. Backend sprawdza konkretnego czytnika w tym samym fizycznym hubie,
VID/PID, serial, nadrzędny hub USB2640 `0424:2640`, przypiętą topologię,
by-id, major:minor, removable=1, pojemność
i jednoznaczny cały dysk. Wymagany commissioning czytnika; nie wybieramy pierwszego
mass-storage znalezionego pod dowolnym hubem. Brak serialu/by-id lub sprzeczna
identyfikacja powoduje odmowę. Sprawdzenie reader association jest **REQUIRES HARDWARE**.

### USB, restart hosta, karty i prędkość

Kod nie implementuje bezpiecznej polityki po restarcie hosta/USB ani watchdogu
izolacji. Stan GPIO po resetach, zaniku VBUS, hotplug i zasilaniu tylko przez DUT
nie jest gwarantowany tym API. Nie zakładamy OFF ani zachowania ostatniego wyboru;
należy odczytać stan i zweryfikować elektrycznie. USB-off może pozostawić kartę
zasilaną przez DUT. SIGKILL i awaria hosta nie wykonają software cleanup.

Nie deklarujemy uniwersalnej zgodności SDXC/UHS/1.8 V ani granicy pojemności.
[FAQ producenta](https://docs.dasharo.com/transparent-validation/sd-wire/faq/)
potwierdza test karty microSDHC 32 GB na Orange Pi Zero i podaje zmierzone
12–21 MB/s. To wyniki producenta, nie nasze i nie specyfikacja maksimum.
SD / SDHC / SDXC, tryby 1.8 V, taktowanie i boot każdego Zynq/RPi/Red Pitaya/Trenz/
Digilent trzeba kwalifikować dla konkretnej rewizji i karty. USB2640/schemat legacy
nie uprawniają do obietnicy USB3 ani prędkości SDReWire. Na początek użyć microSDHC
32 GB, krótkiego połączenia i standardowego trybu SD; mierzyć wydajność osobno.

## Architektura w istniejącym repo

To nowy zasób biblioteki `labinstruments`, obok driverów przyrządów i transportów.
Nie tworzymy kolejnego frameworka DUT ani serwera. Warstwy:

- `RemovableStorage`: lock, transakcje, OFF, oczekiwanie, streaming, logi, recovery.
- `Backend` (Protocol): ownership, quiesce DUT, mount/unmount, identyfikacja, writer.
- `SDWireStorage`: realne wykrywanie i status; mutacje zablokowane bez OFF.
- `MockRemovableStorage`: trwały model z prywatnymi plikami, nigdy block device.
- `storage_workflow`: build → boot files → target → power cycle → UART → health.

Przyszłe SDReWireStorage, USBRelaySDMux, NetworkStorageEmulator i VirtualSD
implementują Protocol; workflow nie rozpoznaje sprzętu SDWire.

```python
from labinstruments.storage import RemovableStorage, MockRemovableStorage
backend = MockRemovableStorage('SIMULATED-01', '/tmp/hil-example/mock')
resource = RemovableStorage('zynq_dev', backend, '/tmp/hil-example/runtime')
with resource as storage:                   # lock przez cały cykl
    with storage.host('boot') as sd:
        sd.copy('BOOT.BIN', '/boot/BOOT.BIN')
        sd.copy('image.ub', '/boot/image.ub')
    # host() kończy w OFF dopiero po sync/unmount
    storage.acquire_target()
    storage.wait_for_target()
    # tutaj dut.power.cycle(), dut.uart.expect(...)
```

API: `acquire_host`, `acquire_target`, `disconnect`, `wait_for_host`,
`wait_for_target`, `block_device` (słownik pełnej tożsamości), `partitions`, `info`,
`host`, `flash`, `recover`. Metody wymagają wejścia w context resource.
`host()` oznacza transakcję plikową, nie tylko przełączenie. Domyślna partycja
mock to BOOT. Realne mount/copy jest świadomie zablokowane wraz z brakiem OFF.

HOST → target: unmount → sync → OFF/readback → delay → target/readback.
Target → host: quiesce DUT → OFF/readback → delay → host → device identity.
Mock symuluje quiesce; production backend musi wymusić i potwierdzić power-off
lub odpowiedni reset/tri-state DUT. Reset sam w sobie nie zawsze wyłącza SDIO.

## Powtarzalna instalacja

Brak nowych system packages ani pip dependencies dla API/CLI. Python >=3.11 i
stdlib zgodnie z istniejącym repo. Nix jest preferowany dla kontrolera C++:

```sh
./scripts/bootstrap-storage.sh --install
export HIL_STORAGE_CONFIG="$PWD/examples/storage/mock.json"
local/storage-tools/bin/hil-storage --json list
nix --extra-experimental-features 'nix-command flakes' develop path:.
# w shellu: hil-storage, sd-mux-ctrl, bmaptool
```

`flake.lock` przypina nixpkgs. Tarball sd-mux ma przypięty commit i SHA256
`sha256-WJTaEqdQbPEMmSxTHRkyECFacAFgeDXufYIqxxYM5rk=`. Build ustawia politykę CMake
3.5 dla starego projektu i brakującą ścieżkę nagłówków libftdi. Bez `sudo make install`.
Opcja `--install` tworzy udokumentowany launcher w ~/.local/bin/hil-storage,
bez nadpisywania obcych plików. Build Nix x86_64 został sprawdzony; aarch64 jest zadeklarowany, ale nie zbudowany.
Pakiet `hil-storage` zawiera Python, kontroler i bmaptool; kod także w istniejącym
zipapp labinst.pyz (import `labinstruments.storage_cli`).

Bez Nix do mocka: `scripts/hil-storage --config examples/storage/mock.json list`.
CLI poza repo domyślnie czyta `~/.config/hil-storage.json`; zmienna
`HIL_STORAGE_CONFIG` lub `--config` wskazuje inny plik. Bez konfiguracji `list`
wykrywa USB, bez tworzenia fikcyjnych urządzeń. Format JSON jest wybrany zgodnie
z resztą biblioteki, bez obowiązkowej zależności YAML.
[Mock](../examples/storage/mock.json), [DUT Zynq](../examples/storage/zynq.json).
[Labgrid USBSDWire resource](https://labgrid.readthedocs.io/en/v26.0/_modules/labgrid/resource/udev.html)
potwierdza identyfikację nadrzędnego huba jako `0424:2640`; nie jest to VID/PID
kontrolera ani gwarancja unikalnego serialu czytnika.
Aliasy są nazwami kluczy w `storage`, nie zapisem EEPROM SDWire.

## CLI dla agenta

```sh
export HIL_STORAGE_CONFIG="$PWD/examples/storage/mock.json"
scripts/hil-storage --json list
scripts/hil-storage zynq_dev status --json
scripts/hil-storage zynq_dev host --json
scripts/hil-storage zynq_dev device --json
scripts/hil-storage zynq_dev partitions --json
scripts/hil-storage zynq_dev off --json
scripts/hil-storage zynq_dev target --json
scripts/hil-storage zynq_dev flash image.img.xz --dry-run --json
scripts/hil-storage zynq_dev flash image.img.gz --verify --json
scripts/hil-storage zynq_dev mount --copy BOOT.BIN /boot/BOOT.BIN --json
scripts/hil-storage zynq_dev recover --json
scripts/hil-storage discover --json
```

`mount` jest ograniczoną transakcją: wykonuje `--copy`, sync, unmount i OFF,
nie zostawia mounta dostępnego innemu procesowi po zwolnieniu locka.
Do dowolnych zmian rootfs/plików używać context API z własnym backendem mount.
Ścieżka /boot w API oznacza wybraną partycję, nie /boot hosta. Odrzucamy traversal
oraz symlinki wychodzące poza mount. Kopie plików są atomic rename z fsync; brak
rollbacku całej karty po częściowej transakcji.

`--dry-run` nigdy nie otwiera writer, ale **zmienia ownership w mocku** w celu
ustalenia pojemności/urządzenia, a kończy w OFF. Na realnym SDWire, który wymaga
zmiany ownership, odmawia przez brak OFF. Nie jest read-only diagnostyką USB;
do tego są `discover` i `status`.

Obrazy .img/.img.gz/.img.xz: preflight strumieniowo liczy rozpakowany rozmiar i
SHA256, bez pliku tymczasowego. Drugie przejście zapisuje i kontroluje limit;
zmiana treści źródła kończy się błędem. `--verify` czyta i hashuje zapisane bajty.
Jeśli jest .bmap i bmaptool, preferujemy bmaptool z **odziedziczonym, wcześniej
zweryfikowanym deskryptorem**, nie dowolnym /dev/sdX. Walidujemy rozmiar i zakresy
bmap, zerujemy pomijane dziury, następnie obowiązkowo sprawdzamy pełny SHA256.
Nie ponawiamy zapisu inną metodą po błędzie bmaptool. Bez bmap używamy bounded
Python streaming (odpowiednik dd bez powłoki), z fsync; bez ponownej identyfikacji
nie ma writer. Realny writer pozostaje zablokowany w SDWireStorage.

Stdout `--json`: jeden obiekt, `ok`, klasyfikacja błędu `error.code/message`.
`locked: true` oznacza lock utrzymywany podczas odpowiedzi status, nie rezerwację
po zakończeniu procesu CLI. Do całego cyklu używać jednego context resource.

Exit: 0 sukces; 2 config; 3 lock; 4 identity; 5 safety/OFF/recovery; 6 karta/partycja;
7 obraz/pojemność; 8 verify; 9 I/O/inne; 130 Ctrl-C/SIGTERM. `list` to snapshot
inwentarza: błędy poszczególnych zasobów są w wierszach, exit 0 nie oznacza
sprawności wszystkich urządzeń. Brak promptów lub domyślnego wyboru jedynego dysku.

## Lock, recovery, logi

Domyślny runtime: `~/.local/state/hil-storage`, alternatywnie `--runtime` albo
`HIL_STORAGE_RUNTIME`. Lock `hil-storage-SERIAL.lock` wykorzystuje flock i
O_NOFOLLOW; wszystkie procesy/aliase tego samego zasobu muszą używać tego samego
runtime. Dla wielu użytkowników administrator przygotowuje wspólny katalog np.
`/var/lock/hil-storage` z grupą HIL, bez world-write, i ustawia wspólną zmienną.
Nie zmieniać runtime w celu obejścia zajętego locka. Lock jest kooperatywny:
samodzielne sd-mux-ctrl/dd/automount poza API go nie respektują. Desktop automount
należy wyłączyć dla stanowiska; nie traktujemy samego flock jako hardware interlock.

Znacznik `.dirty` powstaje przed zmianą ownership i zostaje po awarii. Następny
proces próbuje OFF i blokuje HOST/TARGET do jawnego `recover`. Recovery nie naprawia
filesystemu i nie potwierdza kompletności BOOT.BIN; kartę trzeba obejrzeć/naprawić
w kontrolowanym workflow, zanim wróci do DUT. Nie ma automatycznego fsck -y.
Ctrl-C/SIGTERM: próba OFF. SIGKILL/zanik hosta: cleanup nie może się wykonać;
OFF dopiero po następnym przejęciu w mocku, a realny failsafe wymaga sprzętu.
Błąd OFF zapisujemy jako recovery failed/unknown, nigdy jako potwierdzony OFF.

`operations.jsonl`: UTC, storage/serial, stary/nowy stan, urządzenie, hash obrazu,
operacja, czas, wynik, diagnostyka i simulated. Logi transition/flash/host_files/
recovery są fsync. Status/discover są odczytami, nie operacjami na karcie.

## Walidacja i zakres otwarty

Testy: przejścia obu kierunków, trzy formaty obrazu, dry-run bez writer,
readback, capacity, wrong disk, symlink, karta znika/brak karty, mount/copy/unmount
failure, stale transaction, persistent dirty, collision lock między procesami,
rzeczywisty SIGINT/SIGKILL subprocessów, odmowa SDWire bez OFF, logi, CLI,
workflow PASS/FAIL i pełny UART artifact. To **TESTED / SIMULATED**.

**REQUIRES HARDWARE:** realne seriale obu sztuk, czytnik/topologia/by-id,
SDIO/vdd izolacja i break-before-make na zakupionej rewizji, reset/hotplug hosta,
SDXC/UHS, automount/busy kernel, uszkodzony FS, power/reset DUT, fizyczny UART,
boot Zynq. Błędy mount/unmount i busy device są symulowane; nie twierdzimy, że
przetestowano Linux mount na realnej karcie. Realne mutacje są zablokowane, więc
nie deklarujemy możliwości automatycznego flashowania tych SDWire bez interlocka.

[Bring-up](sdwire-bringup.md) opisuje jedną komendę inventory i raport blokady.
`storage_workflow.storage_boot_test` przyjmuje istniejące zasoby build/power/UART,
zapisuje `uart.bin` i `result.json`. Oczekuje kolejno U-Boot, Linux i login w jednym
budżecie czasu. Capture rozpoczyna przed resetem; adapter `receive(timeout)` musi
respektować timeout. Opcjonalny health_check nie zastępuje login/health urządzenia.

Raport wykonanej walidacji: [software-2026-10-09-final](../reports/storage/software-2026-10-09-final/README.md).
Pełna suite Nix: **117/117 PASS**, w tym **37 testów storage**, bez skip.
Powtórzenie z artifactami:

```sh
nix --extra-experimental-features 'nix-command flakes' develop path:. --command \
  python3 scripts/validate-storage.py --output local/storage-replay
```

## Fizyczny egzemplarz podłączony 2026-10-13

Wykryto fabryczny FT200X `0403:6015`, product `FT200X USB I2C`, serial `DP04I355`.
Nie był skonfigurowany jako `04e8:6001` / `sd-wire`; wcześniejsze wykrywanie pomijało
fabryczny PID. Obecnie factory discovery wymaga dokładnego produktu, USB2640
`0424:2640` i dokładnie jednego kontrolera FTDI oraz czytnika `0424:4050` we wspólnym
hubie. Sam FTDI `0403:6015` nie wystarcza. Nie programujemy automatycznie EEPROM-u.

`bringup` generuje również propozycję konfiguracji czytnika z sysfs/by-id i bieżącej
pojemności; to inventory, nie zgoda na zapis. Dla factory status zwraca unknown z
`state_error.code=UNCOMMISSIONED_FACTORY`; `device`/`partitions` działają jako
odczyty metadanych, a wszystkie przełączenia nadal blokuje OFF_UNSUPPORTED.

[Raport hardware](../reports/storage/hardware-2026-10-13/README.md): topology identity
PASS; czytnik i karta 15716057088 bajtów zidentyfikowane. Szczegółowe próby odczytu
nie są utożsamiane ze sprawdzeniem elektrycznego OFF ani testem zapisu.

Po nadaniu tymczasowych ACL wykonano [PASS_READ_ONLY](../reports/storage/hardware-2026-10-13-read-pass/README.md):
rzeczywisty USB read-pins (raw 254) i dwa zgodne odczyty 1MiB zweryfikowanej karty.
Nie interpretujemy factory raw CBUS jako potwierdzonej własności. OFF, zapis i boot
pozostają nieprzetestowane/zablokowane. Publikowany kod na aktualnej bazie main
przeszedł [83 testy](../reports/storage/software-2026-10-13-main/README.md), w tym
41 testów storage. Wcześniejsze 121 PASS odnosi się do bazy feature z dodatkowymi
testami przyrządów, nie do zmniejszenia zakresu testów storage.
