# I — Prioritized implementation roadmap

> **Current publication status — October 16, 2026:** Design 0.2.0 and bounded A01–A10 are approved for fictional, isolated Phase 2A; Group B/C remain pending. The owner confirmed independent human review without outstanding blockers and authorized security PR #1 to merge; GitHub records merge `1e00ae5d175e0ace627b2dc5fc68e25a73cb41dd`. All seven checks passed on reviewed head `81ecc87672e35a00d45a9c40b2f83d578a364f2a`. This separate documentation PR is authorized for publication after checks. Phase 2A remains unimplemented and gated on documentation review, separate owner merge approval and actual merge. No live connections, deployment or Phase 2B–E implementation. Earlier gate/status snapshots below are historical, not current instructions.


> **Historical adoption record 1 — superseded by approval record 2:** The owner accepted design **0.2.0 as the technical baseline**, subject to unresolved policy approvals in J. This supersedes the earlier “final validation draft / technical approval pending” status only. Proposed policy defaults remain pending. Phase 2A planning is authorized; implementation and GitHub publication actions are not. See [adoption and Phase 2A handoff](I-roadmap.md#adoption-and-phase-2a-handoff) and [owner approval register](J-product-decisions.md#group-a-owner-approval-register).


Design 0.2.0 · Technical baseline and narrow A01–A10 approved; Group B/C pending.
**Planning only. PR #1 must receive independent review and merge approval before new application infrastructure is implemented. Separate owner authorization is still required after architecture approval.** Relative complexity covers engineering uncertainty, not calendar commitments. Vendor contracts can dominate elapsed time.

## Phase 0 — Secure foundation (M)

- **Objective/dependencies:** Review the published remediation at its exact current head; resolve findings and obtain authorized merge decision. Architecture review can proceed in parallel, as this task does.
- **Reuse/new:** Reuse existing capability/RLS/credential restrictions and CI partitions; no new journey infrastructure. New work only if review identifies necessary remediation.
- **Security/acceptance:** Independent reviewer with authorization/RLS/migration expertise; latest-head required CI and CodeQL green; no security test skipped; review migration safety and data-preservation evidence.
- **Risk:** Clean local tests do not substitute for independent review or production acceptance; original demo is not the remediated checkout.
- **Done:** Approved PR merge recorded with commit and test evidence. No implied deployment or permission to connect vendors.

## Phase 1 — Approve universal architecture (M)

- **Objective/dependencies:** Resolve framework-blocking decisions in J, approve D/E/F/G contract boundaries and explicitly defer later policy/vendor choices; depends on owner/product/technical/privacy review, not yet on a live account.
- **Reuse/new:** Extend post-audit-architecture and existing permissions/attribution docs. Adopt a single reviewed specification set and decision log; no application migrations in this phase.
- **Security/acceptance:** Review all protected flows, agency grants, service actor boundary and scenario J/K/L. Every A–O scenario must map to the same canonical domain without vendor-specific core changes.
- **Risk:** Ambiguous newness/collection definitions would create misleading reports; unknown vendor capabilities need discovery gates rather than optimistic promises.
- **Done:** Approved policy/version matrix, source-of-truth document links, unresolved nonblocking items explicitly deferred, and next implementation scope authorized.

## Phase 2 — Reusable connections and durable ingestion (H)

- **Objective/dependencies:** Tenant-bound service identity, connection registry, inbox, validation, retries, replay, review and health. Requires phases 0/1 and separate implementation approval.
- **Reuse/new:** Existing Org/RLS/capabilities, sandbox normalizers/tests and outbound durable-work patterns; add live principal/grants, inbox/work rows, external refs, basic review/audit and connection sync state. Preserve TEST-only synchronous intake.
- **Security/acceptance:** Same-practice DB links; no human impersonation; scopes and revocation checked before effects. Durable commit before ack, crash-safe processing, business dedup, quarantine and context cleanup tested under restricted PostgreSQL.
- **Risk:** Service audit path conflicts with current human-admin triggers; connection lifecycle and unbounded backlog can undermine integrity. Address through additive reviewed design, bounded workers and monitoring.
- **Done:** Fictional adapters demonstrate the ingestion/denial/replay subsets of H/J/K/X and durable restart/crash recovery; they do not assert verified patient conversions or cash ledger projection, with no live connection and no duplicate effects; all relevant regression/security checks pass; migration rehearsal preserves existing data. UI shows accepted/blocked/applied truthfully.

## Phase 3 — First-party acquisition evidence (M–H)

- **Objective/dependencies:** Website/form submission to inquiry with preserved capture and consent. Phase 2; approved site/domain/form and privacy policy for any real pilot.
- **Reuse/new:** Existing local capture module, WebFormSubmission, Contact/Lead/task workflows. Add minimized session/touch/inquiry/episode records, protected server relay and source mapping; no full CMS rewrite.
- **Security/acceptance:** No browser secret/PHI analytics payload; signed continuity, anti-abuse, consent/withdrawal and retention. Test genuine submission vs click, retries, cross-origin limits and Unknown preservation.
- **Risk:** Third-party embedding loses continuity; do not compensate with fingerprinting or source guesses.
- **Done:** One fictional website/form path persists inquiry and evidence, including offline/manual fallback; A/D/N acquisition portions and two practice isolation pass. A real approved website is a separate pilot gate, with documented consent and server-side delivery verification.

## Phase 4 — Appointments and calls (H)

- **Objective/dependencies:** One booking/PMS source and optionally one call source; demonstrate continuity through attendance. Phase 3 plus actual vendor capability/access discovery.
- **Reuse/new:** Appointment/AppointmentChange/JourneyEvent and patient views; add normalized external appointment/encounter refs, authority mapping, identity-review decisions and call inquiry adapter.
- **Security/acceptance:** Weak identifiers never auto-merge; provider/location bindings enforced; no recordings by default. Request vs confirmation and check-in vs attendance distinctions pass A/B/C/E/F/G/H/O.
- **Risk:** Middleware IDs or API success may not prove EHR insertion/attendance. Require authoritative readback/coverage or mark pending.
- **Done:** Fixture pipeline tracks confirmed booking and authority-qualified attendance; duplicate/reschedule/cancel/out-of-order handling verified. Chosen vendor sandbox/approved test practice confirms mapping separately before live enablement. No broad scheduling feature expansion required.

## Phase 5 — Verified patients and collections (VH)

- **Objective/dependencies:** Evidence-backed newness and money, including delayed insurance/refund and cross-feed dedup. Phase 4, approved history definition, source authority and financial policy.
- **Reuse/new:** Patient/Receipt and all refund/matching/allocation/correction protections. Add verified-conversion decisions, financial source evidence, conserved reconciliation allocations and reviewed service projection path. Keep legacy USD ledger initially.
- **Security/acceptance:** Finance capability, same-practice identity/currency/refund constraints, immutable audit and required history. A/B/C/F/H/I/M/O and direct database/concurrency cases pass. Source totals reconcile to patient totals plus unallocated.
- **Risk:** Posted ledger versus collected money, incomplete lifetime history, processor/PMS duplicates, payer allocations and mixed currencies. Keep unsupported status unresolved rather than bypass safeguards.
- **Done:** One fictional first acquisition→verified new attendance→treatment→reconciled collection→refund journey is complete with reproducible lineage; an existing patient and incomplete-history counterexample remain correctly classified. Real clinical/financial evidence semantics approved before pilot metrics are promoted.

## Phase 6 — Attribution and reporting (H)

- **Objective/dependencies:** F's versioned KPIs, cohorts, source/campaign/location/service, spend and coverage. Depends on phase 5 evidence; earlier scaffolding can exist but must remain labeled incomplete.
- **Reuse/new:** Growth and manual MarketingSpend; add explicit spend coverage, versioned attribution decisions, report metadata/as-of projections and controlled aggregate access. Keep old Growth semantics labeled.
- **Security/acceptance:** Agency grants, suppression/complementary controls, no identified drilldown, export revocation. Test exact formulas, missing/zero spend, negative revenue, DST, currencies, restatements and coverage across A–O.
- **Risk:** Precise-looking ratios hide missing source streams; source grouping can double-count outcomes or reveal identities.
- **Done:** All F metrics have fixtures, stable definitions and lineage; cash/cohort/source totals conserve values; L privacy tests and human financial review pass. Dashboard labels explicitly separate verified, recorded, Unknown and incomplete results.

## Phase 7 — Broader ecosystem and agency operations (H per adapter; scope-driven)

- **Objective/dependencies:** Add demanded vendors using the same contracts, then expand website/content/SEO/GBP operations and retention workflows. Requires established pipeline and selected-account access/contract approval.
- **Reuse/new:** Registry, inbox, identity/finance/report contracts and conformance tests; new adapters and capability manifests, not vendor-specific patient models. Later CMS modules add draft/review/publish/rollback and deployment audit separately.
- **Security/acceptance:** Each adapter passes manifest conformance, scoped auth, history/pagination/revocation/reconciliation and relevant A–O tests. New communication/publishing/upload actions need explicit product/privacy authorization.
- **Risk:** API deprecations, commercial restrictions and connector maintenance exceed initial implementation effort. Support tiers must identify field-level guarantees and owner.
- **Done per connector:** Documented/tested capabilities and limitations, approved access, monitored sync and reconciliation, operational runbook, version/deprecation plan and practice acceptance. Universal compatibility is never a completion claim.

## Smallest end-to-end implementation slice

Within approved phases 2–6, prioritize one fictional website submission, one booking/clinical crosswalk and one collection source: touch → inquiry → confirmed appointment → authoritative attendance → newness decision → completed treatment → USD 200 settlement/reconciliation → USD 50 refund → net150 attributed or Unknown. Use TEST Cedar as denied tenant and an existing/shared-contact patient as counterexamples. A second booking adapter fixture must map to the same records without new domain fields. Use manual complete spend100 to produce cohort ROAS1.50, and missing spend to produce null.

This vertical proof should precede broad vendor coverage, ad-account automation, full CMS publishing or sophisticated multi-touch modeling. It does not skip secure infrastructure or financial invariants. After proof, one separately approved practice pilot validates actual vendor semantics. No automatic outreach, live payments or advertising upload is required.

## Production acceptance remains a separate gate

Require independent security/privacy review, real vendor permissions/contracts and applicable BAAs, approved patient/agency grants, human workflow/financial acceptance, successful backup/restore and key-recovery drills, monitored queues/freshness/reconciliation, incident support ownership, capacity/load testing, migration rehearsal, rollback/forward recovery procedures and documented limitations. Verify no real data leaks into public Git or fixtures. Evaluate accessibility and supported browser workflows. Record exact evidence and accountable sign-off; passing architecture fixtures or merging PR #1 does not itself authorize production.

## Handoff per completed increment

Update PROJECT_STATE with approved scope, exact commit/branch/runtime, schema changes, checks actually run, failures/skips, remaining risks and next step. Link specification versions and decision records; do not recopy definitions. Follow current publication authorization rather than older automatic-push instructions. This task prepares handoff updates in a separate documentation overlay only; it makes no edits to the security checkout and performs no publication.


## I1 — Smallest safe first implementation milestone

**Universal Integration Foundation, fictional shadow mode only.** Requires merged/independently approved PR #1, approval of J's framework-blocking choices and separate implementation authorization. Includes connection registry, restricted/revocable service identity, versioned ingress contract, durable inbox, idempotent normalization, tenant-safe processing, bounded retries/replay, unresolved review, audit and per-stream health/coverage. It does not need a real vendor, verified-new policy, ad account, CMS publishing, live website or Receipt-writing bridge.

Use two TEST practices and two differently shaped fictional adapters producing the same canonical observations. An end-to-end **foundation** test runs receive→durable receipt→worker→accepted/unresolved observation→authorized review→idempotent replay. A fixture can contain a future patient journey, but no later-domain verified metric or cash write is claimed. The **full patient-to-revenue** end-to-end proof remains the bounded phases3–6 slice. This distinction avoids making phase 2 acceptance depend on unbuilt phase 5 capabilities.

| Increment | Scope and dependencies | Planned migrations / compatibility | Required tests and exact completion |
|---|---|---|---|
|2A — Registry/principal|After phases0/1; practice/account namespace, service scopes, credential lifecycle, audit|Add service/connection/grant tables with RLS; no legacy PAT/org-key behavior or patient rows changed|Wrong tenant/scope/admin minting denied; credential rotation preserves namespace; no human impersonation; reviewed migration leaves legacy snapshots equal|
|2B — Durable acceptance|After2A; versioned safe ingress subset, inbox and delivery receipt|Add inbox/observation/attempt records with unique delivery keys, bounded payloads, same-org links|Ack only after commit; duplicate samehash same receipt; changedhash409; malformed/oversize rejected; browser clinical facts403; DB outage no success|
|2C — Worker/recovery|After2B; lease/backoff/sweeper, normalization, revocation generation, stream cursors|Add durable scheduling/coverage fields or companion work table; no extra broker/database|Crash at each commit/enqueue boundary loses0 accepted events and duplicates0 effects; normal restart persists all; key revocation race deterministic; one tenant's backlog cannot starve the other|
|2D — Review/replay/health|After2C; unresolved dependencies/identity references, restricted review state, audit, health API/minimal UI|Typed source-reference incarnation and append-only review decisions; no Contact merge or money projection|Wrong-role review/export denied; expired evidence replay unavailable; blocked rows visible to authorized reviewer; ingestion cursor can advance while applied completeness remains partial|
|2E — Foundation conformance|After2A–D; two fictional adapters, coherent source→inbox→review replay demonstration|No extra domain schema; only defects discovered in prior increments|H/J/K/X foundation subset under migrated restricted PostgreSQL; all existing regression partitions relevant to changed auth/services pass; docs/migration drift/frontend checks as applicable; no vendor call or outbound side effect|
|3A /3B — Acquisition domain then adapter|After2E; first add protected inquiry/session/touch/episode and ContactMethod, then one approved form relay|P3 additive tables and narrowly reviewed intake/UI extension; preserve primary email uniqueness and original Patient fields|S/F household tests, no legacy Lead email-merge/notification reuse; fictional acquisition passes before approved live site gate|
|4A /4B — Identity/clinical then calls|After3A; first typed mappings/authority/encounters, then booking adapter and optional call adapter|P4 optional refs and decision tables; no unsupported Appointment.status or conflict-check bypass|A/C/E/F/G/O/T/P domain fixtures; mapping disagreements unresolved; source outcomes validated separately|
|5A /5B /5C — Shadow money, allocation, bridge|After4A and finance policy; source/economic evidence first, then reconciliation/allocations, then separately approved legacy ledger service path|P5 additive evidence first; bridge migration review only after invariants pass|I/Q multi-component and chargeback totals, R immutable receipt identity, service-actor denial, concurrency budgets; no automatic ledger bridge in5A|
|6A /6B — Definitions then release|After5A–B evidence; versioned calculations/spend coverage, then controlled report/API/UI and agency grants|P6 additive facts/projections; legacy Growth unchanged|U/V/W exact ratios/timezones/currencies, N Unknown, L disclosure/revocation; privacy/finance acceptance before agency release|
|7 per adapter|After applicable domain phases; one capability manifest and adapter at a time|Normally no core schema change; new semantic requirement needs reviewed contract version/ADR|Same conformance suite, bounded history reconciliation and vendor sandbox evidence; documented access gaps do not become support claims|

A milestone closes only when its migrations (if any), tests, review findings, limitations and handoff are recorded. No calendar estimates are asserted. Product/privacy/vendor choices can block the corresponding later increment without blocking fictional-only foundation work, once foundational policy is approved. No production rollout belongs implicitly to any increment.

## Adoption and Phase 2A handoff

Adoption record 1 — October 14, 2026. Design version remains **0.2.0**. The owner accepted the technical baseline subject to J's unresolved policies. This section is the consolidated A–G handoff and bounded implementation plan; it does not reopen the architecture audit. Proposed field/API names below are implementation choices for owner review, not existing application features.

### A. Architecture adoption status

The validated A–J, index and validation report are preserved. A new 15-file repository-layout overlay carries this adoption record and the required continuity updates. The original validation report remains the historical review record; its pre-adoption verdict is superseded only by the explicit technical acceptance recorded at the top of each document. D/E/F/G remain authoritative for domain, identity, money and security. This I section is authoritative only for Phase 2A execution details; J's adoption register governs pending choices.

The implementation baseline remains the public security branch at `3858f46f9e80960f1f4d5f0627459d863e5a65e9`. A read-only GitHub check on October 14 found PR #1 **open and unmerged**, base main `11e6d59a0ef79e6cefe6d5fe1a71859099557961`, 57 changed files. These are observations, not independent security approval. The original local checkout and reviewed public clone remain untouched. The running demo has not adopted security remediation or this architecture as new functionality.

Technical adoption is complete as a recorded owner decision. Permanent GitHub adoption and both required merges are outstanding. A01–A10 and conditional 2A implementation/publication are approved; later policies remain pending. This overlay is not an application checkout and cannot be run as one.

### B. GitHub publication plan

Exact Markdown allowlist (15 files; no new sixteenth public document):

1. `AGENTS.md`
2. `docs/modern-practice/PROJECT_STATE.md`
3. `docs/modern-practice/post-audit-architecture.md`
4. `docs/modern-practice/universal-journey/README.md`
5. `docs/modern-practice/universal-journey/A-executive-assessment.md`
6. `docs/modern-practice/universal-journey/B-journey-architecture.md`
7. `docs/modern-practice/universal-journey/C-vendor-capabilities.md`
8. `docs/modern-practice/universal-journey/D-data-and-events.md`
9. `docs/modern-practice/universal-journey/E-identity-and-attribution.md`
10. `docs/modern-practice/universal-journey/F-revenue-and-reporting.md`
11. `docs/modern-practice/universal-journey/G-security-and-privacy.md`
12. `docs/modern-practice/universal-journey/H-acceptance-scenarios.md`
13. `docs/modern-practice/universal-journey/I-roadmap.md`
14. `docs/modern-practice/universal-journey/J-product-decisions.md`
15. `docs/modern-practice/universal-journey/VALIDATION_REPORT.md`

After independent authorized PR #1 merge, use a fresh public-repository clone, inspect origin/current main/clean state and confirm landed remediation semantics. A squash merge can change SHA; compare code and migrations, not ancestry alone. Reconcile changed handoff files rather than overwriting newer work. Create an unused `codex/universal-journey-docs` branch from landed main only when publication work is authorized. Never force-push or use the original private development history. Review the allowlisted patch against that main; a patch check against today's feature head alone does not establish future merge compatibility.

Before explicit commit/push/new-PR authorization: verify file list, whitespace, internal links/anchors, no private materials or identifiers, strict MkDocs and the two existing publication guards without skips; record exact baseline and dependency environment. From the disposable validation checkout, follow [team setup](../team-setup.md): `uv sync --frozen --group docs` in backend, then `uv run mkdocs build --strict -f ../mkdocs.yml -d /absolute/temporary/site`, then `uv run pytest common/tests/test_docs_build_excludes_internal.py --no-cov -v` with repository SQLite test settings and a local test-only secret. Do not run a full migration/test environment against the user's saved database for documentation checks. Review built-site contents as well as source: non-nav docs are copied by MkDocs. No workflow/config changes are part of this overlay.

Suggested separate PR title: **Adopt universal patient journey design 0.2.0 and specify Phase 2A gates**. Description must state technical baseline accepted, policies pending, no code/migrations and actual docs validation results. Do not label the architecture implemented or production-ready. Documentation commit/push/PR creation is conditionally authorized after the security merge and successful checks; no merge is authorized. PR #1 receives no edits, comments, merge or settings changes from this work.

### C. Decision approval register

[Group A in J](J-product-decisions.md#group-a-owner-approval-register) is the single consolidated owner-selection register. A01–A10 cover practice ownership, source authority, credential issuance/lifetime, stable namespace/identity separation, shadow-only effects, fictional retention, revocation, audit minimization, bounded sequencing and release gates. Each gives J references, default, alternatives, consequences, dependency and exact approval required. All ten are **approved** as recorded below. Group B/C account for remaining slices of all 25 original decisions; no selection is inferred from technical acceptance.

The owner has explicitly approved A01–A10 and granted conditional publication/implementation authority. The next actions are the independent review and separate merge gates; do not ask for these same foundation choices again. Security/privacy/finance/vendor evidence required for later phases cannot be supplied merely by an owner checkbox.

### D. Phase 2A implementation specification

#### Scope and non-goals

Deliver a practice-bound connection registry, restricted non-human identity, credential issue/rotation/revocation, metadata-only authentication probe, and immutable lifecycle audit in the existing Django application. API-first; no new frontend screens required. Local frontend 5181/backend 8000 remain unchanged. No event inbox, event acceptance, worker, payload normalization, object mapping, patient creation/linking, financial observation storage, clinical write, agency grants, dashboard, vendor HTTP client or live registration. Return no “accepted” event response in 2A because durable acceptance belongs to 2B.

Enable new endpoints only under an explicit fictional-foundation setting defaulting off and a configured allowlist of disposable TEST Org UUIDs. Names alone are not a security boundary. A valid admin or service credential for another Org is denied. Tests create their own clearly labeled TEST fixtures; no implicit seed/startup changes to saved organizations. Both immutable connection `mode=fictional` and deployment allowlist are checked at every new endpoint. Real-mode registration is unavailable until separately approved.

#### Existing code reuse and proposed modules

| Existing implementation | Reuse | Boundary / necessary addition |
|---|---|---|
| `common.models.Org`, `Profile`, JWT handling and `common.permissions.is_org_admin` | Existing practice tenant and active human admin authorization | No new practice or human identity model; new services never borrow a Profile. Human admin JWT must be explicitly verified, not inferred from profile role after PAT/API-key resolution. |
| `common.base.BaseOrgModel`, `common.rls`, `common.middleware.rls_context` and pool tests | UUID/org/index conventions, forced-RLS SQL and tenant cleanup patterns | Explicit registration/migration for every new table. A service request must fail closed on tenant-context setup/reset errors; do not inherit a log-and-continue failure behavior. |
| `common.models.PersonalAccessToken` | High-entropy/one-time presentation/hash/expiry concepts | Do not reuse PAT rows: PATs represent humans and legacy empty scopes are unrestricted. Service scopes empty means deny. |
| `common.middleware.get_company`, `common.scopes`, `common.external_auth` | Credential dispatch/route restriction patterns | Add narrow dedicated service-token dispatch before JWT fallback; deny service credentials on all legacy and administration routes. Never invoke org-key admin selection. |
| `patients.AttributionConnection/Identity/Event`, `patients.intake`, migration 0016 | Existing fictional synchronous sandbox remains intact; use its test patterns | These immutable TEST rows require human-admin actor and patient targets. They cannot safely become the restricted registry or durable inbox. No backfill or promotion. |
| `patients.access`, Contact visibility, financial services/migrations | Existing patient/outcome/finance rules are unchanged | Integration administration grants no patient or finance capability. No modifications to receipt triggers or immutable attribution. |
| Existing immutable appointment/finance histories, outbound webhook delivery patterns | Audit discipline now, durable-work design later | Generic Activity is not the authorization ledger; no outbound webhook reuse as inbound delivery or notification side effect. |

Proposed module layout: `backend/integrations/{models,manifests,services,authentication,permissions,serializers,views,urls}.py`, `migrations/0001_initial.py`, `tests/`. Register app/URLs and extend the narrow credential dispatcher and tenant table registry only when implementation is authorized. Recheck actual middleware ordering at coding time. No change to default authentication on unrelated routes and no broad authentication-exempt path prefix. New admin endpoints use JWT-only permissions; new service endpoint is separate and explicit. Extend central scope-denial rules so PAT/org keys cannot reach these new management endpoints even if a future view forgets a permission check.

#### Exact proposed schema additions

Four new tables, no existing table data mutation. All inherit UUID/org/creation conventions; references use PROTECT, never cascade-delete credential or audit history. BaseOrgModel's inherited Org deletion behavior needs an explicit PROTECT override for these records. Human creator references remain human provenance, not the service's identity. Use timezone-aware UTC timestamps and org/created_at indexes. No arbitrary provider configuration JSON or URL fields. Label is immutable in 2A and max 100 characters, restricted to safe operator text with a warning not to enter patient data; audit captures changed field name, not label content.

| Model / table | Fields in addition to base UUID/org timestamps | Constraints and purpose |
|---|---|---|
| `ProviderNamespace` / `mp_integration_namespace` | `provider_key` max64, `account_key` max128 opaque synthetic ID, `environment` fixed `fictional`, `created_by_profile` required | Unique `(org, provider_key, account_key, environment)`; org/provider/account/environment immutable; same-org active admin creator on insert. Stable across reconnect/key rotation; new account means new namespace. Provider key from code allowlist, not caller-defined plugin. No patient external IDs here. |
| `IntegrationConnection` / `mp_integration_connection` | protected `namespace` FK; `label`; `adapter_key` max64 and `manifest_version` max32; `manifest_digest` 64 hex; `capabilities` immutable bounded validated snapshot; `mode=fictional`; `status` active/paused/revoked; `authorization_generation` positive bigint default1; `created_by_profile`; `revoked_at` nullable; `revision` positive bigint default1 | DB same-org namespace/creator; manifest/key/version/digest/capabilities and namespace immutable. Only one non-revoked connection per namespace for 2A (partial unique constraint). Generation monotonically increases for pause/resume/revoke and credential revocation/rotation changes; revision supports stale command detection. Terminal revoked cannot reactivate. `revoked_at` iff revoked. |
| `IntegrationCredential` / `mp_integration_credential` | protected `connection` FK; `token_digest` 64 hex; `digest_version=sha256-v1`; `locator_key_version` max32; `scopes` bounded explicit array; `issued_by_profile`; `issued_at`; required `expires_at`; `revoked_at`, `revoked_by_profile`, `revocation_reason_code` nullable; optional protected `replaces_credential` FK | Unique digest; same-org connection/issuer/revoker/replacement; replacement must have same connection. Empty scopes never authorize; subset of connection manifest. Issued data/digest/scopes/expiry immutable; only null→revoked metadata once. Expiry > issue and ≤30 days; optional overlap cutoff handled by shortening old key validity via a dedicated `retire_at` timestamp which can only move earlier, never extend. At most two non-revoked keys per connection; issue/rotation serialized; expired unrevoked keys still occupy slots until explicitly revoked. No plaintext or last-used write on every request. |
| `IntegrationAuditEvent` / `mp_integration_audit` | protected connection FK nullable for namespace creation; namespace FK required; credential FK nullable; actor kind human/service; exactly one of `actor_profile` FK or `actor_credential` FK (separate from the subject credential FK); action/reason allowlist; `request_id` UUID; `request_fingerprint` SHA256 of canonical nonsecret command; previous/new generation nullable; occurred_at server-stamped; bounded details with only lifecycle enum, scopes, expiry, replaced credential ID | Append-only and same-org all links; action/actor compatibility; unique `(org, request_id)` for mutating commands, replay compares nonsecret fingerprint. No tokens/digests/raw bodies, arbitrary free text or patient links. Service has no lifecycle-write authority; initial audit mutations human only. Future service audit actions need explicit schema/permission extension. |

Implement PostgreSQL CHECK/unique constraints and triggers for same-org references, immutable fields, audit immutability and legal lifecycle transitions; service layer also validates for clear errors. Database checks must reject forged foreign IDs and updates even through direct SQL under the restricted role. Scope/manifest snapshot validation needs a versioned fixed validation function or equivalent SQL constraints generated from the same checked-in manifest definition; do not leave JSON authority fields as unchecked escape hatches. Keep manifests immutable and migrations self-contained (do not import mutable runtime manifests from historical migrations). Database protections do not replace human JWT authorization; an app DB role is not an end-user permission system.

Use fixed actions `namespace.created`, `connection.created`, `connection.paused`, `connection.resumed`, `connection.revoked`, `credential.issued`, `credential.rotated`, `credential.revoked`; fixed reasons `fixture_setup`, `maintenance`, `resume`, `compromise`, `retired`, `rotation`, `operator_revoke`. Validate action/reason combinations (compromise only revokes; maintenance pauses; resume resumes; rotation issues/retires keys). Server selects action, client selects only an allowed reason for that command. Do not persist failed authentication tokens or caller-supplied request IDs as trusted audit facts. Invalid-auth monitoring uses server-generated opaque correlation IDs and bounded reason counters, without tenant existence disclosure or request headers.

No separate ServicePrincipal table is necessary in 2A: `principal_id` is the connection UUID, scoped to one Org, with multiple credential versions. Never use credential ID as durable source namespace. No separate capability catalog table: checked-in versioned manifests are authoritative; immutable snapshot/digest allows later review. No new location/site directory, patient crosswalk, economic ledger or global registry lookup. Those dependencies are deferred deliberately.

Manifest edits or authority changes require a new pinned version and replacement connection, not silent edits to an old authority snapshot. Same-account replacement shares namespace after old connection is revoked. Identity incarnation is a later typed source-object reference, not a new namespace each time a provider recycles an ID. Legacy financial dedup key remains independent of connection, credential, delivery and projector versions as specified in D; 2A creates no effect-key table.

#### Provider capabilities and source authority

Create two interchangeable fictional adapter encodings, `fixture_a` and `fixture_b`, supporting the same canonical contract `1.0` from D. A manifest declares schema versions, supported observation types, object kinds, source class (acquisition/booking/clinical/financial), transport shape, history/coverage limitations and `fictional=true`; no URLs or live account claims. Each adapter has separate source-class variants so a form credential never inherits clinical/financial authority simply because its adapter supports those capabilities elsewhere. Caller selects a permitted immutable manifest ID; cannot submit arbitrary authority booleans.

Acquisition manifest permits D's acquisition observations only. Booking manifest permits booking observations but cannot assert attendance. Clinical manifest may eventually submit attendance/treatment **observations**; financial manifest may submit collection/refund **observations**, never assert bank reconciliation. Internal identity-link, new-status, payment-reconciled and correction/revocation decision events are denied for every external manifest. Read exact canonical event names from D, not a new parallel taxonomy. 2A stores declarations and tests the authorization function; none are accepted over HTTP yet. Namespaces bound to a fictional account can use the needed source class but changing class means a reviewed replacement, not scope widening through credential issuance.

2A credentials carry `integration.probe` only. Manifest declares possible future observation authority; that declaration alone grants no current receiver scope. `integration.receive` is introduced only with 2B endpoint and tests. No wildcard, human/resource scope, `patient.read`, `finance.write`, `integration.admin` or empty-as-unrestricted semantics. Grant intersection is active practice + allowed fictional environment + active connection + active unexpired credential + credential action scope + pinned manifest authority + route capability. Future event authority additionally checks canonical type/account/object scope; no verification tier from payload.

#### Service authentication and tenant bootstrap

Proposed bearer format: a distinct `mpis1.` prefix followed by a versioned Django-signed locator (Org UUID, connection UUID, credential UUID, signing-key version, issued/expiry times) and a separately generated cryptographically random 32-byte secret. Use a dedicated signing salt/domain, SHA-256 digest of the complete canonical token, constant-time digest comparison and strict length/format bounds (maximum 2048 bytes). Persist only digest and nonsecret IDs/times; no recoverable bearer secret. Use the deployment's existing signing facility with explicit key version/verification fallback policy, not a new secret service. Token signature is not sufficient: the stored digest/expiry/revocation/current connection must also pass. Never log either locator or secret.

Middleware flow: reject mixed Authorization/Token credentials; identify `mpis1` before normal JWT dispatch; deny any route except explicitly registered service paths. Verify signature and signed expiry **before** choosing any tenant context. Invalid signature/format returns generic 401 with no DB tenant lookup. In a bounded transaction, set LOCAL `app.current_org` from the verified locator; select credential/connection/namespace under forced RLS with matching signed IDs, active Org and allowed TEST UUID; compare digest and expiry/revocation/state/scopes. Do not scan tenant credential tables globally, disable RLS or set context from an unsigned header/path/body. No match is generic 401, not a tenant-existence oracle. Fail DB/context setup closed as 503, never fall back to JWT/org-key authentication.

After successful verification attach a distinct `request.integration_principal` and verified `request.org`; `request.profile` stays None. Use a minimal service principal object for DRF's authenticated identity, not a User/Profile row. Every new service view checks this principal; every legacy route denies service tokens at the dispatcher. Continue with the existing tenant middleware only after authenticated context is established; its integration path must surface context setup failures and reset failures rather than continue. Clear/restore context in finally on all paths; close/discard a DB connection if reset cannot be confirmed, including pooled reuse tests. DRF standalone/RequestFactory paths invoke the same resolver or deny missing verified principal; they cannot bypass middleware restrictions.

Changing any unsigned tenant input must not change the authenticated Org. A supplied conflicting organization header/body is rejected (403); management API ignores no extra tenant selectors silently. Signing-key loss/rotation requires reissuance; bounded fallback keys may verify still-valid locators but never bypass credential revocation. Cross-environment token reuse denied by signing domain/deployment audience embedded in the locator. A domain identifier is nonsecret configuration, not caller input. Define/validate its exact value in tests; live audience/configuration is deferred.

Probe and lifecycle mutations serialize on the connection row. Probe rechecks authorization after acquiring lock and before producing the bounded response. If revocation wins first, probe fails; if probe wins first, it returns only nonprotected connection metadata and revocation commits afterward. In 2C workers must use the same generation/lock protocol immediately before atomic effects. No claim that 2A already protects a nonexistent worker.

#### Proposed API boundary and exact outcomes

All endpoints under `/api/integrations/v1/`; fictional feature flag and Org allowlist required. JSON only, no uploads, request body cap 16 KiB for admin commands. Reject unknown fields; UUID/path objects resolve within request Org, foreign/not-found object returns 404. Existing wrong-role access returns 403; unauthenticated/invalid service token 401; stale revision or conflicting request ID 409; schema errors 400; disabled feature 404; database unavailable 503 with no internals. All responses private/no-store. Paginate metadata lists (default 50, maximum 100); no token/digest or provider account key in general list responses. Account key can be returned only in an explicit admin namespace detail response; still no secrets/PHI.

| Endpoint | Principal / request | Result |
|---|---|---|
| `POST namespaces/` | Active practice admin JWT; request_id, provider_key, synthetic account_key | 201 new or 200 identical retry; immutable namespace. Existing unique account with new request ID returns existing ID without duplicate creation; audit the command. |
| `GET namespaces/` and `GET namespaces/{id}/` | Same admin JWT | Practice-only safe metadata; detail allows account binding inspection. |
| `POST connections/` | Admin JWT; request_id, namespace_id, label, pinned manifest_id | 201 active fictional connection or 200 same retry; reject second non-revoked connection 409. No automatic credential issuance. |
| `GET connections/` and `GET connections/{id}/` | Admin JWT | Metadata/state/revision/generation/manifest, no event payload, patient or secret. |
| `POST connections/{id}/state/` | Admin JWT; request_id, expected_revision, target paused/active/revoked, fixed reason_code | 200 atomic state change + audit. Only paused→active, active→paused, active/paused→revoked; terminal revoke idempotent; revoke marks all keys revoked atomically. Never DELETE. |
| `POST connections/{id}/credentials/` | Admin JWT; request_id, expected_revision, expiry, scopes=`[integration.probe]`, optional replaces_id/overlap_seconds ≤86400 | 201 metadata + raw credential once; requires active connection. Serializes issue/rotation; replacement same connection; old key revoked immediately if overlap0 or retire_at capped. Subsequent identical request returns 200 metadata and `secret_available=false`, never regenerate/reveal. Lost response: explicitly revoke orphan and issue new request. Conflicting fingerprint 409. |
| `GET connections/{id}/credentials/` | Admin JWT | Issuer, ID, scopes, issue/expiry/retire/revoke state only; no hash or raw prefix. |
| `POST connections/{id}/credentials/{key}/revoke/` | Admin JWT; request_id, expected_revision, reason_code | 200 monotonic revocation plus generation/revision increment and audit; repeated same request returns recorded result. |
| `GET connections/{id}/audit/` | Admin JWT | Paginated lifecycle facts; no arbitrary payload, no export endpoint. |
| `GET service/probe/` | Valid service credential with integration.probe | 200 connection UUID, mode=fictional, manifest ID/version and permitted action; no organization name/account key or patient info. Human JWT, PAT, org key and portal credentials denied here. |

No generic PATCH, DELETE, bulk export, event POST or self-service credential management. Label edits can wait; avoid introducing mutable commands unnecessary to 2A. Request-id retries first revalidate current authorization, then compare the stored request fingerprint before checking expected_revision; identical retries return the original nonsecret result even if the command advanced revision. New commands still require the current expected_revision. Retries preserve the original result; an expired human session cannot replay a credential issue response. Connection revision changes for every registry/key mutation; a key rotation never changes provider namespace. Audit and row mutations commit together or neither commits. Response loss never creates duplicate credentials. Concurrency beyond two active credentials is rejected, not silently evicted. If actor becomes inactive during mutation, recheck under appropriate row lock before committing.

#### Migration, compatibility and rollback

One additive `integrations.0001` (or reviewed split for SQL constraints) depends on landed common capability migration and relevant Org/Profile state. Verify actual dependency names after PR #1 merge; current common head includes 0044 and patients head 0017. No dependency on future patient models. Register all four tables with enabled **forced** RLS and both standard policies, same-org triggers and audit guards. Test migration under repository-supported migration-owner setup, then run all security assertions as NOSUPERUSER/NOBYPASSRLS. No production/saved demo migration is authorized by this plan.

No backfill, new global credentials or changes to original attribution/Contact identities/Receipt totals. Existing admin TEST intake remains separate, with unchanged namespace and endpoint authorization. Original manual and sandbox records remain byte-for-byte equivalent on key field fingerprints in a disposable upgrade rehearsal. New feature disabled means old workflows unchanged. No modifications to legacy financial trigger actor rules.

Rollback first disables new routes and revokes service credentials; existing application may run with unused new tables. Do not unapply/drop audit-bearing tables as an operational rollback. Make destructive reverse migration explicitly unavailable or require a separately approved empty-table-only development reversal; preferred specification is irreversible audit-preserving migration plus forward fix. Rehearse clean install, upgrade from exact landed baseline, restart and additive rollback-by-feature-disable. Measure locks/index creation in a disposable database; four empty new tables avoid large existing-table rewrites but do not eliminate migration review.

#### Tests and measurable acceptance criteria

The following are planned tests, **not executed implementation evidence**. Mark new integration database/auth tests for migrated restricted PostgreSQL and update routing checks in the future implementation so they cannot silently land only in SQLite. Preserve existing dedicated security CI; do not broaden this documentation task into workflow edits.

| ID | Test / failure | Required result |
|---|---|---|
| 2A-01 | Feature off; allowlist missing; ordinary/non-TEST Org | New APIs unavailable/denied; 0 registry writes, unchanged old endpoints. |
| 2A-02 | Two TEST practices; foreign namespace/connection/credential/creator/replacement IDs over API and direct SQL | Reads absent/404, writes rejected; no cross-practice link, 0 data leakage under forced RLS; empty/missing context cannot see tenant rows. |
| 2A-03 | Human admin, regular staff, marketing/finance readers, PAT (including broad legacy scopes), org key, portal key, service key across every route | Only active human admin JWT manages registry; only service token probes; service receives 0 patient/contact/finance records from all legacy paths. |
| 2A-04 | Malformed/oversized/forged signed locator; altered Org/connection/credential/expiry/audience; bad secret; mixed headers | Generic denial, no unverified tenant selection; no fallthrough or signing/token data in response/logs. |
| 2A-05 | Expired, retired, revoked key; paused/revoked connection; disabled Org/flag/allowlist | Denied on the next request; no positive authorization cache bypass. Exact expiry boundary uses UTC. |
| 2A-06 | Empty/wildcard/unknown/escalated scopes and forged manifest/capabilities | Rejected in API and protected DB columns; no clinical authority from website source; all internal decision events denied by authority evaluator for all external variants. |
| 2A-07 | Rotation retry, response loss, simultaneous issuance, replacement to wrong connection | At most 2 non-revoked slots; one audit/effect per request ID, same retry never shows secret; expiry/retire window ≤approved limits; no changed namespace. |
| 2A-08 | Pause/resume/revoke race with probe, credential issue and duplicate commands | Deterministic serialized outcome; no issue after winning revoke; terminal state cannot reactivate; audit/generation exactly matches committed command. |
| 2A-09 | Direct SQL update/delete audit or immutable namespace/authority/digest/scope fields; foreign actor; invalid state transitions | DB rejects each; no cascade erasure; app role has neither superuser nor BYPASSRLS. |
| 2A-10 | Exceptions during tenant setup/view/reset, connection pool reused for other practice, DRF direct invocation | Fail closed; no stale context or inherited principal; poisoned connection discarded; subsequent tenant sees only its rows. |
| 2A-11 | Logs, serializer/OpenAPI examples, exception telemetry and one-time response caching | No secret, hash, Authorization header, raw body or patient details; no-store; test-generated token scan returns 0 leaks outside intentional one-time response. Use test-only logs. |
| 2A-12 | Identical commands and conflicting payload with same request ID; transaction failure before audit | One committed mutation/audit; conflicts409; injected failure rolls back both. Secret lost after response failure is not reissued under same ID. |
| 2A-13 | Connection replacement with same namespace vs different account; two fictional adapter variants | Namespace stable on permitted replacement; different account distinct; account relabel rejected; adapter-specific encoding does not change canonical capability meaning. No object identity/linking inferred. |
| 2A-14 | Migration clean/upgrade, normal isolated database restart, feature-disable rollback | Existing patient/cash/source fingerprints unchanged; four tables/constraints/RLS present; credentials/state/audit persist; disabled feature blocks service auth, old app paths work. No volume deletion. |
| 2A-15 | Patient/cash creation counters during all tests; nonexistent event receiver | 0 new Patient/Contact/Receipt/JourneyEvent/Appointment rows from integration service; event POST404/405, no misleading202 acceptance. Existing authorized sandbox test remains unchanged. |

Unit coverage: manifest schema, token codec/digest/lifetime, scope intersection, safe reason codes, request fingerprint excluding secrets, legal state transitions. Integration coverage: full middleware and DRF path, lifecycle transactions, concurrency with separate DB connections, logging and upgrade. Regression checks: repository restricted PostgreSQL security suite (no skips), targeted auth/PAT/portal/patient permissions, routing accounting, Ruff/format, Django check, migration drift, strict docs/publication guards. Broader compatibility suites are required if shared middleware changes affect them; record exact selected checks and limitations. No frontend check/browser walkthrough is required for an API-only milestone unless UI/shared frontend files change. Never present SQLite tests as RLS evidence.

Definition of completion: A decisions recorded and 2A explicitly authorized; independent security PR merged; reviewed code/schema/APIs match this scope; all 2A-01–15 and relevant regressions pass with exact counts and no security skips; clean/upgrade/restart rehearsal preserved records; no live network/clinical/cash effects; limitations and next2B proposal recorded in PROJECT_STATE. Owner review of results is separate from test success. A merge/push/deployment still needs applicable explicit authorization. No foundation-wide completion claim after 2A.

### E. Phase 2 roadmap and dependency boundaries

| Phase | Starts after | Delivers / completion boundary | Explicitly deferred |
|---|---|---|---|
| 2A | Group A, security merge, scoped implementation authorization | Registry, restricted service authentication, issuance/revocation, metadata audit; 2A-01–15 | No accepted events, payloads, workers or domain writes. |
| 2B | Verified 2A and explicit next scope; synthetic payload/retention details approved | Durable inbox, versioned envelope, server-stamped tenant/source, authority checks, durable commit before ack, conflicting retry detection | No asynchronous projection or live vendor accounts. Transport identity is not economic-effect identity. |
| 2C | Verified 2B | Celery/Redis using PostgreSQL durable work/leases/sweeper; bounded retries, dependencies, crash recovery, generation checks, atomic shadow effects; no loss after ack | No Receipt bridge, verified-new claims or spontaneous contact matching. Replay/version changes cannot duplicate business effects. |
| 2D | Verified 2C | Protected unmatched review, typed external reference incarnations, explicit replay, stream coverage/freshness, ingestion vs applied watermark | No unsupported identity guesses, arbitrary agency access, automatic replay after compromise or live SLA promise. |
| 2E | Verified 2A–D | Two interchangeable fictional adapters, duplicate/out-of-order/ambiguity/revocation/failure/restart conformance under restricted PostgreSQL | Does not prove vendor access, patient verification, real collections or production readiness. |

Only prepare the 2A specification now. Do not create later phase tables, migrations, jobs or workers early “for completeness.” H's full patient/finance journeys span phases 3–6; foundation tests cover their transport/authority/recovery invariants only.

### F. Development handoff

A future agent with the published repository should follow this exact order:

1. Read AGENTS then PROJECT_STATE; verify current remote/branch/head/clean state and actual owner authorization. Preserve uncommitted work and distinguish local demo from remediated checkout.
2. Read this adoption handoff, J Group A recorded decisions and D/E/F/G authoritative definitions, then existing patient-permissions and release-readiness. Technical version0.2.0 is accepted; unselected policy defaults are not.
3. Confirm independent PR #1 approval/merge and landed code. If still open, continue only authorized planning; never approve one's own security work as independent review.
4. Confirm both security and documentation PRs are independently reviewed/approved and actually merged. Conditional implementation authorization for **2A only** is already recorded; do not start code before both merges.
5. On authorized work, use current public main and a fresh `codex/integration-foundation-2a` branch (choose another unused codex name if occupied). Reconcile mappings against current code and justify any material deviation with a dated decision before expanding scope.
6. Implement the four additive tables, narrow services/auth/APIs and tests in reviewable increments. Use only isolated fictional databases. Preserve ports, human auth, tenant RLS, existing data and finance invariants. Do not reclassify current PAT/org keys as service identities.
7. Run the 2A test matrix and required repository checks, record exact results/failures and retained limitations. Update PROJECT_STATE and this roadmap status without overwriting historical evidence. Do not claim 2B–E done.
8. Stop at the applicable publication/review gate; no push/PR/merge/deploy unless explicitly authorized. Propose 2B scope only after 2A verification and handoff.

Future architectural decision records can be appended to J with ID/date/status/owner/rationale/alternatives/affected versions and superseded decision. Implementation details may evolve only within approved semantics; changed tenant/authority/effect/money/privacy rules require explicit design review and version decision. Avoid a second competing specification file.

### G. Remaining blockers and next actions

| Next action | Genuine blocker | Resolution |
|---|---|---|
| Finish local planning/adoption package | None once the documentation checks below are recorded honestly | Deliver this handoff and register; no need for vendor selection or another general audit. |
| Publish docs against main | PR #1 independent approval and authorized merge; reconcile landed main; final docs checks; explicit commit/push/PR authorization | Owner assigns reviewer; authorized merger handles PR independently; rerun patch/content/docs checks after merge, then request bounded publication approval. |
| Begin 2A code | Security and architecture documentation review/approved merges | A01–A10 and conditional implementation authority are already granted. Prove both merges before coding; no live policy/vendor decision needed. |
| Begin real integrations later | Group B approvals and actual access/privacy/operational evidence | Resolve with practice/vendor/clinical/finance/privacy owners during dependent phases. Not a current fictional planning blocker. |

Current preparation check results are appended below after execution. Historical validation results are not new test evidence. No code, migration, runtime infrastructure, vendor connection, database data, Git commit/push/PR or repository setting is changed by this adoption task.

#### Adoption preparation verification — October 14, 2026

Completed documentation-only checks: exact 15-file allowlist; 77 local Markdown links/anchors; JSON contract example parses; balanced code fences; all 25 J references classified and ten Group A approval entries present; no local personal paths, private-key markers or credential patterns in prepared files; patch dry-run including whitespace validation against reviewed head; isolated patch application with all 15 file contents matching the overlay; original Git head/status/tracked-diff fingerprints and both earlier architecture-package hashes unchanged. Content review found only design/code references and fictional examples, no real patient records or private reference material.

Strict MkDocs build passed, exit 0, zero warnings. The two unchanged repository publication guard tests passed, zero skips, in a temporary minimal Django-settings harness pointed at an archived public checkout with the overlay. This intentionally bypasses the application pytest fixtures/database startup; it executes the exact guard module, not the full backend/CI test environment. Temporary tool versions: Python 3.11.1, MkDocs 1.6.1, Material 9.7.7, Django 5.2.18, pytest 9.1.1. Dependencies were downloaded into a disposable documentation-tool environment; no runtime infrastructure or repository dependency file was changed. This is not a frozen-lock CI reproduction; run the repository's normal frozen docs job after reconciling landed main.

Generated HTML contains the handoff and specification; excluded `design/` and `superpowers/` directories are absent. This is a generated-output inspection, not a browser/visual-accessibility audit. No app tests, migrations, database/container restart, live vendor calls, hosted CI rerun or production acceptance occurred in this documentation task. Existing security/app test counts remain historical. Planned 2A tests above have not been implemented or executed.

Recorded tooling limitations: first dependency download failed due sandbox DNS; the approved temporary-environment retry succeeded. Exploratory reads initially used nonexistent flat middleware/RLS paths; corrected to the actual package paths. Process inspection was sandbox-denied and unused; the temporary environment has no pip module, so dependency installation used uv. Neither issue affected the completed guards/build. PR #1 is unchanged and unmerged as last observed. Nothing has been committed, pushed, merged, opened as a PR or deployed.

## Controlled implementation gate status

**Historical October 14 snapshot:** the security findings below were subsequently corrected and merged. The October 16 publication status above is authoritative. See [the final remediation report](../pr1-review-remediation.md) and [current project handoff](../PROJECT_STATE.md) for the landed baseline. This snapshot is retained for provenance, not as a pending security gate.

### A. Decision record

A01–A10 recommended bounded defaults are approved by direct owner instruction, with selected choice, date, source and affected specification/dependency in J's recorded approval table. Group B/C remain unapproved. Design 0.2.0 remains unchanged; no new architecture assessment or application design was introduced.

### B. Security PR status

[PR #1](https://github.com/moderndev-seo/Modern-CMS/pull/1) is open/unmerged at `3858f46f9e80960f1f4d5f0627459d863e5a65e9`; base main is `11e6d59a0ef79e6cefe6d5fe1a71859099557961`. GitHub reports mergeable, which does not mean security-approved. No requested reviewers and no APPROVED human review were returned. The sole submitted review is automated Codex COMMENTED on earlier commit `a84a50e4da`; that is not independent human approval.

All seven project-required checks for the current head are successful: backend-tests, backend-tests-postgres, patient-security-postgres, frontend-checks, package-build, docs-build and CodeQL Analyze (python). Evidence: [CI run 38525944019](https://github.com/moderndev-seo/Modern-CMS/actions/runs/38525944019) and [CodeQL run 38525943885](https://github.com/moderndev-seo/Modern-CMS/actions/runs/38525943885). Classic commit statuses returned an empty list; conclusions come from Actions runs/jobs, not that empty response. Repository branch-protection configuration was not changed or certified.

The hosted security job log confirms `--migrations -m postgres_only`, creation of the NOSUPERUSER/NOBYPASSRLS role, and **215 passed, 6294 deselected, 213 warnings in 123.34 seconds**, no skipped tests in the summary. The exact-head autouse fixture asserts PostgreSQL and role flags `(False, False)`; patient tests check forced-RLS catalog flags and cross-tenant access. This verifies the intended migrated restricted-role suite actually ran; it does not prove every endpoint is secure or close uncovered review findings. No CI rerun was triggered.

Four unresolved automated threads remain:

| Priority / GitHub thread | Finding | Current-head read-only spot check |
|---|---|---|
| P1 — [opportunity subresources](https://github.com/moderndev-seo/Modern-CMS/pull/1#discussion_r4267766657) | Patient/finance restrictions missing from Kanban and line-item routes | Kanban still queries Opportunity directly and applies creator/assignee checks; line items use the inline access check. Requires qualified review and targeted regression coverage, not automatic dismissal because CI is green. |
| P1 — [alternate case routes](https://github.com/moderndev-seo/Modern-CMS/pull/1#discussion_r4267766666) | Watching/analytics and merge/unmerge paths outside the patient guard | Watching and analytics still use direct Case queries; merge locks raw rows then uses creator/admin merge authorization. Thread remains actionable for independent review; no exploit/API write was attempted. |
| P2 — [member creation grants](https://github.com/moderndev-seo/Modern-CMS/pull/1#discussion_r4267766674) | Accepted capability grants not persisted at profile creation | Profile creation still copies role/address/org without the three capability fields. |
| P2 — [portal comment author context](https://github.com/moderndev-seo/Modern-CMS/pull/1#discussion_r4267766679) | Authorized readers receive restricted author without serializer context | Multiple detail comment serializers still omit request/profile context. |

These are narrow checks of existing review findings, not a new general audit and not executable reproductions. No thread was resolved, comment posted or PR modified. Required next step: qualified independent human evaluates these findings at the current head, requests/accepts fixes with regression tests as appropriate, and approves the resulting exact head. A changed head invalidates this CI snapshot until its checks succeed. The owner's instruction prohibits modifying PR #1 in this task; remediation changes need separately scoped authorization. No security merge approval has been supplied.

### C. Architecture publication

Prepared local overlay remains exactly the 15 approved Markdown paths. It now records approved A defaults and conditional authorization. Proposed branch `codex/universal-journey-docs`, proposed title “Adopt universal patient journey design 0.2.0 and specify Phase 2A gates.” No branch, commit or documentation PR has been created because the security merge prerequisite is unmet. After actual security merge, reconcile the overlay against landed main and rerun normal frozen docs/publication checks; conditional commit/push/PR authorization is already granted. Documentation merge still needs separate owner approval.

### D. Phase 2A implementation

**Not started, as required by the explicit gate.** No models, migrations, services, auth, endpoints or audit runtime were changed. I's four-model and metadata-probe specification is retained. Phase 2A code may begin only after both security and documentation PRs are approved and merged. Proposed implementation branch remains `codex/integration-foundation-2a`; there is no implementation commit or PR URL yet.

### E. Security verification

Acceptance groups 2A-01 through 2A-15 are **not implemented/not run**. No claim of new tenant-isolation, credential or revocation test results. Existing hosted security evidence is recorded in B and does not substitute for future 2A tests. No saved development/demo/production database was accessed or modified.

### F. Regression results

Existing current-head hosted backend compatibility, PostgreSQL security, frontend, package and docs checks plus CodeQL are successful as observed above. They are inspected hosted results, not new local executions in this task. Local work is documentation only: check the accompanying validation results for the updated overlay's exact link, allowlist, patch, MkDocs and publication-guard results. Full frozen CI, app regression, migration/restart and browser checks are not rerun at this blocked planning gate. Warnings in the existing security run remain documented, not suppressed.

### G. GitHub review status

Existing branch `codex/patient-authorization-ci`, SHA `3858f46f9e80960f1f4d5f0627459d863e5a65e9`, PR #1 open. No human approval; four unresolved review threads; no explicit security merge approval. No new GitHub writes, commits, pushes, review messages, settings changes or merges. Linking PR #1 to the local chat is UI bookkeeping only, not a GitHub change.

### H. Remaining work

1. Independent qualified human review and disposition of four open findings, with authorized targeted fixes/tests if needed. Green CI and Codex review cannot satisfy this gate.
2. Separate owner security merge approval and actual merge after review/checks.
3. Reconcile/publish the docs under already-granted conditional authority, then obtain its independent review/owner merge approval and actual merge.
4. Implement/test/submit 2A under the now-recorded conditional authority after both merges. Group B/C decisions and live vendor access do not block that fictional milestone.

No deployment or live account selection is needed to unblock the next documentation preparation step. Review is a genuine human gate; do not claim completion, implement around it, or request redundant architecture approval.

### I. Next milestone

Immediate next executable milestone remains 2A after the two merges. Proposed **2B**, not authorized here: durable event inbox, versioned canonical contract, server-stamped tenant/source identity, event-type authority validation, durable commit before acknowledgement, stable delivery idempotency/conflict rejection and minimized synthetic payload retention. Depends on verified 2A, explicit 2B authorization and retention details. Acceptance: authenticated permitted fictional delivery persists before acknowledgment; duplicate retries yield one inbox record; conflicting bodies are rejected; foreign tenant/forbidden event authority is denied; crash at receipt boundary loses no acknowledged event; no patient/cash projection. Workers/recovery remain 2C, unresolved review/health 2D, adapter conformance 2E. Do not implement any of these during the gate.


Current approval-overlay validation: 15 allowlisted Markdown files, 80 local links/anchors, JSON/fence checks, privacy/secret-pattern scan and content review, whitespace/patch dry run and actual application to an archived public snapshot passed. Strict MkDocs passed through both unchanged repository publication guards: 2 passed, zero skipped, in the isolated minimal-settings harness; no application/database fixtures ran. Normal frozen repository CI must run after reconciliation with merged main. Earlier package hashes are unchanged; security checkout remains clean. The original local handoff received only an additive continuity pointer, preserving all previous text. No application/regression/2A acceptance tests were executed.

Verification correction: a repeat patch rehearsal initially reused an already-patched temporary snapshot and failed because new files existed. The accompanying guard run was therefore not counted as final-overlay validation. Rehearsal and guards were repeated against a fresh public snapshot; use the final results. No source checkout was affected.
