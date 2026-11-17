# Storm Drill

**Test a phone agent the way a storm week will.**

Ten scripted calls and a scorer for AI phone agents at home service companies.
Read each script to the agent, write down what the system saved, and get a
report of what a real caller would have lost.

```text
Tester reads a script → agent answers → system saves a request
        tester fills in one result file → stormdrill scores it
```

It works with any agent: one built into field service software, a voice agent
service, or a custom build. It does not place calls, listen to audio, or need
an account, a package, or a network connection.

A companion to [AI voice agents for the calls you're missing](https://peakevergreen.com/blog/ai-voice-agents-missed-calls/)
by [Peak Evergreen](https://peakevergreen.com/). Substantially built with Claude.

## Start in a minute

Python **3.10+**. Nothing to install.

```sh
python3 -m stormdrill list                       # the ten scenarios
python3 -m stormdrill script gas-smell           # what the tester says
python3 -m stormdrill score examples/good-agent  # a run that passes
python3 -m stormdrill score examples/weak-agent  # a run that does not
```

Or `make demo`. Both example runs are invented, to show the report.

## The scenarios

| ID | What it catches |
| --- | --- |
| `after-hours-ac` | A complete request: name, number, address, problem, availability. |
| `out-of-state-owner` | Owner, tenant, service address, billing address and access mixed into the wrong fields. |
| `gas-smell` | Diagnosing, booking a routine visit, or failing to alert a person within two minutes. **Critical.** |
| `price-question` | Quoting a price under pressure. |
| `wants-human` | Making a caller ask twice for a person. |
| `duplicate-caller` | A worried callback creating a second job. |
| `dropped-call` | A partial request vanishing when the call drops. |
| `declines-recording` | Recording continuing after the caller says no. **Critical.** |
| `spanish-speaker` | Losing the request when the caller speaks Spanish. |
| `gate-code` | A gate code copied into general notes. |

Every caller, address and phone number is invented.

## Run it against your agent

```sh
python3 -m stormdrill script > scripts.txt   # print for the tester
python3 -m stormdrill blank run-01           # one empty result file per scenario
```

1. Place each call and read the script. Use a real phone, in the conditions your customers call from.
2. After each call, open the request the system created. Copy what it saved into that scenario's file in `run-01/`, and answer the yes/no questions.
3. Score the run:

```sh
python3 -m stormdrill score run-01 --fail-on-critical
```

The report lists every failed check by scenario, the scenarios you did not run,
and any critical failures. See [the result file guide](docs/results.md) for
every field and what each observation means.

Before you start, write down your own rules: what the agent may book, what your
emergency policy says, and the recording-consent flow your counsel approved.
Three observations ask whether the agent followed them.

## Plan a burst

After a storm, calls overlap. Some hosted voice models limit how many calls run
at once, and callers hear whatever your phone setup does at that limit.

```sh
python3 -m stormdrill burst --calls 20 --minutes 10 --lines 4
```

This prints a schedule: which scenario to call, when, and on which phone. Record
`answered_seconds` for each call, then `score --answer-within 20` counts how many
were answered in time.

## Exit codes

| Exit | Meaning |
| --- | --- |
| `0` | Completed. The report may list failures. |
| `1` | A critical scenario failed and `--fail-on-critical` was set. |
| `2` | Invalid input. |

## Limitations

- **It scores what a tester wrote down.** It cannot hear the call. Honest
  observations are the test.
- **Ten calls are a drill.** Passing them does not show how an agent behaves on
  your real call mix. Read or listen to a sample of real calls every week.
- **It is not legal advice.** `declines-recording` and `followed_emergency_policy`
  compare the agent with rules you bring. Recording consent and outbound-call
  rules vary by state. Ask qualified counsel.
- **Key-word matching is forgiving.** A field can pass with the right words and
  still read badly. Look at the record yourself.
- **The scripts are US English and Spanish, for residential service calls.**
  Other trades and languages need their own scenarios.

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [MIT license](LICENSE).
