/** Local capture only. No requests, cookies, analytics tags or patient/form data. */
const SOURCES = new Set([
  'google_ads',
  'organic_search',
  'meta_ads',
  'referral',
  'email',
  'direct',
  'unknown'
]);
const TTL = 24 * 60 * 60 * 1000;
const MAX_TOUCHES = 20;
const copy = (value) => JSON.parse(JSON.stringify(value));
const own = (object, key) => Object.hasOwn(object, key);

/**
 * Approved pages and exact UTM mappings are site configuration, never visitor input.
 * storage is optional (e.g. sessionStorage); failures fall back to this instance's memory.
 * A consent manager must call capture with its current explicit decision each time.
 */
export function createWebsiteAttribution({
  siteId,
  pages,
  sourceRules = [],
  campaigns = {},
  storage = null,
  now = () => Date.now()
}) {
  if (!/^[a-z0-9-]{1,60}$/.test(siteId)) throw new Error('Use a unique siteId.');
  const approved = new Set(
    pages.map((page) => {
      const url = new URL(page);
      if (
        !['https:', 'http:'].includes(url.protocol) ||
        url.username ||
        url.password ||
        url.search ||
        url.hash ||
        url.href !== page ||
        page.length > 1000
      ) {
        throw new Error('Pages must be exact canonical HTTP(S) URLs without query or fragment.');
      }
      return page;
    })
  );
  const rules = sourceRules.map(({ source, medium, value }) => {
    if (typeof source !== 'string' || typeof medium !== 'string' || !SOURCES.has(value)) {
      throw new Error('Invalid source rule.');
    }
    return { source, medium, value };
  });
  const campaignMap = { ...campaigns };
  if (Object.values(campaignMap).some((value) => typeof value !== 'string' || value.length > 255)) {
    throw new Error('Invalid approved campaign label.');
  }
  const key = `mp-attribution:v1:${siteId}`;
  // Changed site configuration invalidates previously captured values.
  const config = JSON.stringify([Array.from(approved), rules, campaignMap]);
  let state = null;
  let loaded = false;
  let persistence = storage ? 'session' : 'memory';

  function discard() {
    state = null;
    loaded = true;
    try {
      storage?.removeItem(key);
    } catch {
      persistence = 'memory';
    }
  }

  function validTouch(touch, time) {
    return (
      touch &&
      SOURCES.has(touch.source) &&
      (touch.campaign === '' || Object.values(campaignMap).includes(touch.campaign)) &&
      approved.has(touch.landing_page) &&
      typeof touch.occurred_at === 'string' &&
      Number.isFinite(Date.parse(touch.occurred_at)) &&
      Date.parse(touch.occurred_at) <= time
    );
  }

  function valid(saved, time) {
    return (
      saved?.version === 1 &&
      saved.config === config &&
      Number.isFinite(saved.started) &&
      saved.started <= time &&
      time < saved.started + TTL &&
      validTouch(saved.first, time) &&
      Date.parse(saved.first.occurred_at) === saved.started &&
      Array.isArray(saved.touches) &&
      saved.touches.length <= MAX_TOUCHES &&
      saved.touches.every(
        (t, i) =>
          validTouch(t, time) &&
          Date.parse(t.occurred_at) >=
            Date.parse(i ? saved.touches[i - 1].occurred_at : saved.first.occurred_at)
      ) &&
      Number.isSafeInteger(saved.omitted) &&
      saved.omitted >= 0
    );
  }

  function safeTouch(touch) {
    // Never propagate arbitrary fields from browser storage.
    return {
      source: touch.source,
      campaign: touch.campaign,
      landing_page: touch.landing_page,
      occurred_at: touch.occurred_at
    };
  }

  function snapshot(status) {
    return {
      status,
      persistence,
      first: state ? safeTouch(state.first) : null,
      touches: state ? state.touches.map(safeTouch) : [],
      omitted_touches: state?.omitted ?? 0
    };
  }

  return {
    clear: discard,
    capture({ consent, url }) {
      if (consent !== 'granted') {
        // Removal of this adapter's own key is permitted on withdrawal; never read it.
        discard();
        return snapshot('consent_required');
      }
      const time = now();
      if (!Number.isFinite(time)) throw new Error('Invalid clock.');
      let page;
      try {
        page = new URL(url);
      } catch {
        return {
          status: 'page_not_allowed',
          persistence,
          first: null,
          touches: [],
          omitted_touches: 0
        };
      }
      const canonical = `${page.origin}${page.pathname}`;
      if (page.username || page.password || !approved.has(canonical)) {
        // Do not expose existing attribution to an unapproved care/payment page.
        return {
          status: 'page_not_allowed',
          persistence,
          first: null,
          touches: [],
          omitted_touches: 0
        };
      }
      if (loaded && state && time < Date.parse((state.touches.at(-1) ?? state.first).occurred_at)) {
        // Preserve known first touch while a local clock moves backwards.
        return snapshot('clock_rejected');
      }
      if (!loaded) {
        loaded = true;
        try {
          const raw = storage?.getItem(key);
          if (raw && raw.length <= 32000) state = JSON.parse(raw);
        } catch {
          persistence = 'memory';
        }
      }
      if (!valid(state, time)) discard();
      const params = page.searchParams;
      const single = (name) => (params.getAll(name).length === 1 ? params.get(name) : null);
      const source = single('utm_source');
      const medium = single('utm_medium');
      const campaign = single('utm_campaign');
      const matches = rules.filter((rule) => rule.source === source && rule.medium === medium);
      const touch = {
        source: matches.length === 1 ? matches[0].value : 'unknown',
        campaign: campaign !== null && own(campaignMap, campaign) ? campaignMap[campaign] : '',
        landing_page: canonical,
        occurred_at: new Date(time).toISOString()
      };
      if (!state) {
        state = { version: 1, config, started: time, first: touch, touches: [], omitted: 0 };
      } else {
        const last = state.touches.at(-1) ?? state.first;
        if (['source', 'campaign', 'landing_page'].some((field) => last[field] !== touch[field])) {
          if (state.touches.length < MAX_TOUCHES) state.touches.push(touch);
          else state.omitted += 1;
        }
      }
      // Rebuild rather than persisting unknown fields from modified storage.
      state = {
        version: 1,
        config,
        started: state.started,
        first: safeTouch(state.first),
        touches: state.touches.map(safeTouch),
        omitted: state.omitted
      };
      try {
        storage?.setItem(key, JSON.stringify(state));
      } catch {
        persistence = 'memory';
      }
      return copy(snapshot('captured'));
    }
  };
}

/** Attribution fields only, for a website-server handoff; no identity or credential. */
export function leadAttribution(snapshot) {
  const first = snapshot.status === 'captured' ? snapshot.first : null;
  return first
    ? {
        original_source: first.source,
        original_campaign: first.campaign,
        original_landing_page: first.landing_page,
        original_at: first.occurred_at
      }
    : { original_source: 'unknown' };
}
