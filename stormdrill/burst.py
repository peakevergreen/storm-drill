"""Plan a burst of calls, the way they arrive after a storm."""
from .scenarios import load_scenarios

# Calls a tester can place back to back without setup between them.
ROTATION = ("after-hours-ac", "price-question", "out-of-state-owner", "wants-human", "gate-code", "dropped-call")


def burst_plan(calls=20, minutes=10.0, lines=4):
    if not (isinstance(calls, int) and 1 <= calls <= 500):
        raise ValueError("calls must be a whole number from 1 to 500")
    if not 0 < minutes <= 240:
        raise ValueError("minutes must be above 0 and at most 240")
    if not (isinstance(lines, int) and 1 <= lines <= 50):
        raise ValueError("lines must be a whole number from 1 to 50")
    _version, scenarios = load_scenarios()
    gap = minutes * 60 / calls
    plan = [{"call": index + 1, "start_second": round(index * gap), "line": index % lines + 1,
             "scenario_id": ROTATION[index % len(ROTATION)],
             "title": scenarios[ROTATION[index % len(ROTATION)]]["title"]} for index in range(calls)]
    return {
        "mode": "burst-plan", "calls": calls, "minutes": minutes, "lines": lines,
        "seconds_between_calls": gap,
        "note": ("Place the calls on this schedule from separate phones, one per line. "
                 "Write down, for each call, how long it rang before the agent answered and what the caller heard if it did not."),
        "watch_for": ["calls that ring out or hit voicemail", "a busy signal or a provider limit message",
                      "slower or cut-off replies as calls overlap", "requests that never reach the office"],
        "plan": plan,
    }
