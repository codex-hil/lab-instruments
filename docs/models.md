# Profile v0.1

| Klucz modelu | Transport używany w labie | Zaimplementowany zakres |
|---|---|---|
| psw800-1.44 | TCP 2268 | ID, V/I pomiar, DC V + limit I, OFF |
| ngp814 | TCP 5025 | ID, V/I pomiar, DC V + limit I, wybór 1..4, globalny OFF |
| b2910bl | TCP 5025 | ID, FETCh V/I (ostatnia próbka), DC voltage-source z current compliance, HIZ/OFF |
| smb100a | TCP 5025 | ID, niemodulowana nośna CW frequency + dBm, RF OFF |
| afg1062 | USBTMC | ID, sinus frequency/Vpp/offset, OFF CH1/CH2 |
| mp750288 | TCP 3000 / USBTMC | ID, sinus frequency/Vpp/offset, OFF CH1/CH2 |
| mso4104 | TCP 4000 | ID, immediate frequency/Vpp wybranego kanału |
| mso2002b | USBTMC | wspólny profil immediate frequency/Vpp; odczyty sprawdzone przez gateway |
| tbs1022 | USBTMC (tryb Computer) | wspólny profil immediate frequency/Vpp; dokładne ID `TBS 1022` |
| dmm7510 | TCP 5025 | ID, READ? w zastanej funkcji pomiarowej |
| 6487 | TCP 4001 przez RS232 9600 8N1 | ID, READ?, source_state, źródło DC ±500 V z limitem I, OFF; rozszerzenie HV bez testu sprzętowego |
| 8550 | TCP 4001 przez RS232 9600 8N1 | ID, pomiar V/I, CC w zakresie 3 A, input OFF |
| n9918b | TCP 5025 | ID, odczyt istniejącego markera 1, bez zmiany trybu |

Nazwy pełnych modeli są weryfikowane z odpowiedzi `*IDN?`, nie z etykiety portu.
Dla źródeł serwer wymaga również dokładnego serialu. Profile nie obejmują całego SCPI.
Nieznane Tektroniksy serii 1000/2000 dodajemy dopiero po sprawdzeniu dokładnego modelu.

`read frequency/vpp` oscyloskopu zmienia immediate measurement i wyłącza HEADER;
nie zmienia skali, podstawy czasu ani wyzwalania. READ? miernika inicjuje pomiar w zastanym
trybie; nie oznacza automatycznie pomiaru napięcia. Picoamperomierz może mieć aktywne
zero-check. FETCh SMU nie inicjuje nowego pomiaru, może zwrócić stary wynik/brak danych.

Transport obsługuje binarne wiadomości USBTMC oraz definite-length IEEE 488.2 na TCP
z terminatorem po bloku. MSO4104 ma teraz semantyczną akwizycję skalowanych waveformów w rozszerzeniu
[FRA](fra/driver-gap.md), nadal bez fizycznego commissioningu tego rozszerzenia.
Pozostałe profile nie mają tego API; eksport screenshotów nie jest zaimplementowany. Własny skrypt zaufany może użyć `Transport.transaction`.
Bloki TCP `#0` są jawnie odrzucane; dla nich potrzebny jest profil framingu danego modelu.
Limit odpowiedzi to 16 MiB. Usługa USB wymaga kernel ioctl MSG_IN_ATTR (sprawdzono na
bieżącym Linuxie); stary kernel bez niego musi zostać zaktualizowany.

Nowy profil powinien mieć: dokładne ID, operacje typed, jednostki, terminatory, timeouty,
tryby/warunki OFF, sprzętowe zakresy, kontrolę odpowiedzi oraz test z fałszywym transportem
przed testem rzeczywistego urządzenia. Nie zakładamy, że rebrand ma identyczny firmware.

Aktualny status prób sprzętowych: [macierz HIL](../reports/hil-2026-09-25/README.md).
Profil MSO4104 automatycznie uwzględnia padding CR pomiędzy odpowiedziami TCP portu 4000;
przy użyciu samego Transport bez Driver ustaw `read_padding: "\r"`.

TBS1022 korzysta ze wspólnych metod oscyloskopu, zgodnie z [instrukcją programowania
Tektronix 077044403 Rev B](https://www.tek.com/en/oscilloscope/tds1000-manual).
Kanał pomiarowy musi być wyświetlany; `9.9E37` oznacza nieważny pomiar, nie częstotliwość.
Profil nie dodaje obsługi akwizycji waveformów dla tego modelu.

Szczegóły źródła 6487 i procedura odbioru: [Keithley 6487 HV](keithley-6487.md).
