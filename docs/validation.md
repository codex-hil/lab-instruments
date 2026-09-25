# Walidacja 0.1

- Testy jednostkowe/integracyjne: walidacja limitów i mocy, niepoprawne kanały/typy,
  NaN/Infinity/injection, wymagana tożsamość, pełny stan, readback, OFF przy błędzie,
  fault latch, wygaśnięcie lease, odrzucenie raw route, auth/TLS, ramkowanie binarne,
  CR terminator, USB EOM, hotplug/duplikaty serialu, profile źródeł na symulatorach.
- HIL identyfikacji: 10 przyrządów odpowiedziało; 6487 przez Waveshare timeout.
  B&K i MSO2002B nie były podłączone do testowanego interfejsu. Raport zachowuje błąd,
  zamiast traktować inwentarz jako dowód łączności.
- Zbudowany `.pyz` zidentyfikował AFG1062 po rzeczywistym USBTMC z odczytem EOM ioctl.
- Unit systemd sprawdzony przez `systemd-analyze verify`; skrypty shell przez `sh -n`.
- `scripts/replay.sh <revision>` wykonuje build z czystego archiwum Git.
- CI sprawdza Python 3.11/3.12/3.13 na Linux x86-64; nie zastępuje próby na RPi/ARM.

Nie wykonano na sprzęcie: nowego API `apply`, wygaśnięcia lease przy aktywnym źródle,
awarii podczas źródłowania, transferu dużego przebiegu, czterech USB naraz, instalacji
root, zmian firewalla ani PoE/RPi. To punkty odbioru przed `commissioned=true`.
Nie wgrywano firmware'u, nie zmieniano limitów rzeczywistych zasilaczy.
