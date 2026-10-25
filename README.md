# NBP Currency System

Aplikacja do analizy kursów walut i ich zmian w otoczeniu wybranych wydarzeń,
realizowana w ramach pracy magisterskiej. Dane pochodzą z tabeli A kursów średnich
[NBP Web API](https://api.nbp.pl/).

## Funkcje

- Odczyt ostatniego dostępnego kursu waluty.
- Historia kursów w wybranym okresie, prezentowana w tabeli i na wykresie.
- Analiza zmiany kursu przed pojedynczym wydarzeniem i po nim.
- Analiza zdefiniowanych wydarzeń oraz porównanie krótkiego i długiego okna.

Aplikacja przyjmuje trzyliterowe kody walut z tabeli A, np. `EUR`, `USD`, `CHF`.
Dostępność danych dla konkretnej waluty i okresu zależy od NBP.

## Technologie i struktura

Python 3.11+, FastAPI, Pydantic, HTTPX, Pandas, Streamlit, holidays i pytest.

```text
Streamlit → FastAPI → NBP API
```

| Ścieżka | Odpowiedzialność |
| --- | --- |
| `app/main.py` | Aplikacja FastAPI i cykl życia klienta HTTP |
| `app/routers/` | Endpointy i walidacja parametrów HTTP |
| `app/models/` | Modele odpowiedzi Pydantic |
| `app/services/nbp_api.py` | Pobieranie kursów, ponawianie zapytań i cache |
| `app/services/analysis_service.py` | Okna dni roboczych i obliczenia zmian kursu |
| `app/services/pandas_analysis.py` | Zestawienia wydarzeń i porównanie okien |
| `app/services/validation.py` | Wspólna walidacja dat i rozmiarów okien |
| `app/services/events.py` | Lista wydarzeń wykorzystywana w analizach zbiorczych |
| `streamlit_app/ui.py` | Interfejs użytkownika |
| `tests/` | Testy walidacji, obliczeń, API, cache i interfejsu |
| `do pisania/` | Opis techniczny implementacji, struktura i wynik przeglądu do pracy |

## Instalacja i uruchomienie lokalne

Polecenia wykonuj z katalogu głównego projektu. Pobieranie rzeczywistych kursów
wymaga połączenia z internetem.

### Środowisko i zależności

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[backend,frontend,test]"
```

W PowerShell środowisko aktywuje się poleceniem `.venv\Scripts\Activate.ps1`.
Na Windows polecenie tworzące środowisko można wykonać jako `py -3.11 -m venv .venv`.

Grupy zależności są zdefiniowane w [pyproject.toml](pyproject.toml). Można zainstalować
sam backend (`.[backend]`) lub frontend (`.[frontend]`). Plik
[requirements.txt](requirements.txt) zawiera pełny zestaw przypiętych zależności
wykorzystywany również przez obrazy kontenerów.

### Backend

```bash
python -m uvicorn app.main:app --reload
```

- API: <http://127.0.0.1:8000>
- Swagger UI: <http://127.0.0.1:8000/docs>
- Schemat OpenAPI: <http://127.0.0.1:8000/openapi.json>

### Frontend

W drugim terminalu aktywuj to samo środowisko i uruchom:

```bash
python -m streamlit run streamlit_app/ui.py
```

Otwórz <http://localhost:8501>. W panelu bocznym rozwiń **Connection**, ustaw
**Backend URL** na `http://127.0.0.1:8000` i wybierz **Check backend**.
Domyślna wartość `http://nbp-app-backend:8000` służy do komunikacji w sieci kontenerów.

Interfejs ma jasną kolorystykę i pola formularzy ułożone w kolumnach. Wyniki
prezentowane są przede wszystkim jako metryki i wykresy, z tabelami notowań oraz
porównania wydarzeń. Surowa odpowiedź API jest dostępna po rozwinięciu
**Response details**.

Wykresy mają jawne ustawienia osi w Vega-Lite. Historia i pojedyncze wydarzenie
pokazują kursy na osi dopasowanej do danych z marginesem; podpis informuje,
że skala może zaczynać się powyżej zera. W porównaniu wydarzeń pełne nazwy są
zawijane do kilku wierszy, a obie serie korzystają ze wspólnej skali procentowej,
symetrycznej względem zera. Tooltip pokazuje nazwę, okno i dokładną zmianę.

### Kontenery

Plik [compose.yaml](compose.yaml) buduje backend według
[Containerfile.backend](Containerfile.backend), a frontend według
[Containerfile.frontend](Containerfile.frontend). Z katalogu głównego wykonaj:

```bash
podman compose up --build -d
```

Na macOS maszyna Podman musi być uruchomiona. `podman compose` wymaga dostawcy
Compose, np. Docker Compose lub podman-compose. Plik `compose.yaml` jest
wykrywany automatycznie; jawny wariant to
`podman compose -f compose.yaml up --build -d`.

Frontend jest dostępny pod <http://localhost:8501>, backend pod
<http://localhost:8000>. Usługi komunikują się we wspólnej sieci przez nazwę
`nbp-app-backend`. Przy uruchamianiu frontend oczekuje na pomyślny healthcheck
backendu, który odpytuje `/`. Ten test sprawdza odpowiedź FastAPI, a nie NBP.

```bash
podman compose ps
podman compose logs -f
podman compose stop
podman compose start
```

`stop` zatrzymuje kontenery, a `start` uruchamia je ponownie. Po zmianie kodu
wykonaj ponownie `up --build -d`, ponieważ pliki są kopiowane do obrazów.
`podman compose down` usuwa kontenery i sieć projektu. Cache RAM znika po
zakończeniu procesu backendu, także przy zatrzymaniu przez `stop`.

## Endpointy

Wszystkie endpointy używają metody `GET`.

| Ścieżka | Parametry zapytania | Wynik |
| --- | --- | --- |
| `/` | — | Potwierdzenie działania backendu |
| `/currencies/{code}` | — | Ostatni dostępny kurs i data jego publikacji |
| `/currencies/{code}/history` | `start_date`, `end_date` | Kursy w zadanym zakresie |
| `/analysis/event-impact` | `code`, `event_date`, `days_before=7`, `days_after=7` | Analiza pojedynczego wydarzenia |
| `/analysis/events-impact` | `code`, `window_business_days=7` | Analiza wydarzeń z `events.py` |
| `/analysis/events-impact-compare` | `code`, `short_window=7`, `long_window=21` | Porównanie okien dla wspólnych wydarzeń |

Wartości po `=` oznaczają domyślne ustawienia; pozostałe parametry są wymagane.
Daty podaje się w formacie `YYYY-MM-DD`.

Przykładowe zapytania:

```bash
curl "http://127.0.0.1:8000/currencies/USD"
curl "http://127.0.0.1:8000/currencies/USD/history?start_date=2024-06-01&end_date=2024-06-30"
curl "http://127.0.0.1:8000/analysis/event-impact?code=USD&event_date=2022-02-24&days_before=7&days_after=7"
curl "http://127.0.0.1:8000/analysis/events-impact-compare?code=USD&short_window=7&long_window=21"
```

## Sposób obliczeń

Okno analizy wyznaczane jest w dniach roboczych, z pominięciem weekendów i polskich
świąt obsługiwanych przez bibliotekę `holidays`. Dzień wydarzenia nie jest liczony
jako dzień przed wydarzeniem ani po nim.

- `before_rate`: ostatni dostępny kurs **przed** datą wydarzenia, w wyznaczonym oknie.
- `after_rate`: ostatni dostępny kurs **po** dacie wydarzenia, w wyznaczonym oknie.
- `before_date` i `after_date`: rzeczywiste daty wybranych notowań.
- `window_rates`: dostępne notowania z całego okna, również z dnia wydarzenia,
  jeśli takie notowanie istnieje.

```text
abs_change = after_rate - before_rate
pct_change = (after_rate - before_rate) / before_rate × 100
```

`abs_change` oznacza zmianę nominalną z zachowaniem znaku. Przykładowo:

| Kurs przed | Kurs po | `abs_change` | `pct_change` |
| --- | --- | --- | --- |
| 4,00 | 4,10 | +0,10 | +2,5% |
| 4,00 | 3,90 | −0,10 | −2,5% |
| 4,00 | 4,00 | 0,00 | 0% |

API zaokrągla obie zmiany do trzech miejsc po przecinku. Procent obliczany jest
przed zaokrągleniem zmiany nominalnej. Interfejs pokazuje kursy do czterech miejsc
po przecinku, zmiany nominalne do trzech, a procentowe do dwóch. Format dwóch miejsc
dotyczy procentów w metryce, tabeli porównania oraz na osi i w podpowiedziach wykresu
porównawczego. Przy zmianach widoczne są znaki oraz jednostki: PLN dla zmiany nominalnej
i % dla procentowej. Podgląd JSON w **Response details** zawiera zmiany
zaokrąglone przez API do trzech miejsc po przecinku.

Parametr `days_before` określa zakres poszukiwania kursu bazowego; bazą pozostaje
notowanie najbliższe wydarzeniu od strony wcześniejszych dat. `days_after` określa
horyzont końcowego notowania. Domyślne okna porównawcze obejmują odpowiednio
7 i 21 dni roboczych po każdej stronie wydarzenia.

Porównanie siły zmian wykorzystuje ich wartości bezwzględne: spadek o 5% jest
silniejszy niż wzrost o 2,5%. Wynik obejmuje pola:

- `pct_change_short`, `pct_change_long`: zmiany procentowe w obu oknach.
- `abs_change_short`, `abs_change_long`: zmiany nominalne w obu oknach.
- `is_short_stronger_pct`: `short`, `long` albo `equal`.
- `is_short_stronger_abs`: `true`, gdy zmiana nominalna w krótkim oknie jest
  silniejsza; `false` przy remisie lub silniejszej zmianie w długim oknie.

Porównywane są wartości zaokrąglone przez analizę do trzech miejsc po przecinku.
Analiza zbiorcza pomija wydarzenia bez potrzebnych notowań. Porównanie zawiera
wydarzenia dostępne w obu oknach; przy braku wyników zwraca pustą listę.

Wyniki opisują zmiany kursów w otoczeniu wydarzeń. Ustalenie ich związku
przyczynowego wymaga dodatkowej metodologii badawczej.

## Walidacja i błędy

| Parametr | Reguła |
| --- | --- |
| `code` | Dokładnie trzy litery ASCII; kod jest zamieniany na wielkie litery |
| Daty | Od `2002-01-02` do bieżącej daty serwera, `start_date <= end_date` |
| Zakres dat | Różnica `end_date - start_date` nie większa niż 367 dni kalendarzowych |
| Liczba dni roboczych | Każde pole od 1 do 367 |
| Porównanie okien | `long_window > short_window` |

Limit zakresu dotyczy także pełnego okna po przeliczeniu dni roboczych na daty.
Poprawna wartość pojedynczego pola nie gwarantuje, że całe okno mieści się w limicie
i dostępnych datach. Niepoprawny zakres jest odrzucany przed pobraniem danych z NBP.

Modele kursów sprawdzają poprawność dat (`date`, także `effectiveDate`) oraz
wymagają dodatnich, skończonych wartości (`Field(gt=0, allow_inf_nan=False)`).
Nieprawidłowe dane NBP dają kontrolowany HTTP 500 z komunikatem
`Invalid response from NBP API` i nie trafiają do cache.

| Kod HTTP | Znaczenie |
| --- | --- |
| `200` | Poprawna odpowiedź |
| `400` | Niedozwolony zakres dat, kolejność okien lub błąd zapytania do NBP |
| `404` | Brak waluty albo wymaganych notowań |
| `422` | Niepoprawny format parametrów lub wartość poza limitem pola |
| `500` | Błąd wewnętrzny albo nieprawidłowa odpowiedź NBP |
| `503` | Niedostępność API zewnętrznego |

### Limit aplikacji a limit NBP

[Dokumentacja NBP](https://api.nbp.pl/) podaje limit 93 dni na pojedyncze zapytanie.
Aplikacja dopuszcza różnicę dat do 367 dni i dzieli zakres na kolejne części
obejmujące najwyżej 93 dni kalendarzowe, licząc obie daty graniczne. Następna część
zaczyna się dzień po końcu poprzedniej, bez luk ani nakładania zakresów.

Przykładowo zakres `2024-01-01`–`2024-04-03` jest pobierany jako
`2024-01-01`–`2024-04-02` oraz `2024-04-03`–`2024-04-03`.
Wyniki są łączone, porządkowane według daty i pozbawiane powtórzonych dat notowań.
Ten sam mechanizm obsługuje historię i okna analiz wydarzeń.

Część bez notowań (HTTP 404, np. sam weekend) jest pomijana. Brak notowań w całym
zakresie zwraca HTTP 404, z rozróżnieniem nieznanej waluty i braku danych w okresie.
Pozostałe błędy przerywają pobieranie; częściowy wynik nie jest zwracany ani
zapisywany w cache.

## Cache i połączenie z NBP

Aktualny kurs każdej waluty jest przechowywany w pamięci przez pięć minut od
udanego pobrania. Po tym czasie następne zapytanie odświeża dane. Czas ważności
określa `CURRENT_RATE_CACHE_TTL_SECONDS` w `app/services/nbp_api.py`.

Historia jest zapamiętywana według waluty i dokładnego zakresu dat, po pomyślnym
pobraniu wszystkich części. Zakres kończący się dzisiaj ma czas ważności pięciu
minut od udanego pobrania, określony przez
`HISTORY_CACHE_TTL_SECONDS` w `app/services/nbp_api.py`. Po wygaśnięciu wpisu następne
zapytanie pobiera dane ponownie, co pozwala uwzględnić nowe notowanie bez restartu.
Błąd pobrania nie przedłuża ważności wpisu.

Czas ważności takiego wpisu obowiązuje również po zmianie dnia, także gdy pobieranie
rozpoczęło się przed północą i zakończyło po niej. Zakresy w całości historyczne
w chwili rozpoczęcia pobierania są przechowywane bez wygaszania. Cache działa osobno
w każdym procesie i znika po jego restarcie.

Historia ma limit `HISTORY_CACHE_MAX_ENTRIES = 500`: jeden wpis oznacza walutę
i dokładny zakres dat, wraz z całym szeregiem kursów. Po zapisaniu 501. różnego
klucza usuwany jest najwcześniej dodany (FIFO). Trafienie cache ani nadpisanie
istniejącego klucza nie zmienia kolejności. Wartość 500 jest przyjętym limitem
konfiguracyjnym, bez pomiaru optymalnego zużycia pamięci. TTL nie usuwa wpisów
okresowo; decyduje, czy można ponownie wykorzystać ich dane. Analizy jednego
i wielu wydarzeń korzystają z tego samego cache historii.

Klient HTTP ma timeout pięciu sekund. Błędy połączenia oraz odpowiedzi `500` i `503`
są ponawiane do trzech prób, z dwusekundową przerwą między próbami. Części historii
są pobierane kolejno, a ponowienia dotyczą tylko aktualnie pobieranej części.
Interfejs używa timeoutu 30 sekund dla zwykłych zapytań i 300 sekund dla porównania wydarzeń.
Przy wolnych odpowiedziach NBP i ponawianiu zapytań analiza może przekroczyć ten czas.

## Testy

Po instalacji grup `backend`, `frontend` i `test` uruchom:

```bash
python -m pytest -q
```

Same testy wartości obliczeń:

```bash
python -m pytest -q tests/test_analysis_calculations.py
```

Testy obejmują walidację danych i granic zakresów, dni robocze i święta, obsługę
brakujących danych, podział historii na części do 93 dni, cache, endpointy oraz interfejs.
Testy obliczeń sprawdzają wzrost, spadek, brak zmiany, zaokrąglanie, wybór notowań
oraz siłę zmian i remisy między oknami.
Kursy wejściowe są podstawiane, a obliczenia wykonywane przez rzeczywiste funkcje
aplikacji. Zestaw testów nie wymaga połączenia z NBP.

Testy interfejsu są pomijane, jeśli Streamlit nie jest zainstalowany. Pełne
środowisko z instrukcji instalacji pozwala uruchomić również te testy.

Testy wykresów sprawdzają scenariusze Streamlit i specyfikacje Vega-Lite,
w tym pełne nazwy wydarzeń i skalę dla stałych lub zerowych wartości.
Nie zastępują wizualnego sprawdzenia strony w przeglądarce.

## Materiały do pracy

- [Opis techniczny implementacji](<do pisania/opis_techniczny_implementacji.txt>)
- [Aktualna struktura i przepływ danych](<do pisania/struktura_projektu.md>)
- [Wynik przeglądu i zakres weryfikacji](<do pisania/przeglad_koncowy.md>)
