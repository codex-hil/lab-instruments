# RPI-USBTMC: wdrożenie bramki i panelu WWW

2026-09-29, Raspberry Pi 3 Model B Plus Rev 1.3, host `RPI-USBTMC`,
`192.168.2.16`. Debian 13 trixie, kernel `6.18.50+rpt-rpi-v8` aarch64,
Python 3.13.5. Konfiguracja: `examples/rpi-usbtmc.json`.

Kod: lokalna gałąź `feature/rpi-gateway` oparta o `feature/fra` (`8f000f1`),
ze zmianami roboczymi. Cztery pierwotnie wskazane pliki bramki były identyczne
na `main` (`bf5ac1c`) i `feature/fra`. Nie dodano nowych driverów przyrządów.

Wdrożony `labinst.pyz`, SHA-256:
`e0db3d1b2c2ab454d8fa69b2bd9a8abb368a730f4ae25ca7927f6cae68585732`.

## Działa na fizycznym sprzęcie

- Usługa systemd `labinst`, enabled/active, użytkownik `labinst`; finalny PID 2131,
  `NRestarts=0` po wdrożeniu. Proces uruchomiono ponownie jawnie przy aktualizacji artefaktu.
- HTTPS `https://192.168.2.16:8840/`. Zawartość strony zgodna bajtowo ze źródłem.
  Weryfikacja TLS z certyfikatem pobranym przez SSH; bez wyłączania weryfikacji.
- Token wymagany przez API; brak tokenu daje HTTP 401.
- Cztery węzły USBTMC mają `root:labinst 0660`, nadane regułami udev dla
  dokładnych VID:PID i seriali. Wszystkie dostępne dla procesu usługi.
- Każdy przyrząd odpowiedział na `POST /v1/identify` oraz przez istniejący
  `Transport(kind='gateway').query('*IDN?')`, czyli endpoint `/v1/transaction`.
  Osiem transakcji w końcowej weryfikacji, zero błędów. Nie zmieniano nastaw ani wyjść.

| Slot | Serial USB | Port przy wdrożeniu | VID:PID |
|---|---|---|---|
| afg1062 | 1544477 | 1-1.2 | 0699:0353 |
| mp750288 | 1944201 | 1-1.3 | 5345:1235 |
| mso2002b | C010257 | 1-1.1.2 | 0699:039a |
| tbs1022 | C012657 | 1-1.1.3 | 0699:03ae |

TBS1022 początkowo zgłaszał HID (`0699:036b`). Po wybraniu „Computer” i ponownym
podłączeniu przez użytkownika pojawił się USBTMC (`0699:03ae`) bez restartu Pi.
To nastąpiło przed uruchomieniem bramki; nie jest testem hotplugu działającej usługi.

Pełne odpowiedzi: [identification.json](identification.json).
Końcowy status i osiem transakcji: [status.json](status.json).

## Weryfikacja lokalna

- 71 testów unittest PASS, w tym hotplug z renumeracją, błąd w trakcie odczytu bez
  ponowienia, niejednoznaczność selektora, niedostępne urządzenie, identyfikacja HTTP,
  limit historii i dostęp do statusu podczas zajętej bramki.
- Deterministyczny build `.pyz` PASS; sprawdzenie sumy na Pi PASS.
- Firefox desktop/mobile 390 px: cztery karty, test wszystkich slotów, brak poziomego
  przewijania strony, bezpieczne wyświetlanie tekstu, usuwanie statusu po HTTP 401,
  czyszczenie tokenu i brak tokenu w localStorage/sessionStorage: PASS.
- Test przeglądarkowy wykonano na lokalnym fixture z zapisanymi deskryptorami i
  odpowiedziami z Pi; transport USB w tym teście był symulowany. Rzeczywiste HTTPS
  i komunikację sprzętową sprawdzono osobno powyżej.
- Wynik: [browser-smoke.json](browser-smoke.json). Zrzuty dostępne lokalnie w
  `local/gateway-browser-desktop.png` i `local/gateway-browser-mobile.png`.

## Pozostaje do wykonania

Fizyczne odłączenie i powrót przy działającej usłudze, odłączenie podczas transakcji,
renumeracja węzłów na Pi, przeniesienie między portami, binarne przebiegi, transfery
pod obciążeniem, stabilność zasilania/huba oraz próba autostartu po restarcie Pi.
Nie wykonywano odbioru izolacji sieciowej ani testów chronionych wyjść w trybie control.

## Dostęp i obsługa

Instrukcja certyfikatu, tokenu, API i klienta Python: `docs/deployment.md`.
Sekrety pozostają poza repozytorium. Odcisk SHA-256 certyfikatu stanowiska:
`8D:5B:0A:63:6C:87:1D:80:9A:AD:77:37:EA:CE:DB:1E:71:1B:78:F6:20:2B:7E:CC:F0:03:F6:5E:A0:38:B2:0A`.

Przy zajętej bramce nowe transakcje otrzymują HTTP 503 przed wysłaniem komendy;
nie ma automatycznego ponawiania. Historia ostatnich 40 transakcji jest w RAM,
bez treści komend/danych, i zeruje się przy restarcie.
