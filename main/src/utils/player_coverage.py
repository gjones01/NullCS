"""Observational coverage only: never changes feature eligibility or model scores."""
from __future__ import annotations

import pandas as pd


def collect_coverage(match, kills: pd.DataFrame, encounters: pd.DataFrame, minimum: int) -> dict:
    people: dict[str, dict] = {}

    def observe(frame, id_col, name_col, source):
        if id_col not in frame:
            return
        for sid, rows in frame.groupby(id_col, dropna=True, sort=False):
            sid = str(sid).strip()
            if not sid or sid.lower() in {'nan', 'none', '<na>', '0'}:
                continue
            person = people.setdefault(sid, dict(steamid=sid, name=sid, sources=[], tick_rows=0))
            if source not in person['sources']:
                person['sources'].append(source)
            if name_col in rows:
                names = rows[name_col].dropna().astype(str)
                if len(names):
                    person['name'] = ' '.join(names.iloc[-1].split())[:120]
            if source == 'ticks':
                person['tick_rows'] = int(len(rows))

    observe(getattr(match, 'participant_info', pd.DataFrame()), 'steamid', 'name', 'participant_info')
    observe(match.ticks_df, 'steamid', 'name', 'ticks')
    for frame, source in [(match.kills, 'kills'), (match.damages, 'damages')]:
        observe(frame, 'attacker_steamid', 'attacker_name', source)
        observe(frame, 'victim_steamid', 'victim_name', source)
    observe(match.shots, 'attacker_steamid', 'attacker_name', 'shots')
    for person in people.values():
        sid = person['steamid']
        k = kills[kills['attacker_steamid'].astype(str).str.strip() == sid] if 'attacker_steamid' in kills else pd.DataFrame()
        e = encounters[encounters['attacker_steamid'].astype(str).str.strip() == sid] if 'attacker_steamid' in encounters else pd.DataFrame()
        # Match the canonical aggregation's non-null RT count, not total kills.
        n = int(pd.to_numeric(k['rt_ticks'], errors='coerce').notna().sum()) if 'rt_ticks' in k else 0
        person.update(kill_rows=int(len(k)), valid_rt_kills=n, encounter_rows=int(len(e)),
                      eligibility='candidate' if n >= minimum else 'insufficient_data',
                      status='not_scored', reason='Scoring has not completed.')
        if n < minimum:
            person['reason'] = f'Insufficient data: {n} kills with reaction-time evidence; at least {minimum} required.'
        if not person['tick_rows']:
            person['reason'] = 'No tick telemetry observed for this participant.'
    return dict(schema_version='nullcs.coverage.v1', scope='metadata_tick_and_event_observations',
                roster_complete=False, minimum_valid_rt_kills=minimum,
                note='Coverage combines available participant metadata, ticks and events; it may omit unrecorded participants. Tick rows do not prove usable encounter telemetry.',
                participants=list(people.values()))


def finish_coverage(coverage: dict, scored_ids, eligible_ids) -> dict:
    scored, eligible = set(map(str, scored_ids)), set(map(str, eligible_ids))
    for p in coverage['participants']:
        sid = p['steamid']
        p['eligible'] = sid in eligible
        if sid in scored:
            p.update(status='scored', reason=None)
        elif sid in eligible:
            p.update(status='not_scored', reason='Eligible feature row did not produce a score.')
        elif p['eligibility'] == 'candidate':
            p['reason'] = 'Excluded during aggregation; inspect name/group eligibility and feature diagnostics.'
    coverage['counts'] = dict(detected=len(coverage['participants']),
        with_tick_telemetry=sum(p['tick_rows'] > 0 for p in coverage['participants']),
        with_encounters=sum(p['encounter_rows'] > 0 for p in coverage['participants']),
        eligible=len(eligible), scored=len(scored),
        not_scored=sum(p['status'] != 'scored' for p in coverage['participants']))
    return coverage
