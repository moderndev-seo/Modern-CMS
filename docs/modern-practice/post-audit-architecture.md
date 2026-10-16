# Proposed architecture and attribution roadmap

Status: **planning only**. The owner authorized authorization and CI remediation now; the architecture and integration work below requires a separately approved milestone. No live connection, infrastructure deployment, or new identity model is implemented by this plan.

## Product boundary

Keep the modular Django application, SvelteKit, PostgreSQL forced RLS, Redis and Celery. A practice remains the patient-data tenant. Agency membership must never be a shortcut to membership or administration of every client practice. Existing organizations, Contact/Patient IDs, event timestamps, first touch, receipts, refunds, immutable correction/reconciliation records and explicit Unknown reporting remain intact.

| Boundary | Proposed responsibility | Access |
| --- | --- | --- |
| Agency operations | Staff, client contracts, sites, SEO, advertising, content and deployment references | Explicit agency-to-client grants, bounded by capabilities and optionally locations/sites |
| Protected practice | Identity, inquiries, appointments, new-patient decisions, outcomes and cash evidence | Active practice membership, explicit capabilities and existing contact sharing; audited sensitive reads/exports |
| Controlled reporting | Channel/service/location totals, spend, completeness and confidence | Aggregate reporting grant; no patient identities or event-level patient exports to agency staff by default |
| Integration intake | Vendor credentials, durable events, replay, reconciliation and identity review | Tenant-bound service identity, narrowly scoped source/operations; never an arbitrary human admin |

The code's current three patient capability fields are a small compatible repair, not the final agency role model. Existing administrators retain authority. Patient finance read is independent; reconciliations, corrections, exports and financial writes remain administrator-only. Future named roles compose explicit grants instead of creating implicit access from job titles.

## Incremental relationships

- **AgencyClientGrant:** connects an agency and practice with approved capabilities, resource/location limits, grantor, validity and revocation. An agency user needs both agency membership and an active client grant. No grants are inferred from website ownership. Protect the grant administration path from self-escalation and credential minting.
- **Location, Website, Service:** practice-owned IDs with composite tenant-safe relationships. Sites can map to multiple practice locations through explicit joins; approved landing pages map to a service and location when known. Keep Unknown when mappings are absent. Existing organization address/website and free-text appointment location are preserved while optional references are added; backfill only through reviewed mappings.
- **Website management:** first store CMS kind, approved domains, content/revision inventory and deployment references. Support agency-built and client-controlled sites. A connector requests scoped CMS changes; publishing is separately authorized. Keep build/deployment execution and secrets outside patient request contexts. Do not replace every client's CMS or build a new deployment platform in the first integration.
- **Person versus acquisition:** retain Contact as identity and Patient as the current protected journey. Evaluate extending the existing Lead for an inquiry/acquisition episode before introducing another lead model: it has B2B fields and lifecycle semantics that may not fit repeated patient inquiries. A person can have several acquisitions and sources over time without rewriting their original attribution. Do not equate one Contact, one inquiry and one new patient.
- **ExternalSubjectReference:** tenant + connection + source-system subject ID maps to an existing patient after an approved identity decision. Provider ID is authoritative only within its documented namespace. Preserve the current sandbox identity IDs/history when migrating to this model.
- **IdentityLinkDecision:** evidence, candidate references, reviewer or deterministic rule version, timestamp and reversal/supersession. Names, phone numbers and emails generate candidates only; shared household contacts, reused phone numbers and typos require review. Never automatically merge on those alone.
- **NewPatientVerification:** source-system evidence, prior-patient search result, event date, location scope, verification rule version and decision actor. Represent verified new, existing, pending and disputed separately. A newly created lead does not qualify.

## Evidence and attribution contract

Store immutable observations separately from derived attribution. Each observation carries practice, connection, external event ID, subject reference if known, event type, provider occurrence time, receive time, provenance, content hash, evidence status and schema version. Do not log raw payloads or credentials. Minimize retained payloads; restrict and expire any necessary protected raw evidence.

Preserve original source and later touches. Future pre-lead visit/call evidence belongs in an acquisition stream, rather than evading the current journey rule that events cannot precede lead creation. Version derived models and keep the evidence and rule that produced a result. Do not retroactively relabel Unknown without a recorded, reviewable decision.

Confidence is not a fabricated probability: use categorical evidence such as manually recorded, validated provider assertion, reconciled against provider API, or disputed. Distinguish identity confidence, source confidence, occurrence verification and financial reconciliation instead of compressing them into one misleading score.

