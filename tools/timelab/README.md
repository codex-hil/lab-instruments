# TimeLab pod Wine — analiza offline

TimeLab Johna Milesa na Dell, automatyczny eksport i regresja względem AllanTools
oraz niezależnych obliczeń Decimal. To opcjonalne narzędzie z własnym venv;
nie zmienia zależności podstawowej biblioteki `labinstruments`.

## Stan potwierdzony

Ubuntu 26.04.1 x86-64, Wine 10.0, TimeLab 1.79A Beta x64. Konto `timelab`
bez sudo, osobny `/home/timelab/.wine-timelab`. Pliki na Dell:
`/home/timelab/wr-timing`. Wykresy wymagają natywnego GDI+ 1.1 z Microsoft
KB3065979 i Arial w tym prefiksie. Xvfb działa z wyłączonym TCP.

**PASS:** 17 zestawów, 2290 porównań, zero przekroczeń tolerancji, 86 kontroli
skalowania jednostek. Ponowne użycie zarchiwizowanych wejść dało bitowo identyczne
CSV wynikowe. Kontrole analityczne i celowo wprowadzony błąd również sprawdzone.
Tolerancja: `|a-b| <= 1e-20 + 5e-8*|b|`, w jednostkach danej statystyki.

- TimeLab „ADEV” porównujemy z **OADEV**, „HDEV” z **OHDEV**.
- Klasyczne ADEV/HDEV: AllanTools kontra Decimal; TimeLab **N/A** — brak osobnego
  nienakładającego trybu w udokumentowanym interfejsie.
- Wspólne MDEV, TDEV i MTIE są porównane we wszystkich trzech parach narzędzi.
- **Surowe NaN: FAIL obsługi tego wejścia** — TimeLab przekroczył 60 s przy
  poprawnej kontroli finite na tym samym klonie prefixu; standardowe wywołania
  AllanTools zwróciły NaN. Harness odrzuca takie wejście. Jawne segmenty oraz
  osobno oznaczona interpolacja są przetestowane. Nie ściskamy osi czasu.
- Detrending jest domyślnie wyłączony; osobny test usuwa wielomian przed obiema
  aplikacjami. Natywnego polecenia detrendingu GUI nie walidowano.

[Samodzielny raport HTML](evidence/baseline-2026-10-31/report.html),
[status JSON](evidence/baseline-2026-10-31/summary.json),
[szczegółowe CSV](evidence/baseline-2026-10-31/results.csv),
[odtwarzanie bitowo identycznych wyników](evidence/baseline-2026-10-31/replay-check.json).
HTML trzeba pobrać i otworzyć lokalnie; GitHub nie renderuje go jak strony WWW.

## Uruchomienie istniejącej instalacji przez SSH

Z Optiplex, z istniejącym kluczem pozostającym na Optiplex:

```sh
ssh -i ~/.ssh/dell_build -o IdentitiesOnly=yes timelab@192.168.2.7 \
  '/home/timelab/wr-timing/scripts/timelab-run export /home/timelab/wr-timing/evidence/imported-pps.tim /home/timelab/wr-timing/results/my-run'
```

Eksportuje ADEV/OADEV i TDEV do CSV/PNG oraz zapisuje TIM. Bez klikania, roota
czy mojego udziału. Nie ma harmonogramu ani uruchomionej usługi TimeLab.
Interaktywne GUI: `ssh -X` z terminala mającego działające lokalne X11/xauth,
a następnie `scripts/timelab-run gui INPUT.tim`. GUI potwierdzono na Xvfb;
pełnej sesji interaktywnej przez SSH nie zweryfikowano z sesji narzędziowej.

[Obsługa eksportu i konwersji fazy](SSH-USAGE.txt).

## Regresja po aktualizacji

```sh
ssh -i ~/.ssh/dell_build -o IdentitiesOnly=yes timelab@192.168.2.7 \
  '/home/timelab/wr-timing/regression/run-regression --inputs-from /home/timelab/wr-timing/regression/latest/inputs --label "po aktualizacji narzędzi"'
```

