# Website attribution capture — local adapter

## What is delivered

A dependency-free browser ES module in `frontend/static/modern-practice/website-attribution.mjs` prepares attribution observations for a website server. It can be hosted with a WordPress, Webflow or custom website that supports custom JavaScript; actual platform installations have not been performed. It makes no network calls, reads no form fields, installs no tags and contains no credentials. Existing CRM API authentication, permissions, RLS and data are unchanged.

The owner's explicit requirement is automated marketing-to-collected-revenue attribution across mixed website platforms. This adapter is one component, **not completed automated intake**. Exact page/parameter allowlists, explicit consent, optional session storage with a fixed 24-hour lifetime and a maximum of 20 subsequent observations are implementation choices. No schema additions are needed.

## Try the fictional demo

Open http://localhost:5181/modern-practice/website-demo.html with the existing frontend running.

1. Leave consent undecided and click Google Ads introduction: the handoff remains Unknown and nothing is captured.
2. Select Granted and click Google Ads introduction: approved first-touch fields appear.
3. Click Later email visit: first source remains Google Ads, with email in subsequent observations.
4. Select Denied / withdrawn: captured observations disappear.
5. Select Granted, click Visit without source, then Google Ads introduction: original stays Unknown.

The demo uses in-memory fictional URLs and does not inspect your current address or create patients. Reload clears it. No login is needed because it contains no practice data or CRM access. The CSP disallows outgoing connections and form submissions. This page is a developer exercise, not a consent notice for patients.

Run focused checks from the repository root with Node 20 or later:

```sh
node --test scripts/test_website_attribution.mjs
```

## Site integration shape (not activated)

```js
import { createWebsiteAttribution, leadAttribution } from '/assets/website-attribution.mjs';

// Reviewed constants for ONE site. Never build these from visitor input.
const capture = createWebsiteAttribution({
  siteId: 'fictional-practice',
  pages: ['https://example.com/'],
  sourceRules: [
    { source: 'google', medium: 'cpc', value: 'google_ads' },
    { source: 'newsletter', medium: 'email', value: 'email' }
  ],
  campaigns: { test: 'TEST campaign' }
  // Optional storage: window.sessionStorage (obtain safely if browser permits).
});

// Call only on reviewed public marketing pages, from the consent manager's lifecycle.
const observation = capture.capture({
  consent: 'granted', // Replace with the CURRENT real decision; never hard-code grant.
  url: window.location.href
});
const attributionFields = leadAttribution(observation);
// Later: your website's protected form receiver handles these untrusted fields.
// No CRM request or administrator token belongs in this browser code.
```

Consent is not inferred from a URL, cookie or presence of UTMs. The adapter starts without reading storage. Only the exact `granted` string allows capture; other values remove its own storage key and clear memory. Call again with the new decision on consent withdrawal. Withdrawal cannot remove an already-submitted CRM record, and this module does not establish a lawful consent policy. Do not initialize it on care, portal or payment pages.

Only exact approved origins/paths are accepted. Captured landing pages contain no query or fragment. Source requires a unique exact match on `utm_source` and `utm_medium`; absent, duplicate, unrecognized or ambiguous values remain Unknown. No assumption of Direct or organic search from a missing parameter/referrer. Campaigns require an exact approved token-to-label mapping. Approved configuration must itself exclude sensitive labels/paths. No referrer, keyword, raw campaign, click ID, patient identity or form field is collected.

First means **the earliest captured observation in this adapter's current consent/session window**, not necessarily the person's actual first introduction. Unknown is preserved even when a later paid source arrives. Later changed source/campaign/page observations stay separate; adjacent identical observations are suppressed. Only the first 20 later observations are retained; `omitted_touches` counts additional changed observations relative to the last retained one, not unique visits. There is no complete browsing history claim.

Optional storage must be sessionStorage-compatible and scoped to one siteId. Use a unique ID per practice/site; it is a namespace, not authorization. Storage failures fall back to instance memory and may lose history across reloads. Saved state is validated against the current configuration and expires 24 hours after the first captured observation (no sliding renewal). Expiration is enforced on the next approved capture, not by a background deletion timer. Tab/session closure normally clears sessionStorage; using localStorage changes that behavior and is not recommended. No cross-tab, cross-domain, cross-device identity or recovery is supplied. Browser storage can be modified by a visitor; its contents are never trusted identity evidence.

## Server handoff still required

`leadAttribution` returns only existing patient original-attribution fields. It returns Unknown if capture was not allowed. The site's protected server must validate identity and timestamps, resolve a fixed practice/connection from its configuration, enforce body limits/anti-abuse controls, and persist a stable submission ID and exact normalized payload for retries. It must reject unsupported fields and never accept a browser-selected practice, cash amount or event kind. Authentication secrets must remain server-side.

The current CRM sandbox endpoint still requires an administrator JWT and a TEST practice. **Do not connect this browser module directly to it, expose a JWT, or put an administrator session in a public website receiver.** Dedicated restricted, revocable integration authentication and a hardened receiver are the next increment. No token is issued by this adapter.

Subsequent observations are not automatically CRM journey events. The existing intake API requires touches on/after the lead timestamp; pre-lead visits cannot simply be posted as post-lead events. Preserve that distinction while designing the server contract. An eventual adapter needs stable subject/event IDs and an explicit mapping across lead/booking/payment systems; no patient is guessed by name or email here. No booking/treatment/cash facts are created or inferred. Existing Growth and ROAS definitions remain unchanged.

Remaining: restricted credentials and receiver; platform-specific installation and consent-manager wiring; server retry/error retention; cross-system identity reconciliation; provider sandbox signatures/status mappings; Ads spend imports; end-to-end and privacy/security acceptance. No Google services or live client sites are connected. This capture layer is not evidence of bank settlement, verified advertising clicks, causal lift or production readiness.
