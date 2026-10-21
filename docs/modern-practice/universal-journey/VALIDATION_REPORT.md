# Final architecture validation and handoff report

> **Execution status:** [PROJECT_STATE](../PROJECT_STATE.md) is authoritative for the current milestone, validation and authorization. Phase 2B is merged in PR #4; Phase 2C is next and unstarted at the October 20, 2026 checkpoint. Architecture 0.2.0 and A01–A10 remain unchanged; Group B/C remain pending. Dated adoption, validation and publication statements below are historical specification records, not current implementation status or new authorization.


> **Historical adoption record 1 — superseded by approval record 2:** The owner accepted design **0.2.0 as the technical baseline**, subject to unresolved policy approvals in J. This supersedes the earlier “final validation draft / technical approval pending” status only. Proposed policy defaults remain pending. Phase 2A planning is authorized; implementation and GitHub publication actions are not. See [adoption and Phase 2A handoff](I-roadmap.md#adoption-and-phase-2a-handoff) and [owner approval register](J-product-decisions.md#group-a-owner-approval-register).


**Design 0.2.0 • October 14, 2026 • Documentation only**

## A — Architecture verdict

**Ready with documented limitations for product-owner approval.** The corrected architecture fits the existing modular Django application and preserves its practice tenant, identities, original attribution and financial guards. Remaining gates are product policy choices, independent review/merge of PR #1, implementation authorization, vendor access/semantics validation and privacy/operational acceptance. This verdict does not approve those gates or certify integrations.

All A–J documents were read in full and evaluated together. The original package is preserved. The code baseline is `3858f46f9e80960f1f4d5f0627459d863e5a65e9`; the local feature checkout was clean and the read-only GitHub PR query confirmed that head, open/unmerged status and main base. No remote or PR mutation occurred.

## B — Substantive findings and corrections

| Finding | Resolution and exact specification location |
|---|---|
|Household scenario conflicted with unique Contact.email and duplicate-email serializer rejection|D3 adds protected ContactMethod relationships while preserving existing uniqueness/IDs; H:F/S asserts second blank primary email and separate patients; J25 requires approval before intake changes|
|Legacy webform reuse could merge households into one sales Lead and trigger email side effects|D3 limits reuse to submission evidence and prohibits legacy merge/notification path in new acquisition ingestion; H:S measures2 inquiries and0 notifications|
|Effect idempotency included projector_version, allowing repeat ledger effects after remapping|D “Relationships and invariants” and D4 separate stable write identity from disposable projection version; H:Q asserts0 additional ledger effects|
|External ID lifetime stability was assumed|D3/E1 introduce source incarnation/validity and immutable namespace; H:R handles reused IDs and conflicting demographics without reassignment|
|Reversing identity could imply rewriting immutable Receipt.patient|E1 explicitly withholds disputed verified attribution while preserving recorded cash identity and requiring separate finance remediation; H:R checks no second payment|
|Financial state table mixed provenance, settlement and allocation, making unallocated reconciled cash contradictory|F1 defines independent axes and total=allocated+unallocated conservation; verified/source credit requires appropriate separate evidence|
|Multi-component cash and real excess chargeback debit were underspecified|D4 uses provider subtransaction keys; F1 preserves excess real bank debits outside attributed principal rather than discarding them; H:Q tests split captures/refund/loss/recovery|
|Attendance cohort could use unmatched inquiry-period spend; incomplete spend allowed a loosely defined estimate|F2 makes inquiry cohort Q the default cost/ROAS denominator population, nulls incomplete ratios, separates C cohort value and marketing-cost return from advertising ROAS|
|Source daily buckets could be silently shifted into practice-local days|F2 preserves provider timezone and refuses unsupported exact redistribution; H:U tests DST23/25h and alignment-unavailable ratios|
|Appointment and encounter counts were conflated|F KPI table counts distinct canonical appointments and separately reports unbooked encounters; D/H:T retain tied/overlapping clinical evidence without false booking counts|
|No exact financial reconciliation quality metric or split between ingestion and applied completeness|F1 adds absolute-effect reconciliation coverage; D4 keeps separate ingestion/applied checkpoints and expected source inventory; H:V tests location gaps despite successful polling|
|Hash-only secret wording was incompatible with HMAC verification|G credential section distinguishes hashed bearer tokens, encrypted retrievable HMAC secrets and public verification keys; H:X tests mechanism and logging boundary|
|Website credentials could appear to supply canonical clinical/verified events|D4/G1 restrict source event authority and internal-only decisions; H:P/X assert403 and0 clinical/cash effects for signed website submissions|
|Pre-patient inquiries could fall outside current Patient-linked safeguards|G1 requires explicit protected classification at intake, including review/search/exports; H:X checks no generic CRM leakage|
|Financial trigger description overstated DB administrator checks; future finance role could be read as current permission|D legacy compatibility now names actual migration0016 admin check versus finance actor/integrity checks; G1 retains current application admin-only financial writes/reconciliation/export|
|NexHealth sign convention was incorrect|C payment row/C1 corrected to negative payment/positive refund in that vendor ledger; normalizer uses explicit kind/positive magnitude, never generic sign heuristic|
|Vendor documentation reachability was mistaken for consistently refreshed capability evidence|C1 marks Meta retrieval failure, unreadable athenahealth details, failed Zocdoc guide, partner/tier requirements and restricted historical Eaglesoft material; no live access claim|
|Lookback, retention and as-of reproducibility could conflict|E1 makes lookback a maximum, separates anonymous/linked retention and marks replay/report reproduction unavailable after lawful evidence deletion|
|Generic organic_search could be narrowed to Google without evidence; event/channel names differed between examples|E1 preserves generic platform Unknown; D/E/H standardize decision name patient.new_status_decided and channel enums; original fields unchanged|
|Phase 2 accepted outcomes belonging to phases4–6; phase 1 appeared to require every vendor/product decision|I1 splits foundation 2A–2E and shadow proof from full patient/revenue proof; J1 distinguishes first-milestone blockers from later decisions|
|Acceptance matrix lacked concrete medical-stack, replay-version, timezone, currency and completeness fixtures|H1 adds exact numeric oracles for A–O; H2 adds P–X measurable edge cases mapped to D/E/F/G|
|Competing future roadmaps and ephemeral-only handoff|Prepared README/AGENTS/PROJECT_STATE pointers and concise roadmap entrypoint designate one authority per topic; design version and ADR approval process are explicit|

## C — Canonical architecture confirmation

One practice-scoped canonical observation/decision domain supports website, form, call, CRM, scheduling, PMS/EHR and cash evidence. Each connector declares source authority, stable namespace/incarnation, versioned mapping, transport method and coverage. Vendor replacement preserves old observations and uses explicit crosswalks; changing a vendor or credential does not redefine a patient, appointment, collection or metric. Unsupported vendor facts remain unknown, unresolved or unavailable. New vendor semantics outside the contract require an intentional contract-version review, not arbitrary vendor columns in Patient.

D1 maps proposed services to current modules; D2 covers every core entity with migration/constraint/test profiles. The additive ContactMethod and economic-evidence extensions address real constraints, without a separate identity platform, microservices or a second ledger replacing existing Receipt history.

## D — Integration research verification

C contains provider-specific official links, narrow confirmed capabilities, remaining unknowns and access/privacy gates. This review reopened official source families across marketing, forms, calls, CRM, scheduling, medical/dental, payments and engagement. Confirmed examples include booking APIs, API authorization, form submission hooks, source identifiers and provider ledger semantics; none proves agency production entitlement. NexHealth payments, Square location coverage and Search Console daily buckets materially affected the design.

Meta details remain unverified; athenahealth returned an unreadable body; Zocdoc detailed-guide retrieval failed though the partner scheduling page was readable. Eaglesoft's historical material is not a current public implementation contract. Partner/license/tier restrictions and applicable contracts/BAAs remain live gates. Do not copy restricted vendor materials into Git. Select categories by stable identity continuity, authoritative outcomes, coverage, testability and actual client adoption; implement one chosen website/form, booking/clinical and financial evidence path, not every named vendor.

## E — Security and financial assessment

Highest-cost-to-reverse choices are tenant boundary, source namespace/incarnation, Contact identity preservation, irreversible write idempotency, event authority and cash semantics. These are specified before the foundation begins. Residual risks include incomplete source history, multi-party payer allocation, unknown contract permissions, preexisting sensitive free text in unrelated CRM, aggregate inference and retained/downloaded information. G enforces future protected intake, separate action grants, raw-data minimization, secret mechanisms and denied marketing disclosure. F exposes coverage and conserves cash across Unknown/unallocated/disputed states. Existing security behavior is preserved; proposed safeguards still need implementation and tests.

## F — Acceptance coverage

H retains all 15 requested A–O journeys with source systems/IDs, canonical normalization, identity, verification, attribution, money, access and recovery. H1 supplies count/amount/denial oracles. H2 adds 9 scenarios P–X for medical alternative stack, multi-leg cash/version replay, ID reuse/immutable cash identity, legacy form collisions, clinical authority, currency/DST, completeness/zero spend, retention/cohorts and credential/logging isolation. Test levels are stated; no scenario is reported as executed. Phase 2 runs only applicable foundation assertions; full A–X acceptance spans later increments.

## G — Final implementation sequence

After PR #1 independent review/approved merge and explicit authorization, implement I1's2A registry/service scopes,2B durable inbox,2C workers/recovery,2D review/replay/health and2E fictional conformance. Completion: accepted events survive DB/worker/container failure; retries and remapping add0 duplicate effects; forged tenant/scope/clinical authority fail; revocation gates final effects; unresolved events remain durable/reviewable; source completeness is honest; logs/queues expose no payloads; legacy tests/invariants and migrations pass. No Receipt bridge, live provider or new-patient claim belongs to this first milestone.

## H — Product approvals

J contains 25 pending decisions with defaults/alternatives and business consequences; J1 supplies explicit security/technical impacts, phase dependencies and first-milestone blockers. Approve foundational tenant/service/data boundaries and fictional shadow scope first. Newness, clinical/cash authority, lookback/cohorts, live retention/consent, reporting privacy and first vendor can be finalized before their dependent phases. No recommendation silently becomes approved by this report.

## I — Documentation handoff and versioning

Permanent location is `docs/modern-practice/universal-journey/`: README, A–J and this report. Three existing docs receive prepared updates: AGENTS, PROJECT_STATE and post-audit-architecture. Current patient-permissions/closed-loop-attribution/website-intake/release-readiness/team-setup remain cross-referenced baseline authorities. A new agent reads PROJECT_STATE, this index, J/I and applicable D/E/F/G/H sections, compares Git/runtime and authorization, and does not implement without separate approval. Future ADRs preserve approval status/version and migration/report impact.

## J — Publication readiness

Prepared as a documentation-only overlay/patch against the reviewed feature commit, separate from PR #1. After its approved merge, use a fresh public-repository checkout at current main, create a separately authorized `codex/universal-journey-docs` branch, reconcile any merge/squash changes to these three handoff files, apply/check only the 15 allowlisted Markdown paths, run documentation/publication checks and inspect the staged diff. Then commit/push/open a separate PR only when authorized. Never force-push, alter PR #1 or copy the original private repository history/output into Git. A patch check at the reference commit is not a promise it applies unchanged to future main.

## Validation scope and limitations

Document consistency, local links/anchors, JSON example parsing, preserved-input hashes, docs-only patch application and publication allowlist are checked locally; exact recorded results accompany the local handoff. Application, vendor sandbox, security regression, runtime browser, concurrency, restart and privacy acceptance tests were not run for this documentation assignment. Historical215-security-test and prior CI results remain historical; no fresh green CI claim is made. Independent technical/product/privacy/finance approval remains required. Vendor capability review cannot establish contracts or working interoperability.

### Recorded documentation checks

- 15 allowlisted Markdown files:12 architecture files plus3 prepared handoff updates; no application, migration, workflow or configuration changes.
- 46 local Markdown links/anchors checked; one JSON contract example parsed; all15 requested scenarios plus9 additional edge-case scenarios present.
- `git apply --check` passed against the exact reviewed baseline. Actual patch application in an isolated non-Git snapshot passed and all15 files matched the prepared overlay.
- Original package file hashes unchanged; both existing Git HEAD/branch/status/tracked-diff fingerprints unchanged. No commits, pushes, merges or remote mutations.
- Full MkDocs strict build and repository docs-publication tests **not run**: MkDocs/Material are not installed and were unavailable in the isolated offline tool cache. An initial tool lookup hit a default tool-directory permission limitation; retry with writable temporary directories confirmed dependency absence. No permission escalation or package download was performed.
- The initial snapshot script used a newer Python tar API unsupported by the local interpreter; it was corrected to validate archive member paths/types before extraction, then rerun successfully. No source checkout was modified by that failed check.
- Mermaid diagrams remain source; rendered visual QA was not performed. This is not a browser/runtime acceptance check. Application and vendor tests remain unexecuted for this documentation-only task.

Publication is therefore **prepared, not yet fully validated for merge**: rerun strict docs/build/publication guards against the post-PR#1 main plus this patch, reconcile any changed baseline, review privacy/publication content and obtain authorization before pushing the separate docs PR.
