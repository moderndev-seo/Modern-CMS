# A — Executive architecture assessment

> **Current publication status — October 16, 2026:** Design 0.2.0 and bounded A01–A10 are approved for fictional, isolated Phase 2A; Group B/C remain pending. The owner confirmed independent human review without outstanding blockers and authorized security PR #1 to merge; GitHub records merge `1e00ae5d175e0ace627b2dc5fc68e25a73cb41dd`. All seven checks passed on reviewed head `81ecc87672e35a00d45a9c40b2f83d578a364f2a`. This separate documentation PR is authorized for publication after checks. Phase 2A remains unimplemented and gated on documentation review, separate owner merge approval and actual merge. No live connections, deployment or Phase 2B–E implementation. Earlier gate/status snapshots below are historical, not current instructions.


> **Historical adoption record 1 — superseded by approval record 2:** The owner accepted design **0.2.0 as the technical baseline**, subject to unresolved policy approvals in J. This supersedes the earlier “final validation draft / technical approval pending” status only. Proposed policy defaults remain pending. Phase 2A planning is authorized; implementation and GitHub publication actions are not. See [adoption and Phase 2A handoff](I-roadmap.md#adoption-and-phase-2a-handoff) and [owner approval register](J-product-decisions.md#group-a-owner-approval-register).


Design 0.2.0 · Technical baseline and narrow A01–A10 approved; Group B/C pending.
**Review draft; implementation requires separate authorization and the remediation merge gate.**

## Assessment

Modern-CMS has a suitable foundation for a universal integration model. Keep Django/DRF, SvelteKit, PostgreSQL forced RLS, Redis/Celery and the current CRM. Extend the existing domain and evidence model within a modular monolith. No new message broker, analytics database, microservice split or EHR replacement is necessary to prove the first end-to-end journey.

The system can currently show a locally recorded journey and attribute recorded receipts less refunds to an original source. It cannot yet claim automated, independently verified acquisition-to-collection coverage across vendors. The blocking gaps are durable ingestion, constrained service identity, cross-system identity reconciliation, authoritative outcome evidence, historical new-patient verification and completeness-aware reporting. Vendor access and healthcare data permissions are additional operational gates, not features a schema can solve.

## Evidence-based inventory

| Status | Existing component | Assessment and precise extension |
|---|---|---|
| Implemented and previously tested | Org/Profile/User, Contact and practice Patient; explicit patient/outcome/finance capabilities | Preserve authentication and Contact/object permissions. Add explicit agency grants and restricted integration principals; agency ownership must not grant patient access. Shared contact methods need D3’s additive design because Contact.email is currently unique per practice. |
| Implemented | Patient original source/campaign/page/time; separate JourneyEvent touches | Preserve these immutable capture fields. Add pre-inquiry observations and episodes; never reinterpret current fields as verified lifetime first touch. |
| Implemented | Appointments, append-only appointment changes and independent journey outcomes | Reuse operational UI and audit. Add provider appointment references, encounter evidence and authority rules; requested booking is not confirmed booking. |
| Implemented | Receipt/refund ledger, matching, reversals, credits, allocations, correction and exclusion safeguards | Preserve all integrity checks. Add external transaction evidence and reconciled projections around the ledger. An invoice or PMS ledger posting is not proof of settled cash. |
| Partial for automation | TEST-only AttributionConnection/Identity/Event and synchronous intake | Reuse normalization/idempotency tests and concepts. It has no live service credential, durable failed-event inbox or reconciliation queue. Add production ingestion alongside it; do not remove TEST restrictions. |
| Partial for acquisition | Consent-controlled local website module | Reuse allowlisted capture and fixed-session tests. It sends nothing; earliest observation is session-local, not lifetime acquisition. Add approved server submission and protected acquisition continuity. |
| Implemented pattern | WebhookEndpoint/Delivery and Celery delivery tasks | These are outbound. Reuse durable scheduling, leases/backoff and explicit tenant context as patterns; do not use the outbound table as an inbound event inbox. |
| Implemented foundation | WebForm, fields, submissions and daily statistics | Reuse built-in form records and submission IDs via an adapter. Do not replace every third-party CMS or assume a form analytics counter is a verified inquiry. |
| Partial reporting | Growth, UTC activity ranges, receipts minus refunds, manual spend and Unknown | Keep labeled legacy report. Add separately versioned cohorts, verified metrics, spend coverage and freshness; do not silently restate old reports. |
| Already proposed | Multi-location/site/service organization, agency grants, durable ingestion and evidence verification | Refine the existing post-audit roadmap through B–J rather than create a competing roadmap. |
| Genuine gaps | Durable inbox, service grants, external identity decisions, verified conversions, campaign coverage and report lineage | Build incrementally after review/merge, as scoped in I. |
| Unresolved decisions | Authority of attendance/cash, new-patient scope, privacy, first vendors and retention | Defaults in J are assumptions, not accepted product requirements. |

Source inspection: `backend/patients/{models,intake,reporting,access}.py`, patient migrations through `0017`, common migration `0044`, `backend/common/org_time.py`, webforms/webhooks models and webhook tasks, `frontend/static/modern-practice/website-attribution.mjs`, and relevant Svelte server routes. Org already has timezone support; the current Growth policy is UTC. Proposed local-day reporting reuses that support.

## Preserve, extend, postpone

**Preserve:** existing practices/data, login, signed tenant context, restricted PAT behavior, forced RLS and relationship checks, append-only audit, original attribution, Unknown, refund budgets, no fake/infinite ROAS, local Messages/Reviews and existing CRM access. Keep ports 5181/8000. The original demo and remediated feature checkout are distinct; architecture approval does not deploy the remediation into the demo.

**Extend:** introduce logical agency/location/site/service/connection relationships; a durable observation pipeline with service-scoped permissions; patient identity decisions and authority mapping; qualified outcomes; financial evidence with currencies and reconciliation; versioned attribution, completeness and privacy-controlled reporting.

**Postpone:** a full website builder/deployment platform, clinical charting, bid automation, universal calendar writes, automatic patient merging, probabilistic cross-device tracking, call transcription, cross-practice identity graphs, advertising conversion uploads and every possible vendor connector. Website inventory/content/publishing can later live in a separate module with explicit publish approval and audit; its release cycle should not block acquisition evidence.

## Business implications and risks

- Universal means a stable domain and adapter contract. It cannot mean guaranteed access to every vendor. Partner agreements, practice licenses, endpoint coverage and source history may limit verification.
- Identity conservatism reduces apparent attribution coverage but avoids assigning a household member's revenue to the wrong patient. Show unresolved work explicitly.
- Marketing platforms explain exposure and cost; booking/clinical systems explain outcomes; cash sources and reconciliation explain collections. One provider is rarely authoritative for all three.
- Provider evidence is stronger than a local assertion only for the fact the provider can establish. A payment ledger can be accurate bookkeeping while still not proving funds received.
- Higher-quality reports can show fewer “verified new patients” than today's lead count. That is a corrected definition, not necessarily a business decline.
- Refunds and delayed insurance can make monthly source revenue negative. Cohort value and period cash answer different questions; both are needed.
- Attributed revenue supports traceable allocation of outcomes to observed marketing. It does not prove marketing caused incremental revenue; that needs separately designed causal studies.

## Recommended smallest proof

Two fictional TEST practices; one approved website/form adapter, one booking/clinical adapter boundary and one collection evidence adapter. Use recorded, sanitized fixtures and a vendor simulator first, including a second vendor shape mapped to the same canonical contract. Demonstrate a new patient, an existing patient, a shared-household ambiguity, delayed cash, a refund, replay and cross-tenant rejection. No live vendor is needed for this architectural proof. A separately approved pilot then validates actual vendor behavior and operational controls.


## Validation conclusion — design 0.2.0

**Ready with documented limitations for product-owner approval; not approved for implementation.** The design fits the current modular monolith after correcting household-email compatibility, external identifier incarnation, version-safe effects, financial state axes, source/date coverage and service permission boundaries. These details are difficult to change after patient data accumulates and belong in the initial contract. D owns the corrected technical invariants; E/F/G own policy semantics; J records unresolved approvals. No runtime implementation or vendor certification is implied.
