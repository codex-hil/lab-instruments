TimeLab differential regression — analiza offline, 2026-10-31

Uruchamiaj na Dell jako timelab, nigdy jako root. Nie ma akwizycji ani dostępu do
aparatury. Blokada /home/timelab/wr-timing/.run.lock jest współdzielona z launcherem
TimeLab. Nie zmieniono Vivado, Quartus, Docker, usług HIL ani licencjonowania.
AllanTools 2024.06 działa w istniejącym izolowanym venv:
  /home/timelab/wr-timing/venv
Pakiety/wersje i hashe źródła AllanTools są zapisane w manifest.json każdego testu.

Z Optiplex:
  ssh -i ~/.ssh/dell_build -o IdentitiesOnly=yes timelab@192.168.2.7 '/home/timelab/wr-timing/regression/run-regression --label "baseline before update"'

Każdy test tworzy osobny katalog runs/<UTC>-<pid> (bez nadpisywania poprzednich).
Kod wyjścia 0 = PASS wejścia skończonego + zabezpieczeń; 1 = rozbieżność, brak tau,
niekompletny eksport lub nieudana kontrola; 2 = niewłaściwy użytkownik/zajęta lease.
Wygenerowane ścieżki raportu są na końcu logu. Typowy czas: kilka minut, w tym
ograniczony do 60 sekund negatywny test surowych NaN w osobnym klonie prefixu.
Tymczasowy klon prefixu jest usuwany po zatrzymaniu jego wineserver; zachowywane
są wejścia, eksporty i logi. Bieżący właściwy WINEPREFIX pozostaje zachowany.

Po aktualizacji narzędzia, aby UŻYĆ IDENTYCZNYCH ZAPISANYCH DANYCH:
  ssh -i ~/.ssh/dell_build timelab@192.168.2.7 '/home/timelab/wr-timing/regression/run-regression --inputs-from /home/timelab/wr-timing/regression/runs/POPRZEDNI_TEST/inputs --label "TimeLab/AllanTools/driver update: podaj wersję"'
--inputs-from sprawdza SHA256 wszystkich CSV, TIM i surowego zapisu z lukami.
To zalecana metoda porównania wersji; ponowna generacja przy zmianie Python/NumPy
może dać różnice ostatnich bitów np. funkcji sin lub dopasowania wielomianu.
--label zostaje zapisany w manifeście. Sterowniki aparatury nie są używane w tym
teście: jego przejście po ich aktualizacji NIE potwierdza poprawności akwizycji.
--skip-nan-probe pomija diagnostykę TimeLab z NaN i oznacza ją NOT_RUN; nie stosuj
go do pełnej walidacji. Testy ochrony przed NaN/lukami nadal działają.
--run-dir ABS_PATH pozwala wskazać nowy katalog wyników; musi nie istnieć.

Odbiór raportu:
  scp -i ~/.ssh/dell_build timelab@192.168.2.7:/home/timelab/wr-timing/regression/runs/TEST/report.html ./
