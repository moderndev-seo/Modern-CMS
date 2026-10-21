# F — Revenue and measurement specification

> **Execution status:** [PROJECT_STATE](../PROJECT_STATE.md) is authoritative for the current milestone, validation and authorization. Phase 2B is merged in PR #4; Phase 2C is next and unstarted at the October 20, 2026 checkpoint. Architecture 0.2.0 and A01–A10 remain unchanged; Group B/C remain pending. Dated adoption, validation and publication statements below are historical specification records, not current implementation status or new authorization.


> **Historical adoption record 1 — superseded by approval record 2:** The owner accepted design **0.2.0 as the technical baseline**, subject to unresolved policy approvals in J. This supersedes the earlier “final validation draft / technical approval pending” status only. Proposed policy defaults remain pending. Phase 2A planning is authorized; implementation and GitHub publication actions are not. See [adoption and Phase 2A handoff](I-roadmap.md#adoption-and-phase-2a-handoff) and [owner approval register](J-product-decisions.md#group-a-owner-approval-register).


Design 0.2.0 · Technical baseline and narrow A01–A10 approved; Group B/C pending.
**Proposed reporting contract. Existing Growth stays labeled as recorded, USD, UTC activity-period reporting.** New verified reports must not imply that existing manual records have acquired provider verification.

## Common measurement contract

Every result includes metric definition/version, currency, timezone, interval, as_of, evidence tier, attribution model/version/lookback, identity decision version, filters, coverage bounds, unresolved count/amount, last successful reconciliation and availability reason. Distinguish `complete`, `partial`, `unavailable`, `not_applicable` and `suppressed`; a numeric zero is valid only when the relevant population was observed and actually empty.

Activity window W is local start-of-day on selected first date through exclusive local start-of-day after selected last date, converted to UTC instants using the report's IANA zone. DST days can be 23 or 25 hours. Offer UTC explicitly; do not reinterpret source dates using server timezone. Preserve source zone/precision, effective_at and received_at. A date-only financial source can support daily reports under its declared zone, but not false sub-day ordering. Missing timezone creates a review/coverage issue.

Verified-new attendance cohort C consists of practice-verified new patients whose qualifying first attendance falls in W (default); separately, inquiry cohort Q contains episodes whose first inquiry is in W. These are different populations and must have different report keys. Cohort value sums eligible cash linked to those subjects through a declared horizon/as_of, even if received after W. Period cash sums eligible transaction effects effective in W regardless of acquisition date. Never place period cash over a cohort denominator without labeling that different analysis.

Dimensions: practice; acquisition source/platform/campaign/site/page/service interest/location; inquiry channel; booked location/service; attendance/treatment location/service/provider; new/existing/indeterminate patient status; payer class; financial status; evidence quality; cohort/time. Display distinct dimension names; use Unknown/Unallocated buckets. Small-cell controls may suppress otherwise valid results.

## Exact KPI definitions

All counts exclude fictional/test data in real reports through explicit dataset scope, not name substring heuristics. Tests deliberately select TEST datasets. “Distinct” means canonical key after approved dedup decisions, not distinct email/phone.

| KPI | Numerator / population / date | Denominator or qualification |
|---|---|---|
| Website inquiries | Distinct accepted, persisted form submission IDs with inquiry.created time in W | Exclude rejected/spam/test and transport duplicates; browser button events are not submissions. No person uniqueness claim. |
| Calls | Distinct inbound call IDs initiated in W | Show answered/missed separately from provider dispositions; repeated genuine calls count; transfers/legs consolidated only by documented call key. |
| Unique acquisition episodes | Distinct episode IDs with first inquiry in W | Multiple inquiries linked by evidence count once; unresolved episodes remain distinct and labeled, not guessed to be unique people. |
| Qualified leads | Distinct episodes first reaching approved qualified state in W | Latest approved qualification must remain valid as of report; show reversals/restatements. Not equivalent to new patients. |
| Booked appointments | Distinct appointment IDs first confirmed in W | Reschedules not new bookings. Later cancellations remain in gross booking count with cancellation breakdown; active booked is a separate snapshot measure. |
| Attended appointments | Distinct canonical appointments with at least one qualifying linked encounter in W; separately report qualifying encounters without a booking | Authority-qualified attendance only; duplicate systems for same encounter require crosswalk. Manual attended count is a separate tier. |
| Verified new patients | Distinct practice persons whose first qualifying attendance is in W and current verified-new decision holds | E's identity/history gates. Unknown history excluded from verified numerator and shown as indeterminate. |
| Existing-patient reactivations | Distinct existing persons whose qualifying reactivation attendance is in W | Approved inactivity interval and complete history; one first qualifying reactivation per inactivity episode, not each visit. |
| Completed treatments | Distinct canonical treatment/outcome IDs completed in W after approved cross-provider dedup | Requires approved completion status. “Treated patients” is separately distinct persons with ≥1 such outcome; never conflate counts. |
| Net collected revenue | Sum economic cash effects eligible for the selected single evidence view, less eligible settled returns/posted losses plus recoveries in W | Separate evidence-tier totals and currency. Manual recorded net is a different labeled measure. Corrections affect the defined effective period. |
| Campaign spend | Sum nonoverlapping approved spend facts for campaign/account and source spend days in W | Complete coverage needed; manual and API values cannot both count for same covered account/day. Fees/tax policy declared. |
| Cost per inquiry | Complete spend for selected channel/cohort window ÷ eligible inquiries in that same acquisition window | Denominator zero → unavailable, not infinity; incomplete spend → null with reason; no default estimate. |
| Cost per booked appointment | Complete matching spend for inquiry cohort Q ÷ distinct appointments confirmed for Q through horizon (one explicit acquisition-episode association per appointment) | Label cohort/horizon. An alternative spend/period-bookings ratio must be labeled period efficiency, not acquisition CPA. |
| Cost per verified new patient | Complete spend for inquiry cohort ÷ verified new persons attributed to that cohort through horizon | Require identity/newness coverage; incomplete outcomes or no verified patients → unavailable/incomplete. Each person credited once under selected model. |
| Attributed ROAS | Eligible net cash attributed to inquiry cohort Q through horizon ÷ complete matching source/campaign spend for Q’s inquiry window | Show period attributed revenue / period spend only as a separately labeled cash-period ratio. Spend missing or zero → null with reason; negative revenue can produce negative ROAS. |
| Patient acquisition cohort value | Eligible net cash for verified new-patient cohort through stated horizon | Total and mean = total / verified cohort size; incomplete histories labeled observed value, never predictive LTV. |
| Lifetime revenue | Eligible net cash per person through as_of from earliest covered financial history | Label observed-to-date if not lifetime-complete; do not extrapolate or mix currencies. |
| Attribution coverage | Eligible linked outcomes with resolved supported non-Unknown source ÷ all eligible outcomes | Show separate conversion-count and cash coverage. Cash coverage uses absolute eligible economic-effect magnitude so refunds/negative totals cannot create nonsensical percentages. Unknown/unresolved remain denominator buckets. |
| Identity reconciliation coverage | Distinct person-requiring source objects with current verified/approved linkage ÷ all person-requiring accepted source objects | State object stream/grain; transport duplicates excluded. Report unlinked/disputed separately and age backlog. |
| Provider data freshness | as_of minus last successful coverage-through time per stream | Also report last successful poll and source-event lag; a quiet source is not necessarily stale. No average hides a failed financial stream. |
| Spend completeness | Covered required account-days ÷ expected active account-days in W | Require source/timezone/currency and documented account inventory; separately mark provisional/final, pagination gaps and estimated spend. A single spend row is not complete coverage. |

Present rates with both numerator and denominator and their coverage. Where acquisition spend cannot be mapped to the requested cohort, CPA/ROAS is unavailable. Campaign/site dimensions that cannot be supported stay Unknown; do not allocate source totals to campaigns proportionally without an explicitly approved model.

## Financial evidence and reconciliation

| State | Meaning | Revenue treatment |
|---|---|---|
| authorized | Funds authorized, not received | Exclude from collections. |
| captured | Processor accepted capture | Keep separate until approved settlement/collection policy is satisfied. |
| recorded | Staff or ledger recorded money | Included only in labeled recorded-cash view. |
| provider_verified | Authenticated source/readback supports the specific posting/status | Not a synonym for settled or reconciled. |
| settled | Configured source supports settled payment under documented semantics | Eligible for provider-settled view; unmatched ownership remains Unallocated. |
| reconciled | Approved reconciliation links collection evidence and accounting/source records; patient allocation is an independent axis | Eligible for reconciled practice collection KPI; unallocated remainder stays visible. Patient/source attribution requires separate valid allocation. |
| pending / disputed | Unresolved collection or dispute state | Do not silently call it final revenue. Show separate exposures; actual posted debits follow chargeback rules. |
| refunded / chargeback | Distinct settled return or posted loss linked to original transaction | Subtract once, on effective return/debit date in period view, from original cohort in cohort view. |
| corrected | New audited evidence changes prior amount/date/classification | Restate affected original periods with as-of version; separate operational notification date. |

One economic collection may appear as processor payment, PMS posting and bank payout allocation. Keep three observations; reconcile to **one** economic cash effect. Bank deposits may aggregate many payments and fees. Do not sum payout plus payments, or subtract fees twice. Recommended collection KPI is gross patient/insurance funds received less refunds/chargebacks, excluding processor fees; report fees and bank net separately. Insurance claim amount, ERA remittance and contract adjustment are not themselves cash. Reconcile insurer EFT/check receipt and remittance allocation before calling it reconciled insurance collection.

Transaction allocations must conserve amounts by currency, never exceed the eligible transaction, and preserve unallocated remainder. A guarantor's payment can cover multiple patients only with authoritative or authorized finance allocation; shared phone/email cannot allocate it. Unlinked money is not discarded: restricted finance sees source totals and unallocated balance; patient/source totals reconcile to the same grand total including Unknown/unallocated. Never create a fake Patient to hold unmatched cash.

Refund requires original transaction, same currency/practice and valid remaining refundable amount; missing parent blocks projection. Proposed chargeback/recovery accounting has distinct effect types and prevents refund plus chargeback from double-counting the same returned principal; fees and exceptional over-principal amounts are separate expense evidence requiring review. Existing Receipt supports payments/refunds, not this entire chargeback model: extend only after reviewed invariants and tests. Keep current correction, exclusion, allocation and matching protections intact.

Multiple currencies remain separate. No global total or ROAS across currencies unless an approved FX policy records rate provider, rate date, original amount, translated amount, rounding and reporting currency. Earliest pilot should remain USD, explicitly labeled, while canonical contracts preserve currency for later support. A non-USD observation is retained/quarantined from the USD ledger, not silently converted or rejected as if lost.

## Worked fictional reconciliation

TEST Harbor: October inquiry/attendance attributed to Google organic. October settled patient payment USD 100, November settled insurance payment USD 300, December settled refund USD 50 linked to the October payment. Period net: October 100, November 300, December −50. October acquisition cohort through December: USD 350. A PMS posting for the same USD 100 does not add another 100. With missing organic spend, ROAS is unavailable. With approved complete USD 200 cohort marketing cost and complete outcome coverage, attributed return on marketing spend is 1.75. Provider fees USD 3 do not change 350 collection revenue; bank net is reported separately.

## Reporting lineage and controls

Use derived PostgreSQL queries/materialized projections after measuring volume. Every authorized detail report traces measure → attribution/identity decision → economic effect/encounter → canonical observation → source reference and ingest/mapping version. Marketing aggregate responses expose only approved group-level lineage/coverage, never patient IDs or raw evidence URLs. Query authorization precedes aggregation and export. Store report definition/input watermarks/as-of versions so later corrected evidence yields visible restatements, not unexplained number changes. Exact historical reproduction is conditional on lawful evidence retention; expired/deleted evidence is explicitly marked unavailable/redacted under E1.

Provider platform conversions and GA4 revenue remain labeled platform-reported comparison series. They cannot override the CRM's clinical or collection evidence. Missing sources, stale streams, incomplete historical enrollment and manually asserted status must remain visible beside totals.


## F1 — Financial state axes and invariant totals

The financial table describes distinct facts, not a single status enum or a ladder. Store **posting status**, **processor collection status**, **bank reconciliation status**, **patient allocation status**, **dispute status** and **evidence provenance** independently. “Provider verified” qualifies what the provider actually asserts; a completed processor payment is not automatically bank-settled. Each report chooses one evidence predicate and counts each economic effect once, even when it meets several predicates. Never add recorded + settled + reconciled views together.

Recommended flagship view is **reconciled net collections**: approved collection evidence reconciled to accounting/source evidence under a declared policy. Display whether bank receipt was actually corroborated; reserve “bank reconciled” for that evidence. This recommendation awaits J07/J08. Lack of patient allocation does not erase a reconciled practice collection. In each currency: total economic net = allocated patient net + unallocated net. Within allocated net: resolved source net + Unknown net + unresolved-source net = allocated patient net. Negative and unallocated buckets are legitimate. A refund without known patient allocation follows its original collection's unallocated partition; it is not dropped.

Add KPI **financial reconciliation coverage**: sum absolute amounts of eligible observed economic cash effects meeting the selected reconciliation policy / sum absolute amounts of all eligible observed economic cash effects for the same period/currency/as_of. Include unallocated effects in both where applicable; do not treat zero observed effects as100% (null/not_applicable). Report source completeness separately:100% reconciliation of a partial history is not complete practice revenue. Expose unmatched amounts, stale streams and gaps alongside the ratio. Identity/source coverage never uses unseen records as a measurable denominator; label all such percentages “of observed eligible records.”

For posted chargebacks/refunds exceeding collected principal because the provider actually debited funds twice, preserve both bank movements and classify the excess as disputed loss/receivable/expense pending finance decision. Never suppress a real debit to satisfy a simplistic refund budget. Only the economic return-of-principal allocations are capped against the collection; excess cash movement lives outside patient revenue and remains visible in bank reconciliation. Chargeback reversal can restore only an evidenced previously posted loss; duplicate notification is not another recovery. No automatic projection of chargebacks into legacy Receipt until separately implemented and tested.

## F2 — Cohorts, dates and unavailable metrics

CPA and default attributed ROAS use **inquiry cohort Q** and the same explicitly covered acquisition window/source/campaign cost basis. They are not automatically calculable for a first-attendance cohort C. Cohort C supports patient value, but associated acquisition spend is unavailable unless a separate approved allocation method exists. An appointment, conversion or economic allocation has at most one effective acquisition-episode association under the first-touch model; ambiguous membership is unresolved and excluded from credited source totals, retained in coverage. Repeat-episode cash cannot also receive full new-acquisition credit in the same report. A separate patient-lifetime acquisition view may credit it, clearly labeled and never summed with episode reports.

Default CPA/ROAS values are null when required spend, identity, outcome or cash coverage is incomplete. Observed counts and amounts can remain visible with partial labels; they must not yield an apparently definitive ratio. Explicitly complete zero spend can yield zero CPA when denominator>0, but ROAS at zero spend remains unavailable. A zero denominator yields unavailable, not infinity. `spend_basis=advertising_only` may be labeled ROAS; all-in SEO/agency/marketing costs use “attributed return on marketing spend.” The fictional organic-cost examples use the latter label; the same arithmetic does not make SEO cost advertising spend.

Preserve vendor daily bucket timezone. A daily Ads/Search Console aggregate cannot be exactly repartitioned into practice-local days without finer-grained data. Present vendor-zone series separately or require aligned report boundaries; mark exact cross-zone spend/cost ratios unavailable when alignment is unsupported. Do not prorate daily spend by hours as if observed. UTC-offset timestamps must agree with declared IANA zone; ambiguous local wall times without offset/fold are quarantined for time clarification. Store reporting timezone and tzdb/version policy in report metadata. Org timezone changes affect future defaults, never silently reinterpret saved snapshots.
