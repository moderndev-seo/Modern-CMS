# H — Fictional multi-vendor acceptance-test specification

> **Execution status:** [PROJECT_STATE](../PROJECT_STATE.md) is authoritative for the current milestone, validation and authorization. Phase 2B is merged in PR #4; Phase 2C is next and unstarted at the October 20, 2026 checkpoint. Architecture 0.2.0 and A01–A10 remain unchanged; Group B/C remain pending. Dated adoption, validation and publication statements below are historical specification records, not current implementation status or new authorization.


> **Historical adoption record 1 — superseded by approval record 2:** The owner accepted design **0.2.0 as the technical baseline**, subject to unresolved policy approvals in J. This supersedes the earlier “final validation draft / technical approval pending” status only. Proposed policy defaults remain pending. Phase 2A planning is authorized; implementation and GitHub publication actions are not. See [adoption and Phase 2A handoff](I-roadmap.md#adoption-and-phase-2a-handoff) and [owner approval register](J-product-decisions.md#group-a-owner-approval-register).


Design 0.2.0 · Technical baseline and narrow A01–A10 approved; Group B/C pending.
**Specifications only. These tests have not been implemented or run.** All names/IDs/amounts are fictional. Use TEST Harbor Dental (practice A) and TEST Cedar Medical (practice B), distinct restricted PostgreSQL tenants. No live calls, messages, ad uploads or money movement.

## Shared executable-test contract

Each scenario must run at adapter contract, domain API and migrated restricted-PostgreSQL levels. Use NOSUPERUSER/NOBYPASSRLS, forced RLS, real database constraints, deterministic clocks and controlled worker crash injection. Test active and revoked grants, denied generic CRM traversal and exports, direct foreign FK writes, and pooled worker context reset. No skip may substitute for tenant tests. In a disposable fictional environment, accept pending work and applied facts, perform a normal application/worker/container restart with volumes preserved, then assert both persist and pending work resumes exactly once. No volume deletion or production restart is part of this architecture task. A simulated vendor response is a fixture assertion, not evidence that a real vendor supports it.

For every accepted event assert persisted inbox ID, tenant/connection binding, canonical hash/schema/mapping version, evidence classification, process state, effect key and lineage. For every replay assert stable effect count and totals. Validate both activity-period and cohort reports, Unknown/unallocated buckets, cash conservation and coverage reasons. Check permissions through HTTP, not only service methods. Export/suppression tests include headers, response bodies, error content and cached URLs.

Below, external IDs are always prefixed by stable provider account namespace. “Verified” means the specified fixture includes the required identity, authority and history evidence; it does not imply current connectors already produce it.

## A — Organic search → verified dental patient

- **Providers/source events:** WordPress stored Gravity Forms submission `WP-A/form1/entry101`, NexHealth confirmed booking `NEX-A/appt201`, Open Dental `OD-A/PatNum301/AptNum401` attendance, and approved collection source `PAY-A/txn501` readback/reconciliation. Consented organic observation precedes submission; sandbox fixtures carry vendor crosswalk and complete qualifying history.
- **Normalized records:** touch, session, inquiry, episode, identity decisions, appointment.booked, appointment.attended, patient.new_status_decided, treatment.completed, payment.settled and payment.reconciled. Source ledger and processor observations link to one economic collection.
- **Identity:** Signed session→entry continuity; explicit NexHealth→Open Dental patient mapping; no matching on email. Person receives a verified-new decision after history/attendance gates; this decision is internally generated, not accepted from the form sender.
- **Attribution:** Earliest eligible organic touch; no individual organic keyword inferred from Search Console. Original capture remains unchanged.
- **Financial result:** One USD 200 reconciled collection, organic attributed revenue200. Missing spend → ROAS null; complete approved marketing cost100 → attributed return on marketing spend2.00 only with complete outcomes.
- **Access:** Practice scheduling sees booking; clinical sees outcome; finance sees cash; SEO only privacy-approved aggregate. One-patient row is suppressed for SEO.
- **Recovery/tests:** Delay crosswalk: event retained blocked, no verified conversion; supply mapping and replay creates exactly one. Duplicate booking/payment deliveries leave one attendance/new conversion/collection. API/database cross-practice link rejected. Assert original source immutable and every metric's lineage resolves.

## B — Paid ad → phone → attendance → payment/refund

- **Providers/source events:** Google Ads account/campaign `ADS-A/c11`; custom website session `SITE-A/s12`; CallRail `CALL-A/c13`; chosen scheduling fixture `BOOK-A/a14`; clinical authority `PMS-A/p15/e16`; processor payment `PAY-A/t17` USD 500 and refund `r18` USD 100. Approved call session linkage and explicit clinical crosswalk included.
- **Normalized records:** marketing.touch_observed, inquiry.created(channel=inbound_call), appointment.booked/attended, treatment.completed, identity decision, settled/reconciled payment and settled refund.
- **Identity:** Call tracking session joins acquisition evidence to the call, not automatically caller to patient. Verified booking/PMS crosswalk or authorized staff decision required.
- **Attribution:** Google Ads campaign c11 under episode first-touch; later email touch remains separate.
- **Verification/finance:** Attended and financial states qualified independently. Net400; refund follows original source/cohort. Complete cohort spend200 and complete outcomes yield ROAS2.00. Ad platform conversion value never replaces500−100.
- **Access:** Call payload limited to approved staff; recording/transcript absent; finance-only refund details.
- **Recovery/tests:** Refund before payment remains blocked_dependency and acknowledged durably; payment arrival resolves to400 once. Same payment with another delivery ID deduplicates by transaction business key. Assert request/booking/attended distinct, no source overwrite and no doubled payment from PMS posting.

## C — GBP booking from existing patient

- **Providers/source events:** Approved tagged GBP link `GBP-A/location1/link1`, site session, Calendly `CAL-A/event1/invitee1`, clinical patient `PMS-A/p21` with earlier qualifying encounter and current encounter `e22`.
- **Normalized records:** touch, inquiry, episode, booking, attended, identity link; conversion decision existing, not new.
- **Identity:** Existing authoritative mapping and prior encounter identify person; no new Contact from another email.
- **Attribution:** Current episode GBP; original captured attribution retained; tagged link required, generic Google referrer alone yields source unresolved/organic only to supported specificity.
- **Verification/finance:** Booked1, attended1, verified-new0. No financial event means no observed cash; revenue completeness remains unavailable unless payment-stream coverage proves zero. Future payment belongs to existing-patient revenue.
- **Access:** Scheduling cannot expose prior treatment/finance; marketing cells suppressed as needed.
- **Recovery/tests:** Remove earlier history: status becomes indeterminate, not new. Restore history: existing. Replay booking once; attempt write `new=true` to the canonical receiver from scheduler returns422 for unsupported field, with zero conversion decisions written. Assert source and original capture distinct and historical status correction retained.

## D — Offline physician referral

- **Providers/source events:** Authorized practice staff creates `MAN-A/referral31`, PMS `PMS-A/p32/e33` and reconciled USD 150 collection `PAY-A/t34`. No digital touch or website token.
- **Normalized records:** inquiry.created(channel=referral), qualification, booking, attended, verified-new decision, payment evidence. AttributionEvidence is staff_asserted physician_referral.
- **Identity:** Staff-entered identity stays asserted until mapped to authoritative PMS patient with history.
- **Attribution:** Offline physician referral; landing page/click ID/campaign null. Source certainty is staff assertion, not falsely browser-observed.
- **Verification/finance:** One verified new after attendance/history; net150. No spend data → cost/ROAS unavailable, not free acquisition.
- **Access:** Staff can create referral under granted scope; physician identity optional and minimized; finance separate.
- **Recovery/tests:** Missing authority/history retains indeterminate newness. Duplicate request ID gives one inquiry. A source correction appends a decision, preserves original staff assertion and audit reason. Assert no generated digital source and denied cross-tenant referral links.

## E — Multiple devices, phone numbers and email addresses

- **Providers/source events:** Session `SITE-A/s41`, call `CALL-A/c42` from another number, booking `BOOK-A/a43` with different email, PMS `PMS-A/p44/e45` and USD 250 payment.
- **Normalized records:** Separate observations/inquiries with unresolved candidate links; independent booking/patient/transaction facts can exist without acquisition linkage.
- **Identity:** No automatic join from timing/name similarity. Authorized review or documented crosswalk linking submission/call/booking to p44 creates explicit decisions; acquisition session joins only if independent continuity evidence exists.
- **Attribution:** Before evidence, clinical collection has Unknown/unresolved marketing attribution. After only booking-to-patient linkage, original session remains unlinked; marketing source is still Unknown. Full evidence permits new versioned decision.
- **Verification/finance:** Cash250 can be verified while acquisition unresolved. Person newness depends on history, not count of inquiries; never count three new patients.
- **Access:** Identity reviewer sees minimum necessary candidates; marketing sees coverage only.
- **Recovery/tests:** Replay with weak matches does not link. Add approved crosswalk yields exactly one effective identity decision; revoke it restores unresolved source in latest report while prior as-of report remains reproducible. Assert250 conserved throughout and no overwritten observations.

## F — Shared household email and telephone

- **Providers/source events:** Two submissions `WP-A/entry51,52` share email/phone; PMS patients `PMS-A/p53,p54`, distinct encounters and payments USD 100/USD 200; one guardian may be payer.
- **Normalized records:** Two inquiries/episodes and distinct patient mappings; payment ownership/allocation references independently evidenced.
- **Identity:** Shared contact fields create ambiguous candidates, not a merge. Explicit source patient IDs and review establish two persons. Guardian contact is not both patient identities.
- **Attribution:** Each episode uses its own evidence; one organic and one Unknown stays that way. No household propagation.
- **Verification/finance:** If both have sufficient newness history, new2. Net300. Shared payer payment cannot be split without authoritative/authorized allocation; otherwise Unallocated300.
- **Access:** Practice-authorized reviewer only; marketing cannot inspect household details.
- **Recovery/tests:** Automated match on phone/email forbidden; assert two Contact/Patient mappings and no cross-patient refund. Preserve existing primary email uniqueness: second Contact.email is blank and two protected ContactMethod associations hold the shared household address, per D3. Concurrent link attempts conflict safely. Undo erroneous reviewed link appends correction and recomputes reports without losing either source observation or doubling300.

## G — Vendor replacement mid-period

- **Providers/source events:** CallRail `OLD-A/c61` and WhatConverts `NEW-A/lead61`; booking vendor X appointment `X-A/71` replaced by vendor Y `Y-A/71`, possibly referring to same clinical encounter `PMS-A/e62`.
- **Normalized records:** Two provider namespaces, retained old observations, new connection and explicitly crosswalked appointment/encounter identities.
- **Identity:** Equal string IDs do not join. Preserve old mappings; authorized migration crosswalk can identify same episode/appointment. Rotation of a key for the same account retains namespace.
- **Attribution:** Original pre-switch touch unchanged; later new-provider touch remains subsequent. Unknown historical source not filled from replacement defaults.
- **Verification/finance:** One clinical encounter/new conversion despite two booking representations if evidenced; one USD 300 collection even if both feeds observe it.
- **Access:** Disable old ingestion permissions without deleting old evidence; crosswalk requires practice approval.
- **Recovery/tests:** Reimport old history plus new live fixtures: no duplicate cash/conversion. Missing crosswalk remains unresolved, not silently deduped. New credential for same provider account cannot defeat business-key uniqueness. Assert historical reports reproducible and source freshness distinct across cutover gap.

## H — Duplicate, conflicting and out-of-order events

- **Providers/source events:** Booking revisions `BOOK-A/a81 v2,v1`; two deliveries of same event; same ID with changed content; processor `PAY-A/t82` USD 100 and refund `r83` USD 20 arriving first; PMS echoes same collection.
- **Normalized records:** Durable delivery receipts, canonical versioned observations, conflict review, blocked refund and one economic payment/refund pair.
- **Identity:** Stable approved mappings; conflicting person reference quarantined rather than relinked.
- **Attribution:** Original source untouched; projections reference latest valid authoritative revision.
- **Verification/finance:** Older status cannot regress appointment. Final net80, never180 or−20 as a completed orphan refund projection. Provider/PMS disagreement remains a visible reconciliation issue.
- **Access:** Only permitted review capability can resolve conflict; normal webhook cannot override it.
- **Recovery/tests:** Inject crash before inbox commit → non-success/no row; after inbox commit before Celery enqueue → sweeper applies once; after effect commit before worker acknowledgment → retry no duplicate. Same event/hash returns original receipt; changed hash conflicts. Concurrent refunds exceeding balance rejected by DB. Validate cursor does not skip failed page and no lost accepted event.

## I — Partial payment, delayed insurance and refund

- **Providers/source events:** October attendance `PMS-A/e91`; October payment `PAY-A/t92` USD 100; November remittance `RCM-A/era93` USD 300 with separately reconciled EFT `BANK-A/eft94`; December refund `PAY-A/r95` USD 50 of t92.
- **Normalized records:** Attended/verified-new, partial collection, remittance evidence, one insurance collection, refund and reconciliation decisions. Remittance is not a second payment.
- **Identity:** Explicit claim/patient/remittance/transaction crosswalk; guarantor or insurer identity does not replace patient identity.
- **Attribution:** Original October cohort/source retained for all linked cash; service allocation remains Unknown if not evidenced.
- **Verification/finance:** Periods100,300,−50; October acquisition cohort through December350. Recorded-only insurance posting remains outside reconciled total until EFT evidence. Currency-specific totals only.
- **Access:** Finance sees remittance/allocations; clinical and SEO cannot retrieve them.
- **Recovery/tests:** Replay835 and EFT multiple times yields one300 effect. Missing EFT leaves reconciled cohort100 until arrival. Date correction moves period total with audit/as-of restatement; original cohort unchanged. Assert refund capped, no fee/claim-value substitution and amounts reconcile to350.

## J — Cross-tenant isolation and foreign links

- **Providers/source events:** TEST Harbor connection attempts body tenant=TEST Cedar, Cedar patient ID, foreign appointment, refund parent, external mapping and supersession target.
- **Normalized records:** None in Cedar; redacted denial audit only under appropriate security scope. Rejected payload must not become a normal canonical event.
- **Identity/attribution:** No foreign candidate resolution or evidence leakage. Agency membership does not authorize the connection to act across practices.
- **Verification/finance:** Both tenant totals and histories unchanged; no new/treated count or money movement.
- **Access:** Test human, service, PAT, org key and stale/revoked agency grants separately through supported entrypoints.
- **Recovery/tests:** API list/detail/search/filter/export and generic Contact/invoice relations deny or omit appropriately without disclosing foreign names. Direct SQL INSERT/UPDATE foreign links fail even with valid current-practice tenant context. Background worker alternates A/B with injected exception; next task sees only its tenant. Assert all protected rows use forced RLS and runtime role cannot bypass. Fix credential mapping only by authorized reconfiguration, never by trusting request tenant.

## K — Credential revoked while work is queued

- **Providers/source events:** Valid `CONN-A/key-v1` accepts e101 before revocation; queued e102, in-flight e103; post-revocation e104; routine rotation tested separately.
- **Normalized records:** Previously committed applied facts remain; accepted pending evidence moves to quarantined(reason=revoked); rejected e104 produces safe denial metadata only.
- **Identity/attribution:** Existing decisions retained; suspect evidence can later be invalidated by authorized correction. No worker inherits a human admin actor.
- **Verification/finance:** No post-revocation effect from queued work. Already committed USD 100 remains until a documented correction, not automatic deletion.
- **Access:** Connection administrator may revoke, but replay/reconciliation permissions remain separate.
- **Recovery/tests:** Synchronize revocation and effect commit with transaction barriers; prove either commit precedes revocation or effect blocked after generation change. Every new call401/403; pending replay cannot run until explicit review/reactivation. Routine key rotation with approved overlap preserves same namespace and idempotency. New key does not silently process compromise quarantine. Audit timeline reconstructs acceptance/commit/revocation order without exposing secret.

## L — SEO aggregate access without patient access

- **Providers/source events:** TEST Harbor fixture cohort with two small service groups and a larger allowed aggregate; GSC/GA4 aggregate fixtures; no patient join keys in marketing data.
- **Normalized records:** Protected patient facts stay tenant-bound; approved report projection exposes only permitted dimensions and coverage.
- **Identity/attribution:** SEO cannot query mappings or infer individual query→patient assignment. Aggregate marketing data remains separate from clinical evidence.
- **Verification/finance:** Authorized aggregate counts/cash may be shown if privacy policy passes. Small cells return suppressed, not zero; complementary totals cannot reveal them by subtraction.
- **Access:** SEO-only grant denies patient/contact-linked body/history, raw inbox, identity, invoice/payment detail and identified CSV/API exports. API includes no hidden IDs or evidence URLs.
- **Recovery/tests:** Exercise normal UI and direct endpoints, changed filters/date ranges, sorting/pagination, repeated overlapping queries, errors, cached exports and signed links. Remove grant while export queued: download denied. Suppression includes associated cash and denominator, and cross-practice portfolio honors individual grants. Assert no identity leakage from aggregate-to-detail links. Privacy expert still reviews residual inference risk.

## M — Legacy EHR with approved periodic imports

- **Providers/source events:** Approved SFTP CSV `LEG-A/batch111` from source system, digest and row IDs, monthly encounters/payments for bounded interval; separate staff spreadsheet assertion fixture.
- **Normalized records:** Import batch, source observations, identities, encounters, recorded/provider-reported financial facts, sync coverage and unresolved review items.
- **Identity:** Stable patient/encounter IDs map within LEG-A. No ID? Quarantine or reviewed row-key strategy; do not infer lifetime identity from names.
- **Attribution:** Existing linked acquisition evidence used; missing historical source Unknown. Recent export is not proof of no earlier visits.
- **Verification/finance:** Provider-origin approved extract can verify supported facts within coverage; staff spreadsheet remains staff_asserted. Newness indeterminate without sufficient history. Ledger payment alone is recorded, not reconciled collection.
- **Access:** Restricted import operator; source file encrypted/minimized, retention controlled; marketers cannot download raw file.
- **Recovery/tests:** Rerun same file no duplicates; changed row same key triggers versioned correction/review; malformed row yields explicit partial/rejected batch and no false complete coverage. Interrupted import resumes from durable accepted rows. Missing month marks stale/gap. Reconciliation compares source counts/totals and preserves prior data.

## N — Incomplete marketing evidence

- **Providers/source events:** Untagged site inquiry `SITE-A/q121`, unclassified call `CALL-A/c122`, authoritative patient/attendance and settled USD 120; GSC aggregate organic increase in same week.
- **Normalized records:** Unknown-source observations, inquiry/episode, verified identity/outcome and financial evidence; aggregate GSC facts separate.
- **Identity:** Person can be verified independently from source; unlinked call remains unresolved until evidence exists.
- **Attribution:** Unknown, not Google organic from timing or business plausibility. Missing campaign/landing page remains null. Original Unknown stays immutable after later supported source decision.
- **Verification/finance:** New-patient count can be1 and net120 while attributable-source coverage0/1. Known-source revenue0 is accompanied by Unknown120, not missing cash. ROAS unavailable absent complete spend/evidence.
- **Access:** Finance can trace120; marketing only eligible suppressed aggregates and coverage explanation.
- **Recovery/tests:** Inject aggregate impressions/clicks and a later paid touch; neither rewrites original Unknown. Supply genuine earlier evidence: new AttributionDecision changes latest calculated source with audit, original capture stillUnknown. Test missing spend never coerced to0 and coverage denominator retains this outcome.

## O — Multiple locations and services

- **Providers/source events:** Site landing page for Location1/service whitening; booking `BOOK-A/a131` at Location2/service exam; encounter `PMS-A/e132` at Location2; treatment `t133` restorative service at Location3; USD 600 receipt with approved service allocation or unallocated variant.
- **Normalized records:** Distinct acquisition, booked, encounter and treatment dimensions on observations/objects; one person/episode; conserved transaction allocation.
- **Identity:** All locations within TEST Harbor; explicit external clinic crosswalk. Another practice's location ID rejected.
- **Attribution:** Acquisition page/location/service interest remains Location1/whitening; booking and treatment never overwrite it. Source credit follows approved episode model.
- **Verification/finance:** Verified-new once at practice level; new-to-location can be separately reported. Net600 once; without reliable payment allocation service revenue Unallocated600, not600 for each service/location.
- **Access:** Only granted practice resources visible; do not claim location isolation until implemented and tested across all linked records.
- **Recovery/tests:** Change booking location through versioned event: acquisition untouched. Report by each named dimension reconciles totals including Unknown/Unallocated. Concurrent treatment updates preserve revisions. Foreign-location link fails API/DB. Missing location mapping blocks that dimension without losing accepted clinical evidence.

## Completion criteria for this matrix

Every scenario needs fixture provenance, explicit expected canonical rows, report snapshots and negative access assertions. Fixture tests establish domain consistency; vendor sandbox tests separately prove adapter mappings, signatures, paging, rate-limit recovery and source semantics. Pilot acceptance must add real authorized practice validation with no unsupported clinical/cash claims. Passing these proposed tests alone cannot establish legal compliance, causal marketing lift or full production readiness.

## Additional lifecycle conformance assertions

Waitlisted and requested appointments never increment booked counts until confirmation; two separate appointments remain two records even if concurrent. Imported overlaps are retained as evidence and flagged rather than silently lost. Provider/location revisions preserve old facts. A treatment recommendation or accepted plan cannot increment completed treatment or collections. Missed/unanswered calls count as call inquiries with their disposition, not qualified leads. Follow-up visits and referral generation cannot create a second practice-new conversion. Test source/medium separately, explicitly reported walk-in/community/offline advertising and Unknown when no source was reported.


## H1 — Exact canonical and numeric oracles for A–O

The scenario prose is explanatory; fixtures use D's full event names, typed references and internal decision boundary. `touch` means marketing.touch_observed; `booking` means appointment.booked; `attended` means appointment.attended; `verified-new` means an internal patient.new_status_decided decision with value=new and sufficient history. Every monetary result below assumes the stated selected reconciliation predicate is actually met; otherwise it remains in a lower tier.

| Scenario | Required result after all valid fixtures and replay | Critical negative assertion |
|---|---|---|
| A |1 person,1 episode,1 confirmed appointment,1 attended appointment,1 verified-new decision,1 economic payment; USD200 organic net | Duplicate payloads produce0 additional effects; no individual SEO keyword |
| B |1 call inquiry,1 confirmed/attended appointment, USD500 payment−100 refund=400; ad spend200 gives2.00 | Refund-first gives0 applied refunds until parent; later email leaves original source unchanged |
| C |1 booking,1 attended appointment,0 verified-new; decision=existing | Payment coverage absent returns unavailable, not confirmed zero collection |
| D |1 referral inquiry,1 verified-new, USD150 reconciled net | Digital page/click IDs null; referral category not replaced with online source |
| E |USD250 conserved across all link decisions; unresolved acquisition before evidence | Weak-field match creates0 links; missing session proof keeps source Unknown |
| F |2 distinct patients; USD100+200=300 total | Shared email/phone never merges patients; unallocated variant retains300 |
| G |Crosswalked fixture has1 canonical encounter and USD300 economic cash | Same literal IDs in different namespaces create0 automatic joins |
| H |1 payment+1 refund effect; netUSD80; highest authoritative appointment revision effective | Mapping/projector replay produces0 additional ledger effects; changed event hash is409 |
| I |October100, November300, December−50; inquiry/attendance October cohort through December350 | ERA+EFT is one300 collection, not600 |
| J |0 foreign rows read or modified,0 foreign effect writes | DB foreign link fails and API reveals no foreign name/amount |
| K |Previously committed100 remains; queued revoked events apply0 effects | Post-revocation requests401/403; explicit replay approval required |
| L |Fixed fixture:10 patients total split into service groups3 and7; small cell suppressed and complementary disclosure blocked | Raw API/export/query variants reveal0 patient IDs; revocation invalidates queued export |
| M |Identical batch twice produces same row/effect counts; one malformed row yields partial coverage | Ledger-only or staff-only amounts produce0 reconciled cash; partial history produces0 verified-new |
| N |Observed source Unknown120;1 verified-new; resolved source coverage0/1 | GSC aggregate and later touch produce0 original-source changes |
| O |1 practice-new, net600 once; acquisition L1, booking/encounter L2, treatment L3 | No allocation→Unallocated600; never600 per each location/service |

## H2 — Additional architecture-critical fixtures P–X

These are additional scenarios, not replacements for A–O. Each test includes source identity, canonical events, verification/attribution/finance oracle, denied roles and recovery below.

| ID / initial evidence | Canonical and identity rules | Measurable result, access and recovery |
|---|---|---|
| P — Medical alternative stack | TEST Cedar custom form `MED-S/q1`, authorized simulated FHIR Patient `MED-E/p1` and Encounter `e1`, approved appointment `a1`, separate payment `MED-P/t1` USD80. Explicit appointment-to-patient crosswalk; complete practice history; organic source. Emit inquiry.created, appointment.booked/attended, patient.new_status_decided and payment evidence. |1 verified-new,1 attended, reconciled80; no core schema change relative to dental A. Website principal cannot emit medical or cash facts (403,0 effects). Missing crosswalk blocks identity and replay resolves exactly once. This is a medical contract simulator, not certification of any named EHR. |
| Q — Replay/version, split captures and chargeback | Account source `t1` has two captures60/40, refund20, posted chargeback30, recovery10; PMS components reference same100. Stable component IDs, same person/episode. Map observation versions1 and2 and rebuild read projections. | Economic net60 (100−20−30+10), same after every replay;0 extra Receipt writes from new projector version. Reversal without original loss blocks. Duplicate debit beyond principal is preserved outside attributed patient revenue with disputed reconciliation status, not discarded. Finance only; corrections audited. |
| R — Incorrect identity and reused IDs | Provider deletes/reuses `p1`; prior incarnation belonged to personA and new source evidence to personB. Existing Receipt forA is immutable. |0 automatic reassignment; ambiguous generation quarantined. Approved new incarnation maps future evidence toB, historical evidence staysA. Revoke erroneous mapping: latest verified attribution withheld/disputed, recorded Receipt.patient unchanged; no second cash entry. Reviewer/finance permissions separately enforced. |
| S — Legacy webform household collision | Two persisted submissions share email; legacy status accepted_duplicate points to one sales Lead. New explicit source patient IDs identify two persons. |2 inquiry records,2 patients via D3 ContactMethod, not1 because of merged Lead. Replay same submission ID adds0 inquiries. New adapter triggers0 legacy notifications and never exposes payload to developer-only grant. Missing identity remains unresolved. |
| T — Clinical lifecycle and authority conflict | Requested+waitlisted visit, later booked; two encounters tied at date-only precision; staff says attended while approved PMS says no_show; accepted treatment plan without completion. | Request/waitlist alone booked0; confirmation booked1. Conflict gives0 verified attended/new until reviewed. Equal timestamps cannot arbitrarily select acquisition location. Treatment plan alone completed0/cash0. Clinical reviewer only; resolution appends evidence without deleting conflict. |
| U — Currency and daily timezone | USD100 and EUR80 independent collections; USD50 complete ad spend. Source daily aggregate is Pacific time; report asks exact Chicago calendar day. Include DST March8,2026 and November1,2026 Chicago boundaries. | No total180 and no mixed-currency ROAS. Chicago day windows23h and25h respectively; ambiguous1:30 without offset quarantined. Daily-only Pacific spend cannot yield exact Chicago-day ROAS (null reason=timezone_alignment_unavailable). Finance/cost detail restricted; finer data or aligned report resolves. |
| V — Completeness and zero spend | Expected two payment locations; only default location retrieved. Appointment stream complete, financial stream partial. Explicit complete zero spend vs missing spend fixtures. | Financial completeness partial despite successful poll; verified ratios null. Missing spend null; complete zero with positive inquiries gives CPA0 but ROAS null. Zero observed effects gives coverage null/not_applicable, never100%. Missing location import fills gap only after reconciliation. |
| W — Cohort and attribution boundaries | Two inquiries at different dates; only one explicitly linked to appointment and cash; touch89 days before inquiry vs91 days; original generic organic_search platform unknown. Evidence later lawfully deleted. | Only89-day eligible touch can receive credit under90-day policy; never infer Google from generic organic. Appointment/cash credited once, ambiguous episode remains unresolved. Attendance cohort value cannot use unmatched inquiry-window spend. Deleted evidence marks historical reproducibility unavailable/redacted; no guessed replay. |
| X — Credential, queue and confidentiality | Properly signed website request for payment.settled; malformed clinical source; valid pending events during revocation; quarantined sensitive payload expiry. | Website request403 and0 clinical/cash effects. Queue arguments/log/error/trace fixtures contain0 payload/contact/token values. HMAC verification succeeds using approved secret mechanism, not hash-only bearer storage. Expired evidence cannot replay; revocation serializes with commit. Restricted SQL and generic API routes cannot retrieve pre-patient inquiry bodies. |

Additional expected test levels: each row has pure calculation/normalization tests, domain/API authorization tests and migrated PostgreSQL integrity/concurrency tests where applicable. Source signatures/pagination need separate provider contract fixtures. The full end-to-end acceptance suite spans phases 2–6; phase 2 alone runs its foundation subset and must not claim these later workflows implemented.