HTML jest samodzielny (wykresy osadzone, bez serwera HTTP i zewnętrznych zasobów).
Wyniki szczegółowe: results.csv/json; summary.json; events.json; controls.json.
manifest.json: Python, platforma/kernel, Wine, rzeczywisty banner TimeLab,
AllanTools, NumPy, Matplotlib, pip freeze, hashe exe/DLL/analizatorów/skryptów.
inputs/manifest.json: N, dt, jednostki, seed, parametry, współczynniki detrendingu,
polityka luk i hashe. inputs/*.csv i *.tim są zachowane. timelab/* zawiera logi,
pełne siatki tau/eksporty CSV, wybrane obrazy PNG i zapis roundtrip.TIM.

Definicje i uczciwa macierz zgodności:
- TimeLab "ADEV" = OADEV; porównanie z allantools.oadev.
- TimeLab "HDEV" = OHDEV; porównanie z allantools.ohdev.
- Klasyczne allantools.adev i hdev: kontrola niezależna, TimeLab N/A
  (brak odrębnego nienakładającego trybu w udokumentowanym interfejsie).
- MDEV nakładające; TDEV=tau*MDEV/sqrt(3); MTIE=max rozstępu w m+1 próbkach.
- Phase/TIE i TDEV/MTIE w sekundach; ADEV/OADEV/MDEV/HDEV/OHDEV bezwymiarowe.
- Jawne tau=m*dt; porównania na zapisanych koszykach, bez interpolacji wykresu.
  Siatka m dla xDEV: 1,2,4,8,10,20,40,80,100; dla MTIE: 1,2,4,10,20,40,100.
  Potwierdzono, że TimeLab MTIE nie eksportuje m=8 ani m=80. Zawsze m<=N/8.
  Wymagany punkt nieobecny lub podwójny to FAIL. Pełne siatki z TimeLab są w events.
- DEN=29, MIN=4, nominal=1 Hz, UNW=1, skala fazy=1. Brak filtracji i edycji.
  Wyłączone: clipping po bandwidth/confidence, error bars, spline, wizualne
  residual/trend/zerowanie. Zgodność eksportu fazy jest sprawdzana dla każdego
  zapisu (liczba próbek i wartości). Pliki TIM używają nagłówka oficjalnego przykładu;
  pole instrumentu HP5370 jest metadanymi szablonu, nie dowodem pomiaru.
- Detrending: brak domyślnego. Osobny zestaw ma jawne usunięcie wielomianu drugiego
  stopnia przed OBIEMA aplikacjami. Współczynniki, rodzic i metoda zapisane.
  Nie jest to test GUI polecenia natywnego detrendingu TimeLab.

17 zestawów obejmuje zero, liniową fazę, kwadratowy dryft, szum fazy, skumulowane
przyrosty Gaussa, sinusoidę+szum, skok, naprzemienną fazę, dt=0.25 i 2 s,
dryft+szum, jawny detrending, krótki rekord, trzy ciągłe segmenty zapisu z lukami
oraz osobny jawnie interpolowany zapis. Segmenty analizowane są oddzielnie;
nie łączymy ich ani nie uśredniamy wyników xDEV.

Kontrola niezależna: reference.py, bez importów AllanTools/NumPy/TimeLab.
Bezpośrednie różnice drugiego/trzeciego rzędu, jawne średnie okien i MTIE;
Decimal z 60 cyframi na dokładnych wartościach binarnych wejścia, końcowy float.
Kontrole analityczne obejmują fazę liniową/kwadratową oraz ręcznie policzony
wektor [0,1,0,-1,0,1,0,-1] przy m=2, odróżniający non-overlap od overlap.
Tolerancja stała, ustalona przed pierwszym porównaniem: rtol=5e-8, atol=1e-20
(|a-b| <= atol+rtol*|b|). Próg absolutny obejmuje cancellation przy idealnie zerowej
statystyce; nie jest dopasowywany do zaobserwowanych rozbieżności. Raport pokazuje
obie skale błędu i stosunek błędu do tolerancji. Osobna kontrola wstrzykniętego
błędu sprawdza, że mechanizm oceny faktycznie wykrywa niezgodność.

Żadne narzędzie nie jest wzorcem: dla wspólnych statystyk zapisywane są trzy
porównania: TimeLab↔AllanTools, TimeLab↔Decimal i AllanTools↔Decimal.
Rozbieżności pozostają FAIL. Nie aktualizuj automatycznie tolerancji ani baseline.
Najpierw sprawdź jednostki, tau, długość okna, próbki fazy i kontrolę analityczną.
Porównujemy estymaty, nie ich błędy/niepewności ani przedziały ufności.

Brakujące próbki:
- Domyślnie odrzucane: NaN/Inf, nieregularny czas, duplikaty timestampów.
- Nie usuwaj próbek i nie ściskaj osi czasu. Dopuszczalna jawna segmentacja lub
  osobno oznaczona imputacja/interpolacja zmieniają analizowany problem.
- Standardowe wywołania AllanTools dla badanego wektora NaN zwróciły NaN.
- TimeLab dla surowych NaN nie zakończył próby w 60 s; kontrola finite na tym samym
  izolowanym prefiksie zakończyła się poprawnie. Jest to FAIL obsługi tego surowego
  wejścia, nie matematyczna rozbieżność na poprawnych danych. PASS całego harnessu
  obejmuje poprawne odrzucanie brakujących danych i jawne testy segmentów.
- Nie badano gradev ani modeli statystycznych nieregularnego próbkowania.

Odtworzenie zależności naukowych w nowym środowisku (nie globalnie, nie jako root):
  python3.14 -m venv /NOWA/SCIEZKA/venv
  /NOWA/SCIEZKA/venv/bin/pip install -r requirements-lock.txt
Launcher jest przypięty do istniejącej ścieżki venv i instalacji Wine/TimeLab;
przy relokacji dostosuj BASE w regression.py i run-regression. Na tym Dell
nie instalowano ponownie tych samych pakietów: użyto już odizolowanego środowiska.
Zapisany source-snapshot.tar.gz i requirements-lock.txt pozwalają zachować kod
harnessu podczas późniejszych aktualizacji. Artefakty runów są niezależne.

Źródła definicji:
https://allantools.readthedocs.io/en/stable/functions.html
https://www.miles.io/PhaseStation_53100A_user_manual.pdf
https://doi.org/10.6028/NIST.SP.1065
