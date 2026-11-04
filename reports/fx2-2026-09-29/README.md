# Uruchomienie FX2 — 2026-09-29

Płytka z AliExpress: Cypress CY7C68013A (FX2LP), REVID=1,
USB `04b4:8613`, High Speed 480 Mb/s. Oznaczenie EEPROM-u ze zdjęcia:
FT24C128A, 16 KiB. Dokładny wariant PCB nie został potwierdzony.

Ubuntu 24.04 amd64, sigrok-cli 0.7.2, libsigrok 0.5.2,
sigrok-firmware-fx2lafw 0.1.7; uruchomiony firmware raportował wersję 1.4.
Pakiety rozpakowano lokalnie, ponieważ konto nie miało sudo. Użytkownik
zainstalował regułę udev udostępniającą urządzenie grupie konta.

## Akwizycja

| Kanały | Próbkowanie | Próbki na kanał | Bajty danych | Wynik |
| --- | --- | --- | --- | --- |
| 16 | 1 MHz | 100000 | 200000 | zapis zakończony, oczekiwany rozmiar |
| 16 | 12 MHz | 1200000 | 2400000 | zapis zakończony, oczekiwany rozmiar |
| 8 | 24 MHz | 2400000 | 2400000 | zapis zakończony, oczekiwany rozmiar |

Sprawdzono metadane i dane w plikach `.sr`. Wszystkie aktywne kanały miały
wyłącznie stan wysoki. Nie podawano znanego sygnału: wynik potwierdza komunikację
i zapis, ale nie poprawność czasową, reakcję pinów ani brak utraty próbek
przy długiej rejestracji. 48 MHz nie testowano. Plików ze stałymi stanami
nie dodano do repo. PulseView nie instalowano w tej sesji.

## EEPROM

Firmware pomocniczy z libfx2, zbudowany SDCC 4.2.0, został załadowany do RAM.
Standardowa próba odczytu pod 0x51 nie otrzymała ACK. Po zastosowaniu
[poprawki](../../tools/fx2/eeprom-read-only.patch) kość odpowiedziała pod
0x50; adresy 0x51–0x57 nie odpowiadały.

Dwa odczyty zakresu 0x0000–0x3fff miały po 16384 bajty i były identyczne.
Cała zawartość: `FF`. SHA-256 każdego pliku:

```text
0fbba07a833d4dcfc7024eaf313661a0ba8f80a05c6d29b8801c612e10e60dee
```

[Raport odczytu JSON](eeprom.json). Binarki pozostały lokalnie jako
`ft24c128a-0x50-read1.bin` i `ft24c128a-0x50-read2.bin`.
Nie wykonywano zapisu EEPROM-u. Przywrócono firmware sigrok do RAM
i potwierdzono wykrywanie 16 kanałów. Następnie użytkownik odłączył płytkę.

Przenośny skrypt w repo jest uporządkowaną wersją skryptu użytego przy
odczycie. Jego ponowne wykonanie na sprzęcie pozostaje do sprawdzenia,
ponieważ płytka została odłączona.

Weryfikacja wersji repo: czyste pobranie przypiętego libfx2, zastosowanie
poprawki i budowanie przez `build-reader.sh` dały plik Intel HEX identyczny
bajtowo z użytym na sprzęcie. Sprawdzono składnię skryptów, `--help`
i odmowę działania przy braku urządzenia (przed utworzeniem katalogu kopii).
Istniejące 31 testów repo przeszło; nie są to testy akwizycji FX2.

## Następny test

Potwierdzić oznaczenia złącz i dopuszczalne poziomy na tym PCB, następnie
sprawdzić niski/wysoki stan i znany przebieg cyfrowy na każdym kanale.
Zmierzyć poprawność częstotliwości i stabilność dłuższej akwizycji.
