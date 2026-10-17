# E — Identity, verification and attribution

> **Current publication status — October 16, 2026:** Design 0.2.0 and bounded A01–A10 are approved for fictional, isolated Phase 2A; Group B/C remain pending. The owner confirmed independent human review without outstanding blockers and authorized security PR #1 to merge; GitHub records merge `1e00ae5d175e0ace627b2dc5fc68e25a73cb41dd`. All seven checks passed on reviewed head `81ecc87672e35a00d45a9c40b2f83d578a364f2a`. This separate documentation PR is authorized for publication after checks. Phase 2A remains unimplemented and gated on documentation review, separate owner merge approval and actual merge. No live connections, deployment or Phase 2B–E implementation. Earlier gate/status snapshots below are historical, not current instructions.


> **Historical adoption record 1 — superseded by approval record 2:** The owner accepted design **0.2.0 as the technical baseline**, subject to unresolved policy approvals in J. This supersedes the earlier “final validation draft / technical approval pending” status only. Proposed policy defaults remain pending. Phase 2A planning is authorized; implementation and GitHub publication actions are not. See [adoption and Phase 2A handoff](I-roadmap.md#adoption-and-phase-2a-handoff) and [owner approval register](J-product-decisions.md#group-a-owner-approval-register).


Design 0.2.0 · Technical baseline and narrow A01–A10 approved; Group B/C pending.
**Proposed policies; recommended defaults require approval in J.** Attribution allocates observed outcomes; it is not a causal-incrementality model.

## Identity is a decision with evidence

An anonymous session is not a person. An inquiry is not a patient. A phone number, email, name, click ID or shared device is never an authoritative patient key alone. Do not auto-merge on a matching combination of these weak fields either. They can produce candidates for authorized review. No fabricated confidence percentages.

External references are namespaced by practice, provider account, object kind and external ID. Trusted continuity is either an existing approved mapping, a documented vendor crosswalk carrying stable source patient IDs, or an authorized practice review using independent evidence. A signed website submission token proves continuity between session and submission; it does not prove the patient's legal identity or newness. A caller/guardian can submit for someone else.

| State | Entry and reporting behavior |
|---|---|
| anonymous | No asserted person; eligible only for minimized acquisition reporting. |
| asserted | Name/contact or staff claim exists; no authoritative mapping. |
| candidate | One or more possible persons; no patient revenue attribution through this link. |
| linked | Explicit evidence-backed same-practice decision identifies person; record exact basis. |
| verified | Configured authority corroborates specified identity relationship; not blanket verification of every fact. |
| disputed | Conflicting linkage/history; dependent verified metrics withheld pending review. |
| revoked / superseded | Prior decision remains visible; subsequent projections use replacement and affected reports restate with lineage. |

Review shows masked candidates to specifically authorized staff. Linking requires reason, supporting refs and expected revision; races return conflict. Splitting/unlinking reverses a relationship through a new decision, never deletes history. Reports must recalculate affected episodes/conversions/transactions under the new decision version. Historical as-of reports retain previous decisions only within the approved retention policy; deleted supporting evidence can make reproduction unavailable/redacted. Cross-practice links are rejected even if the same person attends both practices; no agency-level patient matching is proposed.

Episode default: a confirmed submission creates a new episode unless the source explicitly references an existing inquiry/booking or an authorized decision links it to an ongoing care intent. Do not combine all activity within an arbitrary time window. Multiple calls/submissions may belong to one episode, but duplicated delivery of one call/submission does not create a new inquiry. This yields conservative “unique acquisition episodes,” not a claim of unique humans.

## Verified new patient

Recommended definition: **first qualifying attended clinical encounter at the practice, with verified identity and sufficient authoritative history to establish no earlier qualifying encounter at any of that practice's locations.** Registration, first CRM appearance, booking and an uncorroborated `new_patient` provider flag are insufficient.

Required evidence: authoritative patient ID; qualifying encounter/time/status; practice/location coverage; historical start and completeness; configured exclusions (administrative calls, cancellations, test accounts); provider history/newness evidence and policy version. If history covers only recent years and cannot establish absence earlier, classify indeterminate unless the approved policy explicitly defines a bounded “new in covered history” metric with a different label. An earlier encounter establishes existing status even if other history is incomplete.

A person can be new to a location or service while existing to the practice. Store these dimensions separately and count practice acquisition once. Two same-day encounters require deterministic earliest ordering using reliable source time; unresolved equal/low-precision ordering gets one conversion with an ambiguous location bucket, not two conversions. Later-discovered history supersedes newness and restates reports visibly. Existing-patient reactivation default requires an attended encounter after at least 18 months without a qualifying visit **and adequate history across that interval**; label the policy explicitly.

## Separate evidence axes

Store provenance (`browser_observed`, `server_submission`, `staff_asserted`, `provider_reported`, `provider_readback`, `reconciled`), identity state, outcome status, history coverage and financial status independently. A signed webhook authenticates the sender, not clinical truth. A reviewed import can be authoritative within its approved source and coverage; a handwritten spreadsheet is not equivalent. Public aggregate metrics remain aggregate regardless of confidence in their source.

## Attribution definitions

| Model | Rule | Missing or conflicting evidence |
|---|---|---|
| Original captured attribution | Preserve Patient.original_* and every earliest captured observation exactly as recorded | Keep original Unknown even when later evidence supports a new calculated decision. |
| Episode first-touch (recommended default) | Earliest eligible linked touch within 90 days before the episode's first inquiry, including that inquiry; source rules versioned | No eligible evidence → Unknown. Competing unresolved identity/source → unresolved attribution. |
| Inquiry source | Source evidenced on that specific confirmed call/form/chat/offline inquiry | Not the earliest-ever visit. Unknown when untagged. |
| Last non-direct | Latest eligible non-direct touch in same lookback; if none, evidenced direct may receive credit under explicit rule | Do not manufacture non-direct from search aggregates. Report separately from first-touch. |
| New-patient acquisition | Apply approved episode model to episode explicitly linked to the first qualifying encounter | Verified newness does not repair missing marketing evidence. |
| Repeat revenue | Cash linked to subsequent care episode; retain original acquisition source as a separate analysis dimension | Never relabel an existing patient new because a later ad was clicked. |
| Reactivation | Approved reactivation episode's attribution, with reactivation status independently verified | No qualifying inactivity history → reactivation indeterminate. |
| Multi-touch (deferred) | Explicit eligible evidence set and versioned weights summing to one per outcome | No inferred unseen touches; no duplicate full credit in totals. Not part of first pilot. |

The 90-day default is a **proposed business policy**, not a vendor constraint or current module behavior. The current module's 24-hour local storage is not expanded by this document. Longer server retention/capture requires privacy approval. Reports state observed-history coverage and model/lookback; “first observed eligible touch” is preferable to unqualified “first ever.”

Campaign credit requires a stable provider/account/campaign reference or approved tagged mapping. Free text remains raw capture; do not join solely by display name. Source taxonomy can extend current seven choices to organic_search, google_ads, google_business_profile, microsoft_ads, meta_ads, other_paid, organic_social, directory, physician_referral, patient_referral, email, sms, direct, offline_other and unknown, with versioned mappings retaining original values. Distinguish channel/platform/campaign, and use `unknown` for absent evidence versus `unresolved` for conflicts. A Google referrer alone cannot reliably distinguish GBP from ordinary organic search. GBP credit needs an approved dedicated tag/link or other specific evidence.

Offline referrals preserve the referring category and staff/provider assertion. They need no invented landing page, click ID or digital campaign. Search Console queries, GA4 audiences and advertising platform conversion totals cannot be joined to patient records to assign individual search terms. Patient attribution cannot be reconstructed from matching timestamps in aggregate reports.

## Location and service dimensions

Keep acquisition page location, expressed service interest, booked location/service, encounter location, delivered treatment service and financial allocation location/service as distinct nullable dimensions. All references remain within the practice. Inferences, if ever approved, are labeled and never overwrite source facts. A payment spanning services requires conserved allocations; otherwise the service revenue bucket is Unallocated, not duplicated across services. Unknown location remains visible.

## Recalculation contract

An AttributionDecision includes subject scope, evidence IDs, identity-decision version, model/version, time window/timezone, source/campaign weights, unresolved reason, calculated_at and supersedes ID. Recalculation appends decisions, rebuilds dependent reports and produces a before/after impact summary. Default reports use latest approved decisions with an as-of timestamp; historical snapshots remain reproducible only while the required evidence may lawfully be retained. Original observations are immutable even if consent withdrawal later limits access or requires policy-controlled deletion; tombstones and minimal audit hashes follow approved legal retention, not an unconditional promise to retain PHI forever.

## Ties and unsupported specificity

When candidate first touches have equal timestamps or insufficient time precision, do not break a source attribution tie by UUID or arrival order. Preserve the tied evidence, classify the decision unresolved at that specificity and request review or apply an explicitly approved tie policy. Absent referrer is not sufficient evidence of direct traffic. Source taxonomy includes offline_advertising, community_event and walk_in as explicit reported values; these never imply a measured digital exposure. Store medium separately from source and keep the original submitted labels alongside normalized mappings.


## E1 — Backward-compatible links, retention and source vocabulary

Use D3's source incarnation and ContactMethod extension for reused identifiers and household contacts. Identity decisions can reverse a source-to-person association without mutating legacy Patient.contact or Receipt.patient. If existing immutable cash was assigned to the wrong patient, mark the verified projection disputed and remove unsupported attribution; retain legacy recorded ledger/history, surface the discrepancy to finance, and require a separately approved ledger-remediation workflow. Do not silently “fix” immutable cash identity or create a second payment. New multi-person economic allocations are evidence-layer records and cannot bypass current one-patient Receipt constraints.

Keep legacy `organic_search` as generic organic search with platform Unknown unless Google-specific evidence exists. Do not migrate every legacy organic_search row to Google organic. Normalize source/channel/platform separately with versioned mappings; original labels never change. Proposed source additions in this document are a reporting vocabulary, not modifications to existing source enums until migration approval.

Anonymous-only evidence expires under approved policy; a 90-day attribution lookback is a maximum eligibility window, not a promise of 90-day observation. Once evidence is legitimately linked to an inquiry, retention follows the separately approved linked-evidence schedule. Before that schedule is approved, no live collection is enabled. If lawful deletion removes evidence, retain only approved minimal audit/tombstone; historical reproduction may be unavailable/redacted. Never claim exact as-of reproduction after necessary evidence has been deleted. Reports expose retention-limited coverage.
