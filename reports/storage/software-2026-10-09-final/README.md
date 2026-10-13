# Storage software validation — 2026-10-09

**PASS: 117 testów**, w tym **37 nowych testów storage**, w przypiętym środowisku Nix.
Wszystkie testy storage są **TESTED / SIMULATED**. Bmaptool zapisuje prywatny plik
mocka; testy USB używają syntetycznego sysfs i mock stat, nigdy rzeczywistego dysku.
Nie przeprowadzono hardware HIL. USB discovery na tym hoście: brak SDWire.

- [report.json](report.json): wyniki CLI, źródłowe SHA256, wersja Python, status sprzętu.
- [software-tests.log](software-tests.log): pełne wyniki wszystkich 117 testów, bez skip.
- [operations.jsonl](operations.jsonl): audyt symulowanych transakcji CLI.
- [zynq-simulated/result.json](zynq-simulated/result.json): symulowany build/update/boot/health PASS.
- [zynq-simulated/uart.bin](zynq-simulated/uart.bin): pełny odebrany UART, jawnie SIMULATED.

Polecenie odtworzenia (nowy katalog, nie nadpisywać raportu):

```sh
nix --extra-experimental-features 'nix-command flakes' develop path:. --command \
  python3 scripts/validate-storage.py --output local/storage-replay
```

Mock urządzenia/obrazy zostały utworzone w temporary directory i usunięte po testach.
Ścieżki w raporcie dotyczą tego przebiegu i nie są konfiguracją realnego sprzętu.
Nix x86_64 build kontrolera sd-mux-ctrl i launchera hil-storage przeszedł.
Build istniejącego zipapp labinst.pyz również przeszedł; Python bez bmaptool pomija
jeden test bmaptool (pełny raport Nix powyżej nie pomija żadnego).

Realny backend jest blokowany przez brak trwałego OFF w legacy 3mdeb SDWire.
[Research i ograniczenia](../../../docs/sdwire.md),
[bring-up](../../../docs/sdwire-bringup.md).
