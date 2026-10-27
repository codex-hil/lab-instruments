> Update 2026-10-27: a separate [guarded HOST/DUT API](sdwire-guarded.md)
> supports the actual v1 topology without requiring OFF. It requires verified,
> continuously held DUT stop and mandatory readback. The historical isolated
> API below remains read-only; new physical commissioning is pending USB access.

# SDWire bring-up — bez deklaracji testu fizycznego

**REQUIRES HARDWARE.** Dwie sztuki kupione, seriale nieznane. Research wskazuje
brak trwałego OFF w legacy SDWire; automatyczny zapis i przełączanie pozostają
zablokowane. Szczegóły i źródła: [sdwire.md](sdwire.md).

## Pierwsze podłączenie

1. Włóż testową microSDHC (preferowana 32 GB, bez jedynej kopii danych).
2. Włóż SDWire do DUT, na razie z wyłączonym zasilaniem DUT.
3. Podłącz USB do hosta. Sprawdź mechaniczne dopasowanie i rewizję PCB.
4. Z katalogu repo uruchom:

```sh
./scripts/bootstrap-storage.sh
local/storage-tools/bin/hil-storage bringup \
  --report local/sdwire-bringup-01 --alias zynq_dev --json
```

Z dwoma podłączonymi SDWire pominąć `--alias`: nazwy sdwire-01/sdwire-02 przypisywane
są po sortowaniu seriali. Konfiguracja i raport powstają wyłącznie w nowym katalogu;
nie nadpisujemy istniejącego inventory ani EEPROM-u. Potem zmień nazwy kluczy JSON
na zynq_dev/spare, bez zmiany seriali.

Komenda samodzielnie wykrywa product/VID/PID/serial/topologię, odczytuje status,
przygotowuje `storage.json` i `report.json`. Brak USB: exit 6 i raport NO_DEVICE.
Legacy SDWire: exit 5, BLOCKED_OFF_UNSUPPORTED; mode_tests i write_test są jawnie
niewykonane. Problemy uprawnień/libftdi/status trafiają do raportu. Czytnika nie
zgadujemy — wymagane osobne rozpoznanie i kwalifikacja.

`--alias` wymaga dokładnie jednego urządzenia. Puste/zdublowane seriale powodują
fail closed; nie wykonujemy automatycznego `--set-serial` (zmienia EEPROM FTDI).

## Czynności Codexa po inventory

- Zachować raport oraz schemat odpowiadający fizycznej rewizji.
- Odczytać USB drzewo (`lsusb -t`), sysfs controller/hub/reader i /dev/disk/by-id;
  sprawdzić, czy serial czytnika istnieje i jest jednoznaczny dla obu sztuk.
- Zapisać reader VID/PID, serial, ścieżkę USB, by-id i zakres pojemności w konfiguracji
  według [zynq.json](../examples/storage/zynq.json); nie wpisywać /dev/sda.
- Sprawdzić `status`, `device`, `partitions` bez przełączania. Jeśli reader nie ma
  odpowiednich identyfikatorów, zostawić blokadę i zaprojektować dodatkowe przypięcie
  topologii; nie usuwać kontroli identity.
- Zweryfikować możliwość realnego OFF: data/CLK/CMD/DAT0..3 oraz VDD i brak
  back-power. EN podłączone do GND w v1.4 oznacza brak tej możliwości w stock SDWire.
- Jeśli hardware się różni od v1.4, zaktualizować evidence/specyfikację przed
  implementacją osobnego, kwalifikowanego backendu. Nie ustawiać supports_off=True
  na podstawie braku /dev/sdX lub LED.

**Przy obecnych ustaleniach kończymy na raportowaniu blokady.** Automatyczne
sprawdzenie HOST/OFF/TARGET i test zapis/odczyt nie może legalnie przejść wymaganych
bramek bezpieczeństwa samym kupionym stock SDWire.

