from datetime import date
from app.models.analysis import EventDefinition


EVENTS: list[EventDefinition] = [
    EventDefinition(event_id="north_korea_us_nuclear_tension", name="North Korea U.S. tension", event_date=date(2017, 8, 8)),
    EventDefinition(event_id="covid_outbreak", name="WHO declared COVID-19 a pandemic", event_date=date(2020, 3, 11)),
    EventDefinition(event_id="opec_plus_oil_production_cuts", name="OPEC+ decision on record oil production cuts", event_date=date(2020, 4, 12)),
    EventDefinition(event_id="nbp_first_hike", name="NBP interest rate hike", event_date=date(2021, 10, 6)),
    EventDefinition(event_id="ukraine_war", name="The outbreak of war in Ukraine", event_date=date(2022, 2, 24)),
    EventDefinition(event_id="fed_first_hike", name="FED interest rate hike", event_date=date(2022, 3, 16)),
    EventDefinition(event_id="ecb_first_hike", name="ECB interest rate hike", event_date=date(2022, 7, 21)),
    EventDefinition(event_id="nord_stream_sabotage", name="Nord Stream sabotage", event_date=date(2022, 9, 26)),
    EventDefinition(event_id="ftx_collapse", name="FTX collapse", event_date=date(2022, 11, 11)),
    EventDefinition(event_id="svb_collapse", name="The collapse of Silicon Valley Bank", event_date=date(2023, 3, 10)),
    EventDefinition(event_id="credit_suisse_collapse_ubs_takeover", name="Credit Suisse collapse and takeover by UBS", event_date=date(2023, 3, 19)),
    EventDefinition(event_id="hamas_attack_on_israel", name="Hamas attack on Israel", event_date=date(2023, 10, 7)),]
