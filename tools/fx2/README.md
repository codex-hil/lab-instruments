# Cypress FX2 jako analizator logiczny

Narzędzia pomocnicze dla płytki CY7C68013A (FX2LP), USB `04b4:8613`,
EEPROM FT24C128A 128 kbit = 16 KiB. To oddzielny zestaw narzędzi korzystający
z sigroka i libfx2; nie jest driverem SCPI ani częścią `labinst.pyz`.
[Wyniki prób sprzętowych](../../reports/fx2-2026-09-29/README.md).

## Uruchomienie analizatora

Na Debianie/Ubuntu zainstaluj:

```sh
sudo apt-get install sigrok-cli sigrok-firmware-fx2lafw usbutils
# Opcjonalny interfejs graficzny:
sudo apt-get install pulseview
```

Firmware `fx2lafw-cypress-fx2.fw` ładowany jest automatycznie do RAM.
Po utracie zasilania trzeba go załadować ponownie, co sigrok robi przy skanowaniu.
Programowanie EEPROM-u nie jest wymagane.

Jeżeli pojawia się `LIBUSB_ERROR_ACCESS`, z katalogu głównego repo:

```sh
fx2_group=$(id -gn)
sed "s/@GROUP@/$fx2_group/g" tools/fx2/70-fx2-analyzer.rules.in > /tmp/70-fx2-analyzer.rules
sudo install -m 644 /tmp/70-fx2-analyzer.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb
```

Grupa powinna należeć do użytkownika wykonującego pomiar. Reguła obejmuje
bootloader Cypress i identyfikatory firmware sigrok dla 8/16 kanałów.

```sh
sigrok-cli -d fx2lafw --scan
sigrok-cli -d fx2lafw --show
sigrok-cli -d fx2lafw -c samplerate=1m --samples 100000 -o pomiar.sr
sigrok-cli -d fx2lafw -C D0,D1,D2,D3,D4,D5,D6,D7 \
  -c samplerate=24m --samples 2400000 -o pomiar-8ch.sr
```

Pliki `.sr` można otwierać w PulseView. Standardowe przypisanie firmware:
D0–D7 = PB0–PB7, D8–D15 = PD0–PD7. Położenie złącz i ochronę wejść należy
potwierdzić na konkretnym PCB. Pomiar wymaga wspólnej masy.

## Kopia EEPROM-u przez USB

Kość testowanego egzemplarza odpowiada pod adresem I²C **0x50**, ale standardowy
bootloader libfx2 dla dwubajtowego adresowania EEPROM-u używa **0x51**.
Poprawka `eeprom-read-only.patch` przyjmuje adres 0x50–0x57 przez `wIndex`
i odrzuca wszystkie żądania zapisu EEPROM-u. Pozostawia obsługę USB i RAM
z projektu libfx2. Nie zmieniaj zworek w celu dopasowania do narzędzia.

Źródło: https://github.com/whitequark/libfx2
Przypięty commit: `16cdf948a964dbc3506f42753a335db91b63a39b` (licencja upstream 0BSD).

```sh
sudo apt-get install git make sdcc sdcc-libraries python3 python3-usb1
mkdir -p local
sh tools/fx2/build-reader.sh local/fx2-libfx2
python3 tools/fx2/read-eeprom.py \
  --libfx2 local/fx2-libfx2 \
  --restore-firmware /usr/share/sigrok-firmware/fx2lafw-cypress-fx2.fw \
  --output local/fx2-eeprom-backup
sigrok-cli -d fx2lafw --scan
```

Katalog budowania i katalog kopii muszą być nowe. Zatrzymaj akwizycję i zamknij
PulseView przed odczytem. Podłącz tylko jeden FX2 o identyfikatorze `04b4:8613`.
Skrypt ładuje firmware pomocniczy do RAM, szuka EEPROM-u, odczytuje dwukrotnie
16384 bajty z dwubajtowym adresowaniem i porównuje kopie. Rozmiar jest dobrany
do FT24C128A, nie wykrywany automatycznie.

W bloku `finally` skrypt próbuje przywrócić firmware sigrok do RAM, również
po błędzie. Jeśli urządzenie zostanie odłączone lub proces przerwany w sposób
uniemożliwiający sprzątanie, podłącz płytkę ponownie i uruchom skan sigroka.
Żadna z tych operacji nie programuje EEPROM-u.

## Dokumentacja źródłowa

- https://sigrok.org/wiki/Lcsoft_Mini_Board
- https://sigrok.org/wiki/Fx2lafw
- https://datasheet.lcsc.com/lcsc/Fremont-Micro-Devices-FT24C128A-ENR-T_C232872.pdf