## Kwalifikacja po dodaniu izolacji

Poniższe kroki są planem, nie wykonanym testem:

1. Podłączyć interlock sygnałów/zasilania i niezależny power/reset DUT; wykazać,
   że oba źródła nie mogą zasilać/sterować karty jednocześnie, także przy awarii USB.
2. Zmierzyć OFF i break-before-make; test obu kierunków, obu sztuk, hotplug, reset
   hosta, zaniki VBUS, host-off/DUT-on. Readback stanu izolacji musi być prawdziwy.
3. Uzupełnić backend o quiesce/readback DUT, safe OFF, mount/unmount, stable-device
   wait, automount inhibition i writer oparty na zweryfikowanym otwartym fd.
4. Na testowej karcie i wyłączonym DUT wykonać dry-run, backup, mały kontrolowany
   zapis i pełny readback/hash. Przy każdej niejednoznaczności bez zapisu.
5. Sprawdzić zmianę /dev/sdX, wyjęcie karty, USB unplug, busy filesystem,
   automount, zły reader, kolizję locka, SIGINT/SIGTERM, SIGKILL i awarię hosta.
6. W raporcie oddzielić wyniki realne od wcześniejszych SIMULATED. Zapisać seriale,
   rewizje, pojemność, USB tree, obrazy/hashes, log operations, timing i pomiary.

## Pierwsza pętla Zynq

Użyć istniejącego środowiska Vivado/ARTIQ/Trenz, bez instalowania drugiego toolchainu.
Najpierw przeczytać workspace `docs/toolchains/vivado.md` i status konkretnego DUT.
Nie zmieniać istniejącego golden firmware ani współdzielonego JTAG/power bez
sprawdzenia dostępności zasobów stanowiska.

Wywołać `storage_workflow.storage_boot_test` z adapterami istniejących zasobów:

```python
from labinstruments.storage_workflow import storage_boot_test
result = storage_boot_test(
    storage=dut.storage,
    build=build_boot_files,
    boot_files={'build/BOOT.BIN': '/boot/BOOT.BIN',
                'build/image.ub': '/boot/image.ub'},
    power_cycle=dut.power.cycle,
    uart_receive=dut.uart.receive,       # bytes, timeout w sekundach
    artifacts='local/zynq-boot-001',
    timeout=120,
    health_check=lambda uart: uart.expect('health: PASS', 30),
)
```

`dut` to obiekt zasobów przyszłego/innego test runnera, nie nowy framework tutaj.
Workflow zapisuje pełny odebrany `uart.bin` (także przy FAIL) i `result.json`,
zaczyna capture przed power-cycle, oczekuje U-Boot → Linux version → login:.
Health marker trzeba dostosować do realnego obrazu. Nie loguje automatycznie do
systemu i nie wymyśla poświadczeń. Katalog artifact musi być nowy.

PASS wymaga realnego bootu i uzgodnionego health check. Testy Python mock UART są
SIMULATED i nie dowodzą działania GPIO, power, UART, Linux ani FPGA na sprzęcie.

## Factory FT200X i test bez zapisu

Egzemplarz `DP04I355` ma factory PID `0403:6015`, nie `04e8:6001`.
`discover` obsługuje go po weryfikacji dedykowanego huba/czytnika. Nie uruchamiać
`--set-serial` tylko po to, żeby uzyskać rozpoznanie — jest to zapis EEPROM-u.
Status własności pozostaje unknown do kwalifikacji CBUS/EEPROM.

Bounded test z rzeczywistymi, ale wyłącznie odczytami:

```sh
python3 scripts/bringup-sdwire-readonly.py --serial DP04I355 --output local/sdwire-readonly-001
```

Raport rejestruje brak uprawnień jako ACCESS/NOT_RUN i nie omija go. Tymczasowe ACL
oraz wynik pierwszego podłączenia są w [raporcie hardware](../reports/storage/hardware-2026-10-13/README.md).
