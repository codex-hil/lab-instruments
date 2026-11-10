# SMU2 — Keysight B2910BL MY63320299: przekazanie do pomiarów napięcia

Dodany 2026-11-10 do puli jako **smu2**; istniejący `smu` MY63320305 jest innym
przyrządem. Profil drivera `b2910bl` jest wspólny, nie tworzymy kopii drivera.

| Pole | Wartość |
|---|---|
| Model / serial | B2910BL / MY63320299 |
| Firmware | 5.0.2429.8966 |
| Ostatni IP / port | 192.168.2.19 / TCP 5025 |
| MAC zaobserwowany przy odczycie ID | 80:09:02:1e:82:d6 |
| Nazwa konfiguracji | smu2 |
| Pełna pula | examples/lab.json |
| Osobna konfiguracja | examples/b2910bl-smu2.json |
| Wspólny lock Optiplex | /home/codex-hil/.cache/b2910bl-MY63320299.lock |

IP pochodzi z DHCP; nie identyfikuje urządzenia. Przed każdą sesją sprawdzić
model i serial, po zmianie IP poprawić wskazówkę transport.host. Obecne automatyczne
wykrywanie DPO4104 nie obejmuje B2910BL. Mapa wspólna: network-inventory/devices.json.

## Rozpoczęcie pracy przez kolejny wątek

Kod na gałęzi `docs/b2910bl-second` w publicznym repo codex-hil/lab-instruments.
Z katalogu checkoutu:

```sh
flock -n /home/codex-hil/.cache/b2910bl-MY63320299.lock \
  python3 -m labinstruments identify \
  --config examples/b2910bl-smu2.json --device smu2
```

W Pythonie użyć istniejących `Transport(spec['transport'])` oraz
`Driver(io, 'b2910bl', 'MY63320299')`. Utrzymywać ten sam kooperatywny flock
przez CAŁĄ sesję, włącznie z konfiguracją, pomiarami i przywróceniem stanu.
Driver nie zakłada tego locka automatycznie. Nie usuwać ani nie omijać zajętego locka.

## Rzeczywisty stan odczytany 2026-11-10

[Surowy raport](../reports/b2910bl-MY63320299-2026-11-10.json):
OUTP=0, OFF:MODE=NORM, ON:AUTO=1, SOUR:FUNC:MODE=VOLT, SENS:REM=0.
Wykonano tylko zapytania; niczego nie ustawiano, nie wyzwalano pomiaru, nie włączano
wyjścia. **To nie jest jeszcze skonfigurowany ani zwalidowany woltomierz.**

## Ważne dla pomiaru napięcia

- Istniejące `Driver.read('voltage')` wysyła `FETC:VOLT?`: zwraca ostatnią próbkę,
  nie wyzwala nowej. Nie traktować jej jako aktualnego napięcia DUT.
- Obecny `Driver.apply` dla B2910BL ustawia źródło NAPIĘCIA z ograniczeniem I.
  Nie używać go jako konfiguratora woltomierza. Ustawienie źródła 0 V nie jest
  równoważne wysokiej impedancji wejściowej woltomierza.
- Automatyczne ON jest obecnie włączone. Nie wysyłać READ?/MEAS?/INIT w zastanym
  stanie bez przygotowania i weryfikacji konfiguracji oraz połączeń.
- Docelowy plan: tryb źródła prądu 0 A i pomiar V, odpowiednia granica napięcia,
  zakres i czas integracji, jawne sterowanie wyjściem zamiast auto-ON. Potwierdzić
  szczegóły dla B2910BL w instrukcji producenta przed implementacją.
- Następny wątek musi ustalić spodziewane napięcie/polaryzację DUT, połączenia
  Force/Sense oraz odniesienie LO. Nie zakładać połączeń starego egzemplarza.
- Świeże pomiary wymagają odrębnej semantycznej metody drivera z wyzwalaniem,
  kontrolą trybu, statusu/compliance, timeoutów i cleanup. Dodać testy bez sprzętu
  i sprawdzić na znanym napięciu z niezależnym miernikiem.

Status: identyfikacja i odczyt stanu PASS; tryb woltomierza **NOT_TESTED**.
`commissioned:false` i `allow_output:false` pozostają w przykładach. Są to blokady
chronionego API, nie sprzętowe zabezpieczenie przed dowolnym raw SCPI. Limity w
przykładzie nie są zakresem pomiarowym ani zatwierdzeniem parametrów DUT.

Źródła producenta:
- [B2900 User Guide](https://www.keysight.com/us/en/assets/9018-01860/user-manuals/9018-01860.pdf)
- [B2900B/BL SCPI reference](https://www.keysight.com.cn/cn/zh/assets/9921-01285/programming-guides/B2900B-BL-Series-Precision-Source-Measure-Unit-SCPI-Command-Reference.pdf)
