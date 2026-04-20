from datetime import date
from app.models.analysis import EventDefinition


EVENTS: list[EventDefinition] = [EventDefinition(event_id="covid_outbreak", name="WHO declared COVID-19 a pandemic", event_date=date(2020, 3, 11)),
                                 EventDefinition(event_id="ukraine_war", name="The outbreak of war in Ukraine", event_date=date(2022, 2, 24)),
                                 EventDefinition(event_id="svb_collapse", name="The collapse of Silicon Valley Bank", event_date=date(2023, 3, 10)),
                                 EventDefinition(event_id="nbp_first_hike", name="NBP interest rate hike", event_date=date(2021, 10, 6)),
                                 EventDefinition(event_id="fed_first_hike", name="FED interest rate hike", event_date=date(2022, 3, 16)),
                                 EventDefinition(event_id="ecb_first_hike", name="ECB interest rate hike", event_date=date(2022, 7, 21)), ]