Counts and revenue require explicit definitions:

- Leads: unique acquisition episodes accepted in the reporting window; separate from unique people.
- Booked and attended: distinct verified appointment records, with cancellation/no-show/correction history. Receipt of a webhook alone is not attendance.
- New patient: recommend **first completed attended encounter within the entire practice organization, with a source-system check for earlier encounters**. Until approved and supported by history, report pending verification, not verified new. A first visit at another branch of the same practice is not automatically a new patient.
- Collections: receipts less refunds, separated by currency and financial evidence status. Manual records remain useful but are not provider-verified settlement. Pending/failed/authorized payment events are not collections; refunds require the original transaction and actual provider refund state. Internal charge credits are not cash refunds.
- First-touch attribution: assign eligible collected revenue to the earliest qualifying, consent-permitted acquisition observation under an approved lookback/window rule. Retain today's original-source reporting alongside the proposed version, clearly labeled. Report new-patient acquisition value separately from repeat-patient revenue.
- ROAS: attributed net collections divided by matching source spend. Missing, zero or incomplete spend yields unavailable with a reason. Do not fill missing periods with zero. CPA uses verified new patients and complete matched spend; zero verified patients yields unavailable, not infinity.
- Date definitions: retain current UTC cash/event-period report. Add explicitly labeled acquisition cohorts only as separate reports. Do not sum event-period funnels as though every stage came from the same cohort. Practice timezone support requires an approved transition rule.

## Protected ingestion and delivery

Use connection-specific, revocable server credentials, encrypted secrets with rotation metadata, least-privilege scopes and audited administration. Website JavaScript holds no administrator JWT, PAT or reusable privileged credential. A practice's server-side form adapter calls a narrowly scoped receiver; public browser submission, if later needed, requires its own abuse/consent design and must not masquerade as trusted provider evidence.

Verify provider signatures over the original bytes, enforce timestamp/replay windows where supported, derive practice and connection from credentials rather than payload IDs, and enforce tenant-safe foreign links in both application and database. Restrict payload shape/size and normalize only known fields. A successful response means durable receipt, not verified real-world completion.

Persist an inbox record before processing. Unique connection + external event ID plus payload hash handles retries: identical replay returns the saved result; conflicting replay is quarantined. Resolve transaction identifiers independently of webhook event IDs so two notifications cannot create two cash receipts. Use atomic state changes and row locks with existing financial guards.

Unknown identities and out-of-order events enter a durable unmatched/review queue with reason, retry schedule, attempt history and operator tools. Refund-before-payment and appointment-before-lead must not be discarded or guessed. Reprocessing is explicit and idempotent; review actions record actor/evidence. Failed processing must not lose accepted inbox records. Celery provides bounded retries/backoff; a reconciler compares provider checkpoints, missing IDs, counts, totals and freshness. Alerts describe operational failures without patient details.

Read/export audits must record actor/service identity, practice, purpose, record/resource, action, time and decision without duplicating sensitive content. Apply retention and access rules to audit logs themselves. Include revocation, failed authorization, grant changes, credential rotation, identity decisions and correction/export history. Existing authentication/security logging is not a complete patient-access audit.

## First end-to-end integration proposal

Recommended scope: **one fictional/sandbox practice, one approved website form, one booking/practice-management source, and one payment source with stable patient/appointment/transaction IDs**. Actual vendors are still unknown; no claim of universal connectivity. Prefer one practice-management vendor that exposes both appointments and payments to reduce identity ambiguity. Evaluate its API, webhook signing, historical retrieval, sandbox access, stable IDs, rate limits and applicable contractual/privacy safeguards before selection. Add one call-tracking source only after the website path passes the same identity contract.

| Stage | Accepted evidence | Failure/unknown behavior |
| --- | --- | --- |
| Organic/paid/GBP/direct/referral introduction | Consent-permitted first-party source parameters, approved referrer classification and landing-page ID; distinct GBP tagged links | Preserve Unknown on missing, conflicting or disallowed evidence; absent referrer alone does not prove direct |
| Visit or call | First-party random acquisition ID or provider call ID; occurrence time, approved page/service/location IDs | No identity claim from anonymous visits; exclude call content/recordings/transcripts by default |
| Website lead or phone inquiry | Server-validated form receipt or accepted inquiry linked to acquisition evidence | Duplicate submission idempotency; unsupported identity held for review |
| Appointment booked | Provider appointment ID + provider subject reference and confirmed state | Pending/out-of-order queue; cancellation/reschedule retained |
| Appointment attended | Provider completed encounter/attendance state reconciled to API, not webhook delivery | Pending/disputed if source cannot prove attendance |
| Verified new patient | Authoritative patient reference and approved prior-encounter check | Existing/pending remain distinct; no email/phone/name-only automatic link |
| Collected revenue/refund | Stable source transaction ID, correct patient mapping and validated final state; periodic reconciliation | Pending payment excluded; duplicate events no additional cash; unmatched refund queued; disputed amounts labeled |

