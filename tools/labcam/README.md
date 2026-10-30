# LABCAM — kamery jako instrumenty laboratoryjne

Wspólny punkt wejścia dla kolejnych wątków i agentów. Kod, registry, dokumentacja
oraz dowody pomiarów są w osobnym [repozytorium LABCAM](https://github.com/codex-hil/labcam).
Nie tworzymy tutaj drugiego sterownika ani niezależnej bazy tożsamości.

Host: **Optiplex `greg-OptiPlex-3070`**, katalog `/home/codex-hil/labcam`.
Przeczytaj tam `AGENTS.md`, `README.md` i `docs/CAMERAS.md`.
[Inventory JSON](inventory.json) jest migawką indeksu; źródłem aktualnej konfiguracji
pozostaje `/home/codex-hil/labcam/registry.json`.

| ID | alias | MAC | ostatnio znany IP | stan wiedzy |
|---|---|---|---|---|
| CAM01 | printer-3d | 02:14:ee:60:5e:60 | 192.168.2.8 (2026-10-14) | historyczny snapshot PASS; test 72 h zatrzymany, bieżąca dostępność niepotwierdzona |
| CAM02 | Labcam2 | 02:20:f7:c0:fa:fc | 192.168.2.23 (2026-10-30) | snapshot, RTSP decode i klip 10,02 s PASS; pełny soak nieprzeprowadzony |

Obie: Wyze Cam 2 / T20X / JXF23 / RTL8189FTV, Thingino stable+0598a56.
CAM02 ma potwierdzone H.264 1920×1080 i 640×360, deklarowane 25 FPS.
Jej fizyczna lokalizacja jest jeszcze nieprzypisana; bieżący obraz pokazuje laboratorium.
CAM02 należy oznaczyć na obudowie numerem CAM02.

```sh
labcam list
labcam snapshot Labcam2
labcam health Labcam2
labcam record Labcam2 --duration 10
labcam snapshot printer-3d
```

CLI działa na Optiplex; inne stacje nie mają automatycznie kodu ani credentials.
API na Optiplex: `http://127.0.0.1:8765/cameras/Labcam2/snapshot`.
Podgląd lokalny: `http://127.0.0.1:8765/`.
WebUI CAM02: `http://192.168.2.23/preview.html`;
RTSP: `rtsp://192.168.2.23:554/ch0` i `/ch1`, z uwierzytelnieniem.
Adresy mogą zmienić się przez DHCP; zawsze identyfikuj po MAC, nie po samym IP.

Credentials są wyłącznie lokalnie w ignorowanym `.secrets/credentials.json`.
Nie publikuj ich i nie wysyłaj do urządzenia pod niezweryfikowanym adresem.
Do HIL preferuj natywny snapshot. Po akcji odczekaj na aktualizację JPEG;
nie traktuj timestampu pobrania jako czasu ekspozycji. Artefakty są w
`/home/codex-hil/labcam/data/CAMxx/` z metadanymi JSON.

Przed kolejnym soak sprawdź istniejącą usługę `labcam-soak@CAMxx` i blokadę
`data/CAMxx/soak/run.lock`; nie nadpisuj poprzednich wyników ani nie uruchamiaj
duplikatu. CAM01 miał błędy H.264, problemy timestampów i zmianę DHCP;
stabilność 72 h nie jest potwierdzona. Nie resetuj ani nie zmieniaj firmware,
ustawień lub orientacji kamery bez zakresu zadania obejmującego te zmiany.
Dostęp do obrazu nie upoważnia do uruchamiania drukarki, aktuatorów ani zasilania.
