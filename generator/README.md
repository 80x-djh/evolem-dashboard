# EVOLEM dashboard generator

Regenerates the password-protected KPI dashboard (`../index.html`, served via
GitHub Pages, login password **EvolemLogin**) from the **live Attio Dealflow
list**. Everything is computed client-side from a `<script id="payload">` JSON
blob; this generator just builds that blob and re-encrypts the page.

## Run

```bash
ATTIO_API_KEY=<evolem key> DASH_PASSWORD=EvolemLogin ./build.sh
git commit -am "Refresh dashboard" && git push
```

Steps (`build.sh`):
1. `build_payload.py` — fetch live Dealflow, resolve references → `payload.json`
2. `inject.py` — splice `payload.json` into `template.html` → `plain.html`
3. `encrypt.mjs` — StatiCrypt-v3 encrypt `plain.html` with `DASH_PASSWORD`,
   splice into `../index.html`. `plain.html` is deleted (never commit it).

## Funnel = cumulative

The "Stage conversion funnel" and "Funnel: build-up vs new platform" count a
deal at **every stage up to the deepest stage it ever reached**, derived from the
per-stage date fields in each row (`dossier_date … closed_date`) — *not* from the
deal's current stage. This includes deals later killed (`Abandonné / Fermé`), so
the funnel reflects how many dossiers ever passed through each stage rather than a
snapshot of where deals currently sit ("spot").

Those per-stage dates are backfilled from the `deal_stage` status **history** by
the sibling cron **`80x-djh/evolem-stage-dates`** (`stamp_stage_dates.py`). If
that job stops running, recent status moves won't have dates and the funnel will
under-count — keep it healthy.

## Notes
- `template.html` is the report shell with a `PAYLOAD_PLACEHOLDER` where the JSON
  is injected. Edit report logic here.
- The Attio key is **never** committed; pass it via env / Actions secret.