Google products complement this evidence; they cannot provide an authoritative individual-patient ledger. GA4 and Search Console aggregate metrics describe traffic and search, GBP describes local discovery, and Google Ads describes spend and platform-attributed conversions. They cannot by themselves prove that a specific patient attended, was new, or paid. A matched journey establishes attributed revenue under the stated model, not causal incremental lift or a complete view of unobserved journeys.

Do not send PHI to Google Analytics, Google Ads or other marketing destinations. Hashed patient contact data is not treated as anonymous. Keep patient names, emails, phone numbers, diagnoses, appointment details, protected URLs and patient-level revenue out of marketing payloads. Event naming, approved URL fields, consent, collection basis, retention, vendor agreements and any future outbound conversion export require privacy/security review before activation. Website control makes instrumenting the approved path possible; it does not remove those requirements. This document is not a HIPAA-compliance claim.

## Ordered subsequent milestones

1. **Protected inbox and service identity:** sandbox credentials, tenant validation, signature adapter contract, replay/conflict handling, unmatched queue and read/decision audit. No Google export or production traffic.
2. **One source pair and identity verification:** booking/practice-management and collections adapter, approved new-patient definition, reconciliation and end-to-end fictional acceptance.
3. **Calls and additional CMS adapters:** call IDs and inquiry matching; mixed agency/client websites through a common approved capture contract, not universal plugins promised in advance.
4. **Marketing reporting:** read-only Google Ads spend, GA4, Search Console and GBP connectors with tenant-specific grants/credentials, freshness and completeness. Separate aggregate reports from protected patient evidence. Distinct GBP source classification requires a backward-compatible enum/mapping migration.
5. **Agency operations:** client/location/site/service grants, content inventory/revision workflows, local SEO/GBP operations and separately approved publishing references. Keep patient access opt-in.
6. **Operational readiness:** load/concurrency and accessibility acceptance, backup restoration drill, production secret/rotation strategy, monitoring, incident response, privacy/security review, vendor contracts, data retention and team training. Pilot a bounded client only after acceptance; do not equate feature completion with production approval.

## Owner decisions that remain

| Decision | Recommended default | Alternatives and consequences |
| --- | --- | --- |
| New-patient scope | First attended encounter across the practice, with historical verification | Per location/service counts growth differently and can double-count existing patients; incomplete history stays pending |
| First real source pair | One sandbox-enabled practice-management system with appointments and payments | Separate booking/payment vendors require authoritative crosswalks; unsupported vendors need reviewed imports and lower evidence status |
| Staff grants | Patient capabilities off for regular members; approve named practice staff and contact assignments | Broad role defaults reduce administration but expand exposure; agency staff retain aggregate-only access |
| Marketing reports/privacy | No patient exports; only approved aggregate reporting to trusted staff | Small-cell suppression, broader agency access or any conversion export needs explicit security/privacy approval and a threat model |
| Attribution window and repeat revenue | Preserve current immutable first touch; separately version new acquisition-cohort rules after approval | Lifetime, time-limited and per-episode credit answer different questions; choosing one changes ROAS/CPA interpretation |
| Collection and retention policy | Minimal allowlisted metadata; no call recordings or marketing identity payloads | Additional tracking/payload retention requires documented purpose, consent/collection review, retention and vendor approval |

## Next bounded milestone acceptance

Build milestone 1 above only after the present remediation is approved and merged and the owner separately authorizes implementation. Dependencies: accepted permission defaults, service-identity administration policy, sandbox vendor event examples, and test fixtures without patient data. No real credentials are required to implement the adapter contract.

Acceptance: revoked/wrong-scope/wrong-tenant credentials rejected; forged foreign IDs rejected by API and database; invalid signatures/replays rejected; accepted events survive worker failure; identical retries yield one stored effect; conflicting duplicates quarantined; unresolved identities and out-of-order refunds persist without cash writes; reviewer linking is audited and reversible by a superseding decision; original source unchanged; cash/refund totals reconcile; marketing responses contain no patient identities; test suite passes under forced RLS. No live connector, automatic new-patient claims or deployment is included.
