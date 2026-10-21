# D — Canonical data and event specification

> **Execution status:** [PROJECT_STATE](../PROJECT_STATE.md) is authoritative for the current milestone, validation and authorization. Phase 2B is merged in PR #4; Phase 2C is next and unstarted at the October 20, 2026 checkpoint. Architecture 0.2.0 and A01–A10 remain unchanged; Group B/C remain pending. Dated adoption, validation and publication statements below are historical specification records, not current implementation status or new authorization.


> **Historical adoption record 1 — superseded by approval record 2:** The owner accepted design **0.2.0 as the technical baseline**, subject to unresolved policy approvals in J. This supersedes the earlier “final validation draft / technical approval pending” status only. Proposed policy defaults remain pending. Phase 2A planning is authorized; implementation and GitHub publication actions are not. See [adoption and Phase 2A handoff](I-roadmap.md#adoption-and-phase-2a-handoff) and [owner approval register](J-product-decisions.md#group-a-owner-approval-register).


Design 0.2.0 · Technical baseline and narrow A01–A10 approved; Group B/C pending.
**Logical schema proposal, not migrations.** Reuse existing physical models where they fit. A conceptual entity below does not necessarily need its own table. New structures are justified by evidence that cannot safely fit today's patient-only synchronous intake or manual ledger.

## Existing-model mapping

| Concept | Reuse / extend / new | Proposed meaning and minimum additions |
|---|---|---|
| Agency | New | Agency organization and explicit AgencyClientGrant; separate from the practice tenant. No global patient index. |
| Client / Practice | Reuse Org | Existing tenant; do not repurpose sales Account as a clinical practice. Add business metadata only when needed. |
| Location | New org-scoped | Stable ID, code, timezone, active interval and external mappings. Appointment.location text stays as legacy display. |
| Website | New org-scoped | Domain/path ownership, CMS/product, allowed form origins, location/service mappings, configuration versions. |
| Service | New org-scoped | Approved reporting taxonomy and vendor code crosswalk; acquisition interest distinct from delivered service. |
| Provider / Clinician | New org-scoped directory | Minimal stable references and locations; not every provider is a login User. |
| IntegrationConnection | Extend concept; new live registry | Keep existing AttributionConnection TEST namespace. Live registry has provider account, capabilities, service grant, health and secret reference. |
| MarketingCampaign | New org-scoped | Provider/account/campaign ID, names with validity intervals, currency and mappings; free-text campaign remains original capture. |
| MarketingTouch | Extend JourneyEvent plus pre-lead evidence | Existing `touch` remains patient history. Store minimized anonymous observations before a patient exists; project only authorized links. |
| AcquisitionSession | New | Consented random session token, site, start/expiry, evidence refs; not a person identifier. |
| Inquiry / AcquisitionEpisode | New | Inquiry is a distinct submission/call/chat/staff request; episode groups an evidenced care/acquisition intent. Store membership decisions and status histories. |
| Lead | Reuse generic Lead optionally | CRM follow-up linkage; never require every inquiry to create a sales Lead or Patient. Qualified status belongs to explicit episode decision. |
| Contact / Person | Reuse Contact | Practice-local identity; do not create a universal agency person table. Existing object visibility remains enforced. |
| Patient | Extend Patient | Preserve one-to-one Contact, original source and dates. Add references to verified status decisions rather than mutable boolean `is_new`. |
| ExternalIdentity | Extend concept; new generalized mapping | Current AttributionIdentity is TEST connection-to-patient and immutable. New mapping covers person, appointment, transaction and other object kinds in a stable provider namespace. |
| IdentityMatchDecision | New append-only | Candidate/linked/rejected/disputed/revoked decisions; evidence, actor, policy version, effective times, superseded decision. |
| Appointment | Extend Appointment and AppointmentChange | External refs, canonical location/service/provider, source revision, confirmed/requested distinction and authority. Preserve local optimistic revisions/history. |
| Encounter / Attendance | New evidence; reuse JourneyEvent projection | Stable encounter key, encounter status, source, linked appointment optional, verification and correction references. |
| VerifiedConversion | New decision/projection | Patient, qualifying encounter, scope, new/existing/indeterminate, history coverage and policy version; append-only evidence-backed decisions. |
| TreatmentOutcome | Extend JourneyEvent with evidence | Existing consultation/treated events remain; add provider outcome key, service/location, status, effective time and evidence. No clinical narrative required. |
| FinancialTransaction | New source-evidence layer around Receipt | Namespace/object key/currency/amount/type/status/time; original transaction, payer class and settlement/reconciliation links. Receipt remains local cash ledger with current constraints. |
| AttributionEvidence | Reuse canonical observations plus typed evidence links | Links immutable capture, inquiry, call and consent evidence. No aggregate-to-person inferred joins. |
| AttributionDecision | New append-only | Subject/episode/conversion/cash scope, model/version/window, evidence IDs, source/campaign weights, reason and supersession. |
| MarketingSpend | Extend existing MarketingSpend | Preserve manual source/date totals. Add account/campaign/currency/source revisions and explicit completeness intervals; deduplicate manual/provider overlap. |
| ConnectorSyncState | New | Connection/object stream cursor, watermark, bounded coverage, last success/error, gap and reconciliation status. |
| IntegrationEventInbox | New | Authenticated delivery, durable state, idempotency keys, safe payload, adapter/schema versions, attempts and effect references. |
| UnmatchedEventReview | New | Links accepted observations to unresolved identities/dependencies/conflicts; authorized disposition and replay. |
| AuditEvent | Extend existing audit patterns | Common audit envelope over immutable financial/appointment histories and new connector/identity decisions. Generic Activity alone is insufficient for tamper-resistant evidence. |

Also reuse WebFormSubmission as a source object; existing outbound WebhookDelivery as a durability pattern only; Tasks for authorized follow-up; invoice/Payment matching as financial reconciliation evidence. No existing invoice value enters collected-revenue totals.

## Relationships and invariants

Practice owns locations/sites/services/connections, people, all events and all decisions. Agency grants reference a practice and capabilities but never confer database bypass. One person can have multiple episodes and external identities; an episode can have multiple inquiries and appointments; an encounter can lack a booking; treatment can span encounters; a transaction can be unresolved or allocated across patients/services only through explicit conserved allocations.

Every tenant row has org_id, immutable creation metadata and appropriate indexes. Composite same-org relationships or equivalent database triggers cover every link, including review/correction/supersession targets. Forced RLS applies to new tables under a non-superuser NOBYPASSRLS application role. Test direct SQL and API foreign links. Tenant context comes from verified credentials, not body/header choices.

Database uniqueness: `(org, provider_namespace, object_kind, external_id, incarnation)` for source identities; `(connection, external_event_id)` for transport identity; `(org, provider_namespace, transaction_id, incarnation, transaction_component)` for financial business identity; one active identity decision per external person reference; one effective new-patient conversion per `(org, person, definition_version, scope)`; reports select exactly one definition version and effective decision, never sum versions; unique durable write key `(org, economic_effect_id, effect_kind)` independent of delivery, mapping and projector versions; versioned read-model key `(projection_run_id, canonical_observation_id, effect_kind, object_key)`. A provider namespace persists across credential rotation and reconnection to the same account; connection IDs do not define financial uniqueness.

Supersession is append-only, same-org, acyclic and restricted to compatible object/event kinds. Concurrent finalization locks the subject/business key; unique constraints provide the final guard. Foreign IDs are validated at resolution time, never trusted because a UUID parses. Index org/time/status, namespace/external ID, pending due work and review state; partition only when measured load warrants it.

## Canonical envelope, version 1 proposal

```json
{
  "schema_version": "1.0",
  "event_type": "appointment.booked",
  "external_event_id": "TEST-booking-event-017",
  "source_object": {"kind": "appointment", "id": "TEST-appointment-42", "revision": "7"},
  "occurred_at": "2026-10-01T14:00:00-05:00",
  "source_timezone": "America/Chicago",
  "external_person_refs": [{"kind": "patient", "id": "TEST-patient-18"}],
  "location_ref": "TEST-clinic-2",
  "service_ref": "TEST-exam",
  "data": {"starts_at": "2026-10-09T10:00:00-05:00", "ends_at": "2026-10-09T10:30:00-05:00"},
  "evidence_refs": ["TEST-booking-readback-017"],
  "supersedes_external_event_id": null
}
```

This is the **adapter-normalized contract**, not a requirement that vendors send this JSON. Server stamps org_id, connection_id, provider_namespace, received_at, ingest mode, raw/safe-payload hashes, authentication evidence, mapping_version, trust classification and processing metadata. If a vendor body includes tenant/account identifiers, compare them with the connection binding and reject mismatches. The caller cannot set verification, patient UUID, actor, financial sign or admin capabilities directly.

Store canonical payload hash separately from raw transport digest; semantically identical canonical retries can have different delivery headers. Define canonical serialization per schema, preserve submitted digest and reject same event ID with changed semantic content. Date-only evidence retains its precision; do not fabricate midnight-level ordering. Missing times remain unknown with received_at separate. Currency is ISO code plus integer minor units and known exponent; don't force all currencies into two decimals. Legacy USD Receipt remains decimal under its existing rules.

Consent evidence records policy/version/purpose/status/capture time/site and withdrawal, separate from clinical processing authority. No raw cookies, IPs, full query strings, authentication tokens or free-text chart content in the default event schema. Approved opaque acquisition references are sensitive linkage metadata, not authentication credentials. Adapter-specific fields remain restricted, versioned and allowlisted, not an unlimited JSON escape hatch.

## Event vocabulary and payload rules

| Event | Required subject/data | Result and restrictions |
|---|---|---|
| marketing.touch_observed | Site/session or separately authorized linked episode; source evidence/time | Observation only. Unknown valid. Never updates Patient.original_* fields. |
| inquiry.created | Stable submission/call/chat/staff request ID, channel, occurred time | One inquiry; candidate person/episode linkage may remain unresolved. |
| inquiry.qualified / inquiry.disqualified | Inquiry/episode, reason, authorized actor/source | Qualification revision; no automatic clinical verification. |
| appointment.requested | Source request ID, requested interval | Intent only; not counted as booked. |
| appointment.booked | Stable appointment ID, confirmed state, interval | Initial confirmation once; future retries/rebook changes preserve identity. |
| appointment.rescheduled / appointment.cancelled / appointment.no_show | Appointment ref, source revision, new interval or status/reason | Update effective state by authority/version; preserve prior observation. |
| appointment.attended | Encounter/attendance ref, appointment optional, effective time, authority evidence | Does not by itself establish new patient or treatment. |
| patient.identity_linked | Decision ref, source and canonical references | Generated by reconciliation; never a blind vendor command to merge. |
| patient.new_status_decided | Person, qualifying encounter, scope, history coverage, policy version | Generated decision new/existing/indeterminate; requires E's evidence gates. |
| consultation.completed / treatment.completed | Outcome key, person/encounter, time, service/location if evidenced | Minimal clinical outcome; provider assertion separately classified. |
| payment.recorded / payment.authorized / payment.captured / payment.settled | Transaction ID, amount/currency, payer class, source status/time | Different facts/states of one transaction; not four revenue entries. |
| refund.recorded / refund.settled | Refund ID, original payment reference, amount/currency/time | Wait for missing payment; validate budget/ownership; no anonymous negative receipt. |
| payment.reconciled / payment.disputed / chargeback.posted / chargeback.reversed | Original transaction and reconciliation/dispute evidence | Reconciled is a decision; reversals have distinct keys and accounting treatment. |
| conversion.corrected / identity.link_revoked | Target decision/event, reason, replacement evidence, actor | Supersede projection, preserve evidence and invalidate dependent metrics. |
| relationship.reactivation_qualified / referral.recorded | Episode/person, policy or referral category | Existing/new status remains separate; referring patient's identity omitted by default. |

Source status snapshots are observations, not automatically new transitions. No universal event emitted solely because an API response was 200/201/202. Unknown source statuses quarantine until mapping is reviewed. Schema minor versions may add optional fields; required-field or semantic changes require major version and compatibility fixtures. Retain old parsers during documented replay windows.

## Durable processing and recovery

1. Validate credential/signature and replay window, active grant, account binding, payload size/content type/schema and permitted event types. Store safe rejected-request metadata without retaining attacker PHI. Return 401/403/422 as appropriate; vendor protocol status details belong to the manifest.
2. Atomically insert inbox and durable pending-work row. Duplicate same ID/hash returns original receipt; changed content returns conflict and audit. If DB commit fails, no success acknowledgment. Use vendor-required success code after commit only.
3. Worker claims bounded work using locks/lease; sets tenant context inside transaction, rechecks current grant and connection generation, normalizes with pinned mapping, resolves same-tenant IDs and dependencies, checks business-key dedup and authority.
4. Atomically write canonical observation, business effect or unresolved-review item, audit and processing result. Crash before commit leaves no effect; crash after commit/retry cannot duplicate effects. Clear tenant context in finally; pooled connections cannot carry it between jobs.
5. Retry transient network/rate/DB conflicts with bounded exponential backoff and jitter, honoring Retry-After. Proposed default: six attempts over 24 hours, then review; missing prerequisites enter blocked state, not a retry storm. Sweep expired leases and orphaned pending rows. Metrics cover oldest pending age, failure and coverage gaps.
6. Poll with overlap and stable object versions; checkpoint only after the page's observations are durably accepted. Backfill uses the same contract, coverage bounds and dedup, labeled historical; it never triggers outbound messages. Reconcile periodic source counts/totals and modified objects, not only webhooks.
7. Out-of-order revisions cannot regress state. Where provider revision/ordering is absent, fetch current authoritative state; ambiguous incompatible snapshots require review. Do not sort arrival time as business truth. Same transaction observed by PMS and processor needs explicit crosswalk/reconciliation; preserve both observations but count one economic collection.
8. Replay from an authorized review action records actor, reason, old/new mapping and report impact. Rebuild projections into a new version, compare totals, then publish atomically. No silent destructive replay or automatic mutation of original capture.

Accepted inbox states: accepted → processing → applied / blocked_identity / blocked_dependency / conflict / quarantined / retry_due / terminal_failure; revocation uses quarantined with reason=revoked, not a second undocumented suspended state. Terminal failure is retained and reviewable, not lost. Transport acknowledgment is independent of projection state.

## Legacy ledger and service-actor compatibility

Current attribution migration `0016` explicitly validates an active human practice administrator. Financial audit triggers require actor/reason and immutable correction relationships; administrator-only financial action authorization is enforced in application services. Do not assume every financial trigger independently checks administrator role. A live worker must **not impersonate an administrator** or weaken those triggers. Proposed implementation adds an explicitly authorized service-actor audit path and domain services, with separate scope checks and migration review; until approved, normalized financial observations remain shadow evidence and do not write Receipt. Existing manual receipts stay manual evidence. The bridge must prove invariant equivalence, provenance, one business transaction/one receipt effect and concurrent refund budget protection before activation.

No migration is included here. Before any schema work, rehearse additive migrations on a disposable PostgreSQL copy with fictional fixtures, preserve existing rows/constraints and verify downgrade/irreversibility policy. Do not drop legacy audit tables or rewrite original source fields.

## Additional lifecycle coverage, without expanding the first pilot

Use optional canonical event types `appointment.waitlisted`, `appointment.waitlist_removed`, `appointment.provider_changed`, `treatment.recommended`, `treatment.plan_accepted`, `treatment.plan_declined`, `care.followup_requested` and `relationship.referral_generated`. Each includes the stable source object, effective time, version, actor/authority evidence and same-practice relationships required by the base envelope. Recommendation/acceptance includes a minimal plan reference and approved service codes, never automatic cash or completed-treatment credit. A waitlist entry is an independent request reference and cannot increment confirmed bookings. Provider/location changes preserve appointment identity and prior revisions.

Multiple appointments for one patient are representable as distinct source appointment IDs, including simultaneous bookings. Existing local patient conflict checks remain unchanged; an authoritative imported overlap is preserved as evidence and flagged for scheduling review instead of being silently discarded or forced through the local booking command. Whether users may intentionally create overlaps is a separate practice scheduling policy, not necessary for the attribution pilot. Appointment type/provider/resource mapping must remain distinguishable from treatment delivered.

Inquiry channel taxonomy includes form, inbound_call, chat, sms, portal, booking_request, staff, walk_in and referral; call disposition includes missed, unanswered and answered without turning any into qualification automatically. Marketing evidence keeps source, medium, campaign and sanitized landing-page/site references separately. Offline advertising, community events and walk-ins use explicit source categories when reported; absent evidence is Unknown, never assumed direct. These are optional contract extensions implemented only when an approved connector/workflow supplies the facts.


## D1 — Contract ownership and module boundaries

All proposed code remains in the existing Django deployment. A proposed `integrations` app owns service principals, provider namespaces, connections, inbox/attempts, sync coverage and credential adapters. `patients` owns clinical/identity decisions, episodes and economic reconciliation; common/contacts remain identity and human authorization infrastructure. Reporting reads those facts and cannot write them. Adapters call canonical services, never manipulate Patient/Receipt directly. This is module organization, not new infrastructure or a standalone identity service.

| Proposed service | Actual reusable baseline | Extension and boundary |
|---|---|---|
| Authenticate/authorize connection | `common/models.py` Profile/PAT concepts; `common/permissions.py`, `patients/access.py`, existing JWT middleware | Separate service principal plus practice/scope checks; do not select an arbitrary admin or reuse org-key patient access. |
| Receive/normalize/deduplicate | `patients/intake.py` strict input, atomicity and sandbox tests | Dedicated inbox contract; sandbox endpoints and namespace remain unchanged. |
| Claim/retry/reconcile stream | `webhooks/tasks.py`, `common/tasks.py` tenant context, existing Celery | New inbound work rows; reuse pattern, not outbound delivery table. No network call while holding long database transaction/connection lock. |
| Resolve person/episode | Contact/Patient; `contacts/access.py`; `patients/serializers.py` | Typed evidence-linked decisions, contact methods, unresolved acquisition. Weak matching never calls existing link-by-email convenience paths. |
| Project appointment/outcome | `patients/appointments.py`, AppointmentChange/JourneyEvent | Separate imported observation and authority-aware projection; preserve existing local conflict rules. |
| Reconcile financial facts | `patients/{matching,reconciliation,allocations,corrections,exclusions,balances}.py` | Source/economic crosswalk and shadow evidence first. Existing administrative action services keep their restrictions. |
| Calculate reports | `patients/reporting.py`, `common/org_time.py` | New versioned report service; no change to legacy UTC/USD Growth semantics. |
| Audit/review/export | Existing append-only domain histories, `patients/statements.py` | Integration audit/review is new; generic Activity and existing read logging are not proof of complete sensitive-read audit. |

## D2 — Schema implementation profiles and compatibility

These profiles apply to **every entity** in the mapping table. Each future migration must specify its profile plus exact fields/indexes and rehearse against the reviewed baseline. No migrations are created in this package.

| Profile and entities | Why / existing reuse | Constraints and migration implications | Required tests |
|---|---|---|---|
| P0: Practice, Contact/Person, Patient, Lead | Preserve Org, Contact, Patient IDs and Lead pipeline | Existing Patient.contact and original capture stay immutable; Contact/Lead email uniqueness unchanged. New optional references additive; no inferred backfill or wholesale identity merge | Legacy snapshots unchanged; foreign links rejected; original-source guard; all prior authorization cases |
| P1: Agency, Location, Website, Service, Provider/Clinician, MarketingCampaign | Missing canonical directories; existing Org metadata is not a directory | AgencyClientGrant practice-authorized; nullable new FKs to org-scoped directories; unique org/code or provider external key; approved crosswalk backfill only. Websites have explicit org binding even when domain is shared | Self-grant escalation denied; duplicate code rejected; foreign location/site/service denied; old free-text fields still readable |
| P2: IntegrationConnection, ConnectorSyncState, IntegrationEventInbox, UnmatchedEventReview, AuditEvent | No live service inbox in sandbox; reuse outgoing durable-task pattern | Additive tables, RLS and deny-by-default scope; stable namespace, transport uniqueness, lease/generation and stream-specific coverage; append-only evidence/audit separated from mutable queue state | Crash/restart/retry, forged fields, revocation races, independent stream coverage, retention and direct-SQL tests H/J/K/X |
| P3: ExternalIdentity, IdentityMatchDecision, Inquiry/AcquisitionEpisode, AcquisitionSession, MarketingTouch, AttributionEvidence | Existing identity/event require Patient; pre-patient and reversible relations need separate evidence | Typed source reference plus incarnation; one active link per reference generation; versioned memberships; observation payload immutable; preserve current AttributionIdentity rows untouched | Household/reused IDs, unlinked events, reverse link, pre-lead time, webform duplicates, simultaneous review E/F/G/R/S |
| P4: Appointment, Encounter/Attendance, VerifiedConversion, TreatmentOutcome | Reuse Appointment/Change/JourneyEvent for compatible operational projection | New evidence/authority refs additive. Requests/waitlists/imported overlaps stay canonical observations until valid projection; do not insert unsupported Appointment.status. Conversion decision uniqueness includes scope/policy; typed relationships, no unguarded GenericForeignKey | Request≠booking, encounter≠appointment, chronology/tie/history corrections, concurrent newness, foreign clinical refs A/C/O/T |
| P5: FinancialTransaction | Preserve Receipt, refund/correction/exclusion/match/allocation histories | Add source observation/economic effect/allocation records; typed same-org/currency FKs; conserved positive magnitudes, independent refund/reversal kinds; effect identity independent of projector. No reassignment of immutable Receipt.patient | Multi-feed/multi-leg dedup, partial insurance/refund/chargeback, currency, unlink, service-actor denial B/H/I/Q/R |
| P6: AttributionDecision, MarketingSpend | Reuse original capture and manual spend; new calculation/coverage needed | Do not remove unique(org,source,date) on legacy MarketingSpend to squeeze in campaigns. Add detailed SpendFact/Coverage and provenance mapping; select nonoverlapping authoritative facts. Decisions append-only with one current version per subject/model | Missing vs zero, partial spend, source taxonomy, cohorts, timezone mismatch, known/unallocated cash and restatement N/U/V/W |

Supporting logical records: **ContactMethod** (P3), typed **SourceObjectReference** (P3; generalized ExternalIdentity), **EconomicEffect/Allocation** (P5), and **SpendFact/Coverage** (P6). These are explicit extensions, not a new person platform. AttributionEvidence can be typed links to canonical observations rather than a duplicate raw-payload table. UnmatchedEventReview may be a case/history over inbox references; processing attempts and canonical observations must remain distinguishable even if physically consolidated.

## D3 — Household contacts and source identity incarnation

`contacts.Contact` enforces `unique_contact_email_per_org` over lowercase nonblank email; `PatientSerializer` rejects duplicate email and suggests linking. `Lead` also has per-org email uniqueness. Therefore two household patients **cannot** be created by supplying the same primary Contact.email through today's serializer. Proposed ContactMethod stores org/contact, kind, normalized value, relationship (self/guardian/shared), evidence and validity intervals. Its value is not globally unique; prevent only duplicate active method rows for the same contact/kind/value/relationship. Keep current Contact.email uniqueness: preserve an existing primary email, and leave a newly created household contact's primary email blank when shared, retaining the shared method through the protected extension. No invented email addresses or identity merge. This needs an approved future intake/UI change and migration; current behavior is not advertised as solved.

`webforms/service.py` merges legacy lead submissions by email and may notify assigned users. Reuse submission IDs and validated payload selection only. `accepted_duplicate` is not evidence of the same patient or duplicate economic inquiry; retain distinct submission records unless a stable retry key proves retransmission. The new protected acquisition path must not call legacy Lead/Case creation, email merging or notification side effects. Do not reclassify old submissions or expose old payloads to agency developers.

Provider IDs can be reused after deletion, reset, account migration or source merge. Add an `incarnation` established from documented stable generation/creation evidence or authorized review; an event's ambiguous incarnation is unresolved. Rotation/reconnect alone does not change it. Conflicting demographics suspend the link rather than silently move it. Maintain validity intervals and superseding decisions; past events bind the applicable source incarnation. A provider namespace is stable across credentials but cannot be relabeled to another vendor account or tenant. Provider merge/delete is an observation and review trigger, not a command to delete local patients.

## D4 — Trust, replay and coverage contract

Separate validated ingress envelope from canonical observation. Authenticate, bound size and validate provider-schema allowlist before durable receipt; normalization can then fail safely inside the durable pipeline. Store the minimal encrypted, policy-approved normalized-input subset needed for replay plus its original digest and adapter version. If exact raw bytes are required for signature validation, validate in memory before discarding; retain only under exceptional approved quarantine policy. Arbitrary provider bodies never become permanent replay storage. Unsupported but authenticated schema versions get a bounded quarantine receipt only if the manifest allows safe retention; otherwise reject and record safe metadata.

A canonical observation has `observation_id`, `source_object_reference`, schema/mapping versions, occurred_at nullable with precision, received_at, effective interval, provenance and normalized data. The normalizer stamps canonical type only within its approved authority manifest. Browser/server-form credentials can submit acquisition facts, never clinical/newness/cash decisions. Decision events (`patient.identity_linked`, `patient.new_status_decided`, `payment.reconciled`, corrections/revocations) are emitted by internal domain services only. External input cannot grant its own verification tier.

Transport dedup identifies delivery; source-object revisions identify observations; stable economic-effect identity guards irreversible writes. Projection version belongs only to disposable derived views. Rebuilding a projection must never invoke cash creation or human correction commands. Changed mapping results produce a preview/difference decision and explicit authorized correction, not another ledger effect. A source revision can supersede an observation while retaining the source object's identity. Multiple partial captures/refunds have distinct provider subtransaction IDs, not amount/time-generated business keys. Missing stable keys block cash projection.

For every connection/object stream, coverage records account/location inventory, source timezone, history-from/through, provider limit/truncation, cursor/page completion, ingestion checkpoint, applied checkpoint, unresolved counts/amounts and last reconciliation. A durably ingested page can advance ingestion cursor but not projection completeness while blocked events remain. Unknown provider outage gaps cannot be inferred empty. Declaring coverage requires independently approved expected source inventory; successful paging alone does not prove all practices/locations/accounts were included.

Queue task arguments carry opaque job IDs only, not source payloads. Use bounded batches, per-practice fairness and dead-letter alert ownership. Perform provider network fetch outside effect transactions; revalidate authorization generation in the final short locked transaction. Retry uses bounded attempts and next_attempt_at, terminal work remains reviewable, and replay requires retained authorized evidence. If evidence expired/deleted, mark replay unavailable rather than reconstructing guessed facts.