Nowy katalog `regression/runs/<UTC>-<pid>` zawiera raport HTML z wykresami różnic,
CSV/JSON, logi, wersje i hashe narzędzi oraz wejścia. Kod wyjścia 0 oznacza PASS
skończonych danych i zabezpieczeń, 1 — rozbieżność/błąd, 2 — zajętą blokadę lub
nieodpowiedniego użytkownika. Nie aktualizujemy automatycznie tolerancji.

Każdy test blokuje tę samą `.run.lock` co zwykły launcher. Próba NaN używa
oddzielnego tymczasowego klonu prefixu, z ograniczeniem czasu i sprzątaniem.
Nie podłącza ani nie steruje aparaturą. Przejście po aktualizacji sterownika
**nie potwierdza poprawności akwizycji**. Testy są krótkie, nie wielogodzinne.

[Pełna instrukcja, definicje i polityka luk](regression/README.txt).

## Kod z repo a instalacja na Dell

Repo jest źródłem kodu; ścieżki w launcherach są celowo zgodne z istniejącą
instalacją Dell. Po przeglądzie zmian można skopiować `scripts/` i `regression/`
do `/home/timelab/wr-timing/` jako użytkownik `timelab`, zachowując aplikację,
venv, prefix i wcześniejsze wyniki. Nie kopiować katalogów całego narzędzia
wprost na instalację ani nie nadpisywać cudzej aktywnej sesji; sprawdzić `.run.lock`.
Archiwalne dane z `evidence/baseline-2026-10-31/inputs` można wskazać przez
`--inputs-from` po skopiowaniu ich na Dell. `latest` na aktualnym Dell wskazuje
zarchiwizowaną bazę, nie jest automatycznie przesuwany po kolejnych testach.

`bootstrap-root.sh` przygotowuje pakiety systemowe i konto, **nie wykonuje pełnej
instalacji TimeLab ani Wine jako root**. Nowa maszyna wymaga dodatkowo:

1. Pobrania TimeLab z [oficjalnego źródła](https://www.miles.io/timelab/beta.htm)
   i rozpakowania `innoextract -d app downloads/beta.exe` jako `timelab`.
2. Utworzenia osobnego WINEPREFIX jako `timelab` na Xvfb.
3. Wydzielenia GDI+ 1.1 x64 z oficjalnego
   [KB3065979](https://www.microsoft.com/en-us/download/details.aspx?id=47320),
   SHA256 sprawdzonego DLL:
   `222095f88914695b96330e4f5f9ff7a55d670b1117ae378b636ac0daea638ccd`.
   `decode-msdelta.py` odtwarza pliki PA30 z rozpakowanego pakietu; wymaga
   przenośnego Python Windows i natywnego `msdelta.dll`. Nie instaluje .NET/Windows.
4. Dodania Arial do tego prefixu i używania `WINEDLLOVERRIDES=gdiplus=n,b` tylko
   dla TimeLab. Wine built-in dawał białe obrazy, GDI+ z Windows 10 gubił tekst.
5. Utworzenia izolowanego venv; sprawdzony Python 3.14.4 i
   `pip install -r regression/requirements-lock.txt`. Nie instalować globalnie.

Instalatory, czcionki, DLL, Wine i venv nie są wersjonowane w tym repo.
Starszy [raport uruchomienia](REPORT.txt) opisuje pierwszą walidację.
Bieżące dane referencyjne regresji i ich źródła/hashe są w `evidence/`.
Historyczny manifest i `source/` opisują dokładnie kod uruchomiony 31 października;
obecny wrapper ma uporządkowaną zmienną WINEPREFIX zgodną z rzeczywistym prefiksem
używanym już wtedy przez silnik Python. Nie zmieniono wzorów ani tolerancji.

## Zawartość i granice dowodów

Zachowano deterministyczne CSV/TIM, parametry generacji, źródła historycznej
walidacji, kontrole analityczne, wyniki porównań i logi próby NaN/kontroli finite.
Pierwotne logi wszystkich sesji, instalatory i pełne środowisko pozostają na Dell
w `/home/timelab/wr-timing`; nie publikujemy ich jako części kodu narzędzia.
Zestawy są syntetyczne, nie są pomiarami z częstotliwościomierza/VNA.
Pole HP5370 w TIM pochodzi z szablonu producenta i nie identyfikuje aparatury.
