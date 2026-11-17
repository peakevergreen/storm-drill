"""Bundled call scenarios. Every caller is invented."""
import json
from importlib.resources import files

RECORD_FIELDS = (
    "caller_name", "callback_number", "relationship", "service_address", "unit",
    "billing_address", "problem", "existing_job", "access_notes", "availability", "authorizer",
)
OUTCOMES = {"request_taken", "booked", "transferred", "abandoned"}


def load_scenarios():
    document = json.loads(files("stormdrill").joinpath("data/scenarios.json").read_text(encoding="utf-8"))
    return document["version"], {item["id"]: item for item in document["scenarios"]}


def observation_names(scenario):
    expect = scenario["expect"]
    return [*expect["must"], *expect["must_not"]]
