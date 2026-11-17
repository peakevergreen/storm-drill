# Contributing

Start with `make demo` and `make test`. No packages, accounts, or network are needed.

- Every caller, address, and phone number in a scenario or example must be invented. Use `555-01xx` phone numbers.
- Never add a real call recording, transcript, or customer record to this repository or to an issue.
- A new scenario needs a script a person can read aloud, checks that can fail, and a test.
- Bump the scenario version in `stormdrill/data/scenarios.json` when a scenario's expectations change.
- Keep reports free of result text: name the scenario and the check, never the caller's details.
- Run `make test` and `make lint` before opening a pull request.
