# API v1

HTTPS, `Authorization: Bearer <token>`, JSON. Brak domyślnych haseł. Token operatora
nie ma uprawnienia zmiany konfiguracji. Wszystkie odpowiedzi mają `Cache-Control: no-store`.

- `GET /`: panel WWW, bez informacji o urządzeniach przed autoryzacją.
- `GET /v1/status`: status, po autoryzacji. W trybie control wynik ostatniej operacji,
  **nie gwarancja bieżącego stanu fizycznego**. Gateway pokazuje bieżącą enumerację USB.
- `POST /v1/control`: tylko w roli control, pola `device`, `action`, `args`.
- `POST /v1/transaction`: tylko w roli usb-gateway, pola `slot`, `data`, `reply`.

## Operacje typed

```json
{"device":"supply","action":"apply","args":{"channel":1,"voltage":5,"current":0.1,"enable":true}}
```

`current` jest current-limit/compliance dla supply/SMU; dla load jest prądem CC.
DC napięcie w V, prąd w A, moc W. SMU obecnie wyłącznie voltage-source, local sense.
RF: `channel, frequency, dbm, enable`. AWG: `channel, frequency, vpp, offset, enable`.
Load: `channel, current, enable`. Częstotliwości Hz. Pola są obowiązkowe; dodatkowe odrzucone.

`identify`, `off`, `renew` mają `args: {}`. `read` ma `operation` oraz opcjonalne `channel`.
Odpowiedź `apply` zawiera odczyt kontrolny, kompletny stan i `lease_seconds` dla ON.
`renew` przedłuża tylko jeszcze niewygasłą dzierżawę; nie włącza wyjścia. Wszystkie osoby
z tokenem mają tę samą rolę operatora — nie ma jeszcze odrębnych kont ani lease ownerów.

## Surowa transakcja USB dla zaufanego klienta

```json
{"slot":"usb1","data":"KklETj8K","reply":true}
```

`data` to base64 bajtów `*IDN?\n`. Odpowiedź `{"data":"...base64..."}` obejmuje pełne
bajty do USB EOM. Dla zapisu `reply:false`, odpowiedź zawiera pusty string base64.
Bramka niczego nie dopisuje do komendy. Pojedyncza transakcja jest atomowa; wiele transakcji
nie tworzy sesji wyłącznej. Nie wolno równolegle uruchamiać dwóch skryptów konfiguracyjnych
tego samego przyrządu. Złożone źródła z limitami należy obsługiwać przez tryb control.

API nie oferuje arbitralnego hosta, nazwy pliku, komendy systemowej ani ścieżki `/dev`.
Konfigurację slotów ustala root. Po odpięciu klient dostaje 503; ponowna transakcja rozwiązuje
serial/topologię ponownie. Nie ma automatycznego retry zapisów. Odpowiedź utracona po ON
oznacza nieznany stan: użyj typed OFF i poczekaj na potwierdzenie albo sprawdź sprzęt.
