"""
Build the EVOLEM dashboard payload from the LIVE Attio Dealflow list.

Fetches every Dealflow entry, resolves all references (company names, originator
actor names, introducer, select-option titles), and writes payload.json with the
row schema the report template expects.

Funnel note: the report computes a CUMULATIVE funnel from each row's per-stage
date fields (dossier_date … closed_date). Those dates are backfilled from the
deal_stage status HISTORY by the sibling cron `80x-djh/evolem-stage-dates`
(stamp_stage_dates.py), so make sure that job is healthy or the funnel will
under-count deals whose stage dates are empty.

Env: ATTIO_API_KEY (required).
"""
import os, json, requests

API_KEY = os.environ["ATTIO_API_KEY"]
BASE = "https://api.attio.com/v2"
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
LIST_ID = "e84ce78e-110e-406a-a2c1-e762b21e531f"
OUT = os.path.join(os.path.dirname(__file__), "payload.json")

# Pipeline stages in funnel order (excludes the terminal "Abandonné / Fermé").
STAGES_IN_ORDER = [
    "Dossier reçu", "Pre-Screening", "ManPres / Q&A / Coffee", "Pré-CI",
    "LOI Submitted", "Due diligence", "Closé",
]
LOI_STAGES = ["Closé", "LOI Submitted", "Due diligence"]
CLOSED_STAGES = ["Abandonné / Fermé", "Closé"]
NEW_PLATFORM_POLE = "Nouveau pôle"


def get(url, **kw):
    r = requests.get(url, headers=H, **kw); r.raise_for_status(); return r.json()


def post(url, body):
    r = requests.post(url, headers=H, json=body); r.raise_for_status(); return r.json()


def build():
    optmap = {}
    for slug in ["pole", "sector", "funding_round", "passed_reason"]:
        optmap[slug] = {o["id"]["option_id"]: o["title"]
                        for o in get(f"{BASE}/lists/{LIST_ID}/attributes/{slug}/options")["data"]}

    members = {}
    for m in get(f"{BASE}/workspace_members")["data"]:
        fn = m.get("first_name") or ""; ln = m.get("last_name") or ""
        members[m["id"]["workspace_member_id"]] = (fn + " " + ln).strip() or m.get("email_address")

    entries, off = [], 0
    while True:
        batch = post(f"{BASE}/lists/{LIST_ID}/entries/query", {"limit": 100, "offset": off})["data"]
        if not batch:
            break
        entries += batch
        if len(batch) < 100:
            break
        off += len(batch)

    cache = {}
    def record_name(obj, rid):
        k = (obj, rid)
        if k in cache:
            return cache[k]
        name = None
        try:
            nv = get(f"{BASE}/objects/{obj}/records/{rid}")["data"]["values"].get("name", [])
            if nv:
                name = nv[0].get("full_name") or nv[0].get("value") or nv[0].get("name")
        except Exception:
            name = None
        cache[k] = name
        return name

    def date(ev, slug):
        v = ev.get(slug, []); return v[0].get("value") if v else None

    def opt_title(ev, slug):
        v = ev.get(slug, [])
        if not v:
            return None
        return optmap[slug].get(v[0].get("option", {}).get("id", {}).get("option_id"))

    def all_opt_titles(ev, slug):
        out = []
        for v in ev.get(slug, []):
            t = optmap[slug].get(v.get("option", {}).get("id", {}).get("option_id"))
            if t:
                out.append(t)
        return out

    rows = []
    for e in entries:
        ev = e["entry_values"]
        comp = record_name(e.get("parent_object", "companies"), e.get("parent_record_id"))
        # originators: deal_team actor names, fall back to ALL owners
        team = [members.get(x.get("referenced_actor_id")) for x in ev.get("deal_team", []) if x.get("referenced_actor_id")]
        team = [t for t in team if t]
        if not team:
            team = [members.get(x.get("referenced_actor_id")) for x in ev.get("owner", []) if x.get("referenced_actor_id")]
            team = [t for t in team if t]
        # introducer: company name, else individual name
        intro = None
        ic = ev.get("introducer_company", [])
        if ic:
            intro = record_name("companies", ic[0].get("target_record_id"))
        if not intro:
            ii = ev.get("introducer_individual", [])
            if ii:
                intro = record_name("people", ii[0].get("target_record_id"))
        tr = ev.get("target_raise", [])
        ticket = (tr[0].get("currency_value") * 1e6) if tr and tr[0].get("currency_value") is not None else None
        sv = ev.get("deal_stage", [])
        stage = sv[0].get("status", {}).get("title") if sv else None
        rows.append({
            "company": comp,
            "stage": stage,
            "pole": opt_title(ev, "pole"),
            "sector": opt_title(ev, "sector"),
            "originators": team,
            "introducer": intro,
            "dossier_date": date(ev, "dossier_recu_date"),
            "pre_screening_date": date(ev, "pre_screening_date"),
            "manpres_date": date(ev, "manpres_date"),
            "pre_ic_date": date(ev, "pre_ic_date"),
            "loi_date": date(ev, "loi_submitted_date"),
            "due_diligence_date": date(ev, "due_diligence_date"),
            "closed_date": date(ev, "closed_date"),
            "abandonne_ferme_date": date(ev, "abandonne_ferme_date"),
            "end_date": None,
            "deal_type": opt_title(ev, "funding_round"),
            "passed_reasons": all_opt_titles(ev, "passed_reason"),
            "ticket": ticket,
        })

    from datetime import datetime, timezone
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "year": 2026,
        "stages_in_order": STAGES_IN_ORDER,
        "loi_stages": LOI_STAGES,
        "closed_stages": CLOSED_STAGES,
        "new_platform_pole": NEW_PLATFORM_POLE,
        "rows": rows,
    }
    json.dump(payload, open(OUT, "w"), ensure_ascii=False, indent=2)
    print(f"wrote {OUT}: {len(rows)} rows")


if __name__ == "__main__":
    build()
