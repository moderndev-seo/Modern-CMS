# G — Agency, practice, service and healthcare data boundaries

> **Current publication status — October 16, 2026:** Design 0.2.0 and bounded A01–A10 are approved for fictional, isolated Phase 2A; Group B/C remain pending. The owner confirmed independent human review without outstanding blockers and authorized security PR #1 to merge; GitHub records merge `1e00ae5d175e0ace627b2dc5fc68e25a73cb41dd`. All seven checks passed on reviewed head `81ecc87672e35a00d45a9c40b2f83d578a364f2a`. This separate documentation PR is authorized for publication after checks. Phase 2A remains unimplemented and gated on documentation review, separate owner merge approval and actual merge. No live connections, deployment or Phase 2B–E implementation. Earlier gate/status snapshots below are historical, not current instructions.


> **Historical adoption record 1 — superseded by approval record 2:** The owner accepted design **0.2.0 as the technical baseline**, subject to unresolved policy approvals in J. This supersedes the earlier “final validation draft / technical approval pending” status only. Proposed policy defaults remain pending. Phase 2A planning is authorized; implementation and GitHub publication actions are not. See [adoption and Phase 2A handoff](I-roadmap.md#adoption-and-phase-2a-handoff) and [owner approval register](J-product-decisions.md#group-a-owner-approval-register).


Design 0.2.0 · Technical baseline and narrow A01–A10 approved; Group B/C pending.
**Proposed extensions preserve implemented patient-permissions.md. Architecture is not a HIPAA compliance determination.** Legal and operational acceptance remains separate.

## Authorization model

Request authorization is the intersection of authenticated principal, active practice grant/membership, action capability, resource/location scope, existing Contact/object visibility and event-specific authority. Membership alone does not grant patient access. Location-restricted access cannot be offered until all traversals, reports and exports enforce it; first pilot defaults to practice scope with capabilities, not unimplemented location isolation.

| Role | Recommended access | Explicitly excluded by default |
|---|---|---|
| Agency administrator | Agency/client setup, grant administration, connection health metadata | No automatic patient or cash-detail access; cannot self-grant clinical data without practice authorization. |
| SEO specialist | Suppressed source/site/service aggregates, site content performance | Patient identities, inquiry bodies, raw events, small-cohort drilldown or identified exports. |
| Paid advertising manager | Approved ad-account/spend reporting and aggregated performance | Patient lists, clinical conversion uploads, raw click-ID-to-patient mappings. |
| Website developer | Approved site configuration, fictional test events, redacted delivery status | Production form bodies, patient histories, clinical/billing systems. |
| Content manager | Content drafts and separately approved publish capability | Patient data, tracking changes or vendor secrets. |
| Client account manager | Approved portfolio/practice aggregate reports and operational status | Identified records unless separately granted for a legitimate practice task. |
| Practice administrator | Practice governance and explicit operational/patient grants | No other practice access; sensitive exports/actions remain audited. |
| Clinical staff | Assigned/visible patient and clinical outcome capabilities | Financial details unless separately granted. |
| Scheduling staff | Minimum visible patient/contact and appointment workflow | Treatment details, finance and unrelated patient histories. |
| Finance staff | Authorized patient financial workflow and reconciliation | Clinical narratives and marketing account administration. |
| Integration service account | One practice/connection, specified event/object/action scopes | Human login, arbitrary Contact search, agency-wide traversal, impersonated administrator. |

Agency grants need approving practice actor, purpose, capabilities, resource scope, expiry, revocation and audit. Portfolio access reevaluates each practice grant; caches and queued reports are invalidated on revocation. No agency role bypasses forced RLS. Separate metadata registry access from protected practice queries; workers operate one practice at a time.

## Tenant enforcement and credential lifecycle

Use dedicated high-entropy, revocable service credentials with identifier/hash for inbound bearer credentials. HMAC verification secrets must instead be retrievable through encrypted secret storage (a one-way hash cannot validate a vendor HMAC); public-key signature verification stores the approved public key. Outbound OAuth refresh/API secrets are encrypted using a managed secret/key facility, with only secret references in connection records. Never put credentials in browser code, URLs, logs or exported configuration. Exact secret manager choice is an infrastructure decision, not a new dependency mandated here.

Scopes bound connection, event types, object operations and optional validated locations. Validate vendor signature over correct raw request representation, timestamp/replay window and account binding. For providers without strong webhook signatures, use an approved authenticated gateway or webhook-as-hint followed by authenticated readback; do not treat an unsigned callback as a trusted fact. Rate/size limits and schema allowlists apply even after authentication. Generic org keys and PATs do not inherit these powers.

Revocation default: reject all subsequent deliveries; quarantine unprocessed accepted events for the connection with reason=revoked; retain immutable accepted evidence with acceptance-time credential metadata. Workers recheck revocation immediately before atomic effects. In-flight transaction/revocation ordering must serialize on connection authorization generation: either commit before revocation or stop without effect after it. Routine key rotation may allow a bounded overlap without revoking the connection; compromise revokes the connection and quarantines queued evidence for review. Reactivation never automatically processes quarantined records; authorized review/replay is required. Previously applied facts are not erased; assess compromise and append corrections where needed.

Forced RLS is defense in depth, not the entire authorization layer. Apply it to all new tables with WITH CHECK and same-practice FK/trigger guards, non-owner runtime roles, request/worker transaction context and finally cleanup. Test list/detail/create/update/delete/filter/search/export, generic CRM relationships, audit bodies and background jobs. Existence errors must not disclose foreign record details.

## Sensitive data flows

Classify credentials as secret; identified clinical/appointment/payment data and identity mappings as restricted; linkable acquisition/session/click evidence as sensitive; source-level aggregates as controlled, not automatically public. Raw browser URLs can contain patient information: use allowlisted path IDs/campaign tags, strip queries/fragments and avoid names/conditions in ad-facing events. Do not ingest clinical narratives, recordings, transcripts, card data or diagnoses for attribution by default.

Protected practice facts flow into internal reconciliation/reporting only. Google Analytics documentation says it must not receive PHI and does not offer a HIPAA BAA for Analytics. Keep clinical outcomes, patient identifiers and linkable patient financial data out of GA4. [Google Analytics healthcare guidance](https://support.google.com/analytics/answer/13297105?hl=en).

HHS guidance addresses tracking disclosures involving PHI and notes a court order vacating part of its treatment of IP addresses plus visits to unauthenticated health-related pages. Do not assume every public page view is PHI, or that every public tracking flow is exempt. Counsel must evaluate actual data, purpose, entities and contracts, including applicable non-HIPAA privacy requirements. [HHS tracking guidance](https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/hipaa-online-tracking/index.html).

Consent management is purpose-specific and versioned. Cookie consent is not automatically a HIPAA authorization or permission to upload clinical conversions. Hashing identifiers does not make disclosure permissible. Future advertising offline-conversion uploads require a separate approved design covering vendor policy, data fields, legal basis, consent, contracts, revocation and testing; default is disabled. GTM consent mode is a technical control, not a legal determination. [Google consent controls](https://developers.google.com/tag-platform/security/guides/consent).

## Aggregate disclosure protection

Agency marketing receives preapproved dimensions and bounded date granularity, no patient search/export/drilldown. Proposed starting threshold: suppress cells containing fewer than five distinct patients, with complementary suppression and restriction of overlapping queries that permit subtraction/differencing. Five is a planning default, not proof of de-identification. Clinical services may require higher thresholds or less detail. A suppressed metric returns a reason, not zero; associated revenue/denominator and drilldowns are suppressed too. Do not expose row IDs, exact event times, raw evidence, query-level search terms linked to patients or signed export links. Rate/query auditing and expert privacy review must address repeated-query inference. Existing aggregate Growth access should not be described as already implementing all these proposed controls.

## Audit, retention, recovery

Audit principal/type, approving grant, practice, action, resource, reason, decision/version, time and safe request correlation ID. Record identity links/unlinks, role changes, credential lifecycle, exports, review/replay, financial/attendance corrections, report publication and denial patterns. Protect audit integrity/access; do not dump raw request bodies or secrets into Celery/error telemetry. Restrict support tooling and redact exception context. Outbound fetches/imports need SSRF protections, controlled destinations, malware/size checks and spreadsheet formula-safe exports.

Proposed planning retention: minimized anonymous session evidence up to 30 days pending policy approval; routine safe delivery metadata 90 days; raw sensitive payloads not retained by default, exceptional encrypted quarantine up to 7 days with restricted review. Clinical/financial identity/audit retention must follow practice contracts, applicable laws and legal holds; do not impose these short operational defaults on statutory records. Consent withdrawal stops future optional tracking; deletion workflows distinguish legal retention from optional evidence and invalidate unsupported derived links. Keep deletion/tombstone audit without preserving unnecessary PHI indefinitely.

Production requires verified encrypted backups, restoration into isolated environment, key recovery/rotation, least-privilege operator access, monitoring/alert routing, incident response, vendor outage procedures, tested revocation, deletion/retention jobs and a documented recovery target approved by the owner. Proposed pilot planning targets RPO 24h/RTO 8h require a measured drill and business approval, not a service promise. Public repository contains no credentials, real patient fixtures, database exports or internal decks. Fictional fixtures only.


## G1 — Action capabilities and compatibility

Proposed future capability families are distinct: `patient.read`, `outcome.write`, `finance.read`, `finance.write`, `finance.reconcile`, `patient.export`, `identity.review`, `integration.admin`, `integration.receive`, `integration.review`, `integration.replay`, and `aggregate.read`. Names are proposed, not existing token scopes. Each action also checks practice/resource/contact visibility and the current grant; integration administration does not confer patient reading or arbitrary replay/financial authority. Until a reviewed future capability migration explicitly changes it, **existing cash writes, corrections, reconciliation and internal statement exports remain administrator-only**. Finance readers do not acquire those actions merely from a job title in the role table.

Website/form service authority is restricted to acquisition observations and confirmed server submission. Even a correctly signed website request for payment.settled, appointment.attended or a verified decision is rejected. Provider-specific field authority is configured by approved practice policy, not sent in the payload. Shared vendor accounts spanning practices require explicit immutable routing to single-practice connection bindings; ambiguous multi-practice events quarantine, never split by untrusted tenant hints.

All identifiable pre-patient inquiries and their review queues require protected access even before a Contact exists. Do not let “not yet Patient-linked” expose sensitive submissions through general CRM Lead, form, attachment, search or developer debugging routes. For this new module, classify and gate them at ingestion; existing unrelated legacy free text remains a documented baseline limitation, not automatically remediated by this design.

Read/export audit includes protected evidence retrieval and report-detail access. Queue messages, retry exceptions, metrics labels, tracing spans and alert texts contain opaque IDs/reason codes only; encrypted payload retrieval happens under authorized tenant context. Reject unbounded error-body logging. Audit logs need their own access/retention controls. Website signing secrets and clinical provider credentials have independent scopes and rotation; a compromised website cannot assert clinical authority.

For initial agency reporting, use fixed approved cohorts/dimensions and fail-closed suppression; do not claim arbitrary query differencing is solved by a threshold or rate limit. Until a privacy reviewer approves a tested release mechanism, flexible cross-filter drilldown/identified exports remain disabled. Legal deletion, credential revocation and report-cache invalidation include derived materializations and stored export links; already downloaded data cannot be recalled.
