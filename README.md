# NBP Currency System
System do analizy kursów walut na podstawie danych z API Narodowego Banku Polskiego. Realizowany w ramach pracy magisterskiej 

## Technologie
- Python 3.11
- FastAPI
- Pandas
- Streamlit
- NBP API

## Architektura
Projekt oparty na architekturze 3-warstwowej:
```
NBP API → FastAPI backend → Streamlit frontend
```

## Endpointy
- `GET /currencies/{code}` — aktualny kurs waluty
- `GET /currencies/{code}/history?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` — historyczne kursy w zakresie dat

## Obsługiwane waluty
- EUR/PLN
- USD/PLN
- CHF/PLN

## Uruchomienie
uvicorn app.main:app --reload



