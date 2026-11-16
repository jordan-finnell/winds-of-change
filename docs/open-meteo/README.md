# Open-Meteo documentation

winds-of-change gets all of its real weather from [Open-Meteo](https://open-meteo.com/). These pages collect what you need to know about the service and its API to work on this library, or to extend it, without re-reading the upstream docs every time.

| Page | What's in it |
|---|---|
| [Open-Meteo, the service](open-meteo.md) | The APIs, terms of use, rate limits and call costs, licence and attribution, SDKs, self-hosting. |
| [API reference](api-reference.md) | Request parameters, response format, time zones, elevation and grid cells, errors, variables, and each endpoint's quirks. |
| [Models and datasets](models.md) | Forecast models, reanalysis datasets, ensembles and run archives: their `models=` IDs, resolution, time steps, coverage and delays. |
| [How this library uses Open-Meteo](in-this-library.md) | The requests winds-of-change sends and why, measured differences between endpoints and models, and pitfalls to keep in mind when changing a source. |

## How these pages were checked
Two kinds of statement appear here, and the pages say which is which:

- **Documented:** taken from Open-Meteo's own pages (the docs at [open-meteo.com/en/docs](https://open-meteo.com/en/docs), terms, pricing and licence), read in November 2026.
- **Observed:** checked against the live API on 16 November 2026 (UTC), with small requests for Greenwich (51.5° N, 0.0° E). Where the live API and the docs disagree, both are given.

Open-Meteo changes often: models are added and retired, archives grow and limits move. Treat dates and numbers as a snapshot and re-check anything you depend on. The [API reference](api-reference.md#checking-a-claim) has a quick way to do that.

## Privacy
Every example uses Greenwich or another neutral place. Never write real coordinates, a city, or weather fetched for a real person's location into these pages (see the repo's `CLAUDE.md`).
