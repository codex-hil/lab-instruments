# FCA3003 — próby na Raspberry Pi, 2026-10-09

**Status PARTIAL.** To rzeczywisty sprzęt, nie emulator. Identyfikacja i poprawna
obsługa timeoutu są potwierdzone; nie uzyskano poprawnego wyniku pomiarowego.

Stanowisko: RPI-USBTMC `192.168.2.36`, Linux 6.18.50+rpt-rpi-v8 / aarch64,
Python 3.13.5. FCA3003: USB `0699:3003`, serial `442678`, firmware
`V1.31 06 Mar 2015 12:55`. Generator AFG1062: serial `1544477`;
użytkownik potwierdził połączenie **B/CH2 AFG1062 → A FCA3003**.

| Próba | Wynik | Dowód |
|---|---|---|
| USBTMC `*IDN?` i model/serial | PASS | [wejście A](hil-input-a.json) |
| HTTPS → USBTMC identyfikacja | PASS | [bramka](hil-gateway.json) |
| Timeout firmware: pusty READ, bit 1024, SCPI -230 | PASS obsługi błędu | [bramka](hil-gateway.json), test regresyjny |
| A: generator 1 kHz, 100 kHz, 1 MHz | NO_TRIGGER, wynik niewalidowany | [próby](hil-sweep.json) |
| Wewnętrzna referencja, kanał 6 | TIMEOUT | [pierwsza próba](hil-reference-before-timeout-fix.json) |
| Przywrócenie częstotliwości AFG CH2 do 1 MHz | PASS readback | [próby](hil-sweep.json) |
| Biblioteka na RPi | 42 testy PASS | [status](status.json) |

FCA3003 pokazał [„No trig or Tout”](counter-no-trigger.png). Wejście A miało
AC, 1 MΩ, tłumienie ×1, autotrigger ON, filtr OFF i zbocze POS. Również
3-sekundowy timeout nie dał wyniku. Generator zgłaszał CH2 ON, SIN, CW,
amplitudę `1.000000e+00` i offset 0; ta próba nie dowodzi fizycznej obecności
sygnału na kablu. Rzeczywista przyczyna braku wyzwalania nie jest ustalona.
Próby B/C także zgłosiły timeout, ale nie miały potwierdzonego źródła sygnału.

Pierwsza próba wywołała `InstrumentError` zamiast `TimeoutError`, bo firmware
oprócz bitu timeoutu zwraca błąd SCPI `-230,"Data corrupt or stale"`.
Driver poprawiono: bit timeoutu ma pierwszeństwo, a kod SCPI zachowujemy
w komunikacie wyjątku. Odpowiedź `READ?` to pojedynczy LF, nie wartość NaN.
Test regresyjny odtwarza ten zestaw odpowiedzi. Plik pierwszej próby zachowano
jako dowód zachowania sprzed poprawki.

Na RPi umieszczono kod w `/home/usbtmc/fca3003-driver`, dodano stabilny slot
`fca3003` do `/etc/labinst/config.json` oraz regułę udev ograniczoną do
VID/PID/serialu licznika. Zrestartowano istniejącą usługę `labinst.service`.
Kopie obu zmienionych plików mają sufiks `.before-fca3003-20261009`.
Bramka działa na `https://192.168.2.36:8840`; token i certyfikat pozostają
na stanowisku. Nie zmieniano kodu serwera ani ustawień pozostałych slotów.

Próba częstotliwości zmieniała jedynie częstotliwość generatora CH2;
przywrócono początkowe 1 MHz. Nie zmieniano jego amplitudy, offsetu, funkcji
ani stanów wyjść. Konfiguracja pomiaru licznika została zmieniona przez driver.

Reprodukcja po potwierdzeniu sygnału na wejściu A:

```sh
ssh usbtmc@192.168.2.36
cd /home/usbtmc/fca3003-driver
sudo python3 scripts/hil-fca3003.py --usb-serial 442678 --serial 442678 \
  --channel 1 --expected-hz 1000000 --output /tmp/fca3003-hil.json
```

Nadal wymagane: poprawny pomiar sygnału, następnie testy pozostałych wejść,
funkcji czasowych, duty cycle, napięcia i par kanałów. Nie wykonano kalibracji.
