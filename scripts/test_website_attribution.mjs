import test from 'node:test';
import assert from 'node:assert/strict';
import { createWebsiteAttribution, leadAttribution } from '../frontend/static/modern-practice/website-attribution.mjs';

const base = 'https://example.com/';
const google = `${base}?utm_source=google&utm_medium=cpc&utm_campaign=test`;
const email = `${base}?utm_source=newsletter&utm_medium=email`;
function fixture(overrides = {}) {
  let time = Date.parse('2026-10-13T12:00:00Z');
  const values = new Map();
  const calls = [];
  const storage = Object.fromEntries(['getItem', 'setItem', 'removeItem'].map((method) => [method, (...args) => {
    calls.push([method, ...args]);
    return method === 'getItem' ? values.get(args[0]) : method === 'setItem' ? values.set(...args) : values.delete(args[0]);
  }]));
  const options = { siteId: 'test-practice', pages: [base],
    sourceRules: [{ source: 'google', medium: 'cpc', value: 'google_ads' },
      { source: 'newsletter', medium: 'email', value: 'email' }],
    campaigns: { test: 'TEST campaign' }, storage, now: () => time, ...overrides };
  const adapter = createWebsiteAttribution(options);
  return { adapter, options, values, calls, advance: (ms) => { time += ms; },
    capture: (url = google, consent = 'granted') => adapter.capture({ url, consent }) };
}

test('no consent means no read/capture; withdrawal removes only owned data', () => {
  const f = fixture();
  assert.equal(f.calls.length, 0);
  for (const consent of [undefined, false, true, 'pending', 'denied']) {
    assert.deepEqual(leadAttribution(f.capture(google, consent === undefined ? 'pending' : consent)), { original_source: 'unknown' });
  }
  assert.ok(f.calls.every(([method]) => method === 'removeItem'));
  f.capture(); f.capture(google, 'denied');
  assert.equal(f.values.size, 0);
  assert.equal(f.capture(email).first.source, 'email');
});

test('first touch survives later touches, reloads and caller mutation', () => {
  const f = fixture(); const first = f.capture();
  first.first.source = 'meta_ads';
  f.advance(1000);
  const later = f.capture(email);
  assert.equal(later.first.source, 'google_ads');
  assert.equal(later.touches[0].source, 'email');
  const restored = createWebsiteAttribution(f.options).capture({ consent: 'granted', url: email });
  assert.deepEqual(restored, later);
  assert.equal(restored.touches.length, 1);
});

test('unknown first source is not guessed or replaced by a later paid click', () => {
  const f = fixture(); f.capture(base); f.advance(1000);
  const result = f.capture(google);
  assert.equal(leadAttribution(result).original_source, 'unknown');
  assert.equal(result.touches[0].source, 'google_ads');
});

test('only approved labels and canonical page survive hostile URLs', () => {
  const f = fixture();
  const result = f.capture(`${base}?utm_source=patient-name&utm_medium=cpc&utm_campaign=diagnosis&email=private&gclid=secret#medical-record`);
  const serialized = JSON.stringify([...f.values.values(), result]);
  for (const privateValue of ['patient-name', 'diagnosis', 'private', 'secret', 'medical-record']) assert.ok(!serialized.includes(privateValue));
  assert.equal(result.first.source, 'unknown');
  assert.equal(result.first.campaign, '');
  assert.equal(result.first.landing_page, base);
});

test('unapproved host/path and credential URLs neither read nor expose stored context', () => {
  const f = fixture();
  for (const url of ['https://evil.example/', `${base}patient/123`, 'https://user:pass@example.com/']) {
    assert.equal(f.capture(url).first, null);
  }
  assert.equal(f.calls.length, 0);
  f.capture();
  assert.equal(f.capture(`${base}billing`).first, null);
});

test('duplicate parameters and ambiguous source configuration stay unknown', () => {
  const f = fixture();
  assert.equal(f.capture(`${google}&utm_source=newsletter`).first.source, 'unknown');
  const rules = [{ source: 'google', medium: 'cpc', value: 'google_ads' }, { source: 'google', medium: 'cpc', value: 'email' }];
  assert.equal(fixture({ sourceRules: rules }).capture().first.source, 'unknown');
});

test('fixed 24-hour retention expires without renewal on later touches', () => {
  const f = fixture(); f.capture(); f.advance(23 * 3600000); f.capture(email);
  f.advance(3600000);
  assert.equal(f.capture(email).first.source, 'email');
  assert.equal(f.capture(email).touches.length, 0);
});

test('storage failures use memory; malformed/future/config-changed records are discarded', () => {
  const broken = fixture({ storage: { getItem() { throw Error(); }, removeItem() { throw Error(); }, setItem() { throw Error(); } } });
  assert.equal(broken.capture().persistence, 'memory');
  assert.equal(broken.capture(email).first.source, 'google_ads');
  for (const change of [(s) => { s.started += 999999; }, (s) => { s.config = 'other'; }, (s) => { s.touches = 'bad'; }]) {
    const f = fixture(); f.capture(); const [key, raw] = [...f.values][0];
    const saved = JSON.parse(raw); change(saved); f.values.set(key, JSON.stringify(saved));
    assert.equal(createWebsiteAttribution(f.options).capture({ consent: 'granted', url: email }).first.source, 'email');
  }
});

test('practice/site namespace isolation and explicit clear', () => {
  const f = fixture(); f.capture();
  const other = createWebsiteAttribution({ ...f.options, siteId: 'other-test' });
  assert.equal(other.capture({ consent: 'granted', url: email }).first.source, 'email');
  other.clear();
  assert.equal(f.values.size, 1);
  assert.equal(f.capture().first.source, 'google_ads');
});

test('bounded touch history reports omitted observations', () => {
  const f = fixture(); f.capture();
  let result;
  for (let i = 0; i < 25; i++) { f.advance(1000); result = f.capture(i % 2 ? google : email); }
  assert.equal(result.touches.length, 20);
  assert.ok(result.omitted_touches > 0);
  assert.equal(result.first.source, 'google_ads');
});

test('extra persisted fields are not returned or retained', () => {
  const f = fixture(); f.capture(); const [key, raw] = [...f.values][0];
  const saved = JSON.parse(raw); saved.first.email = 'private'; f.values.set(key, JSON.stringify(saved));
  const result = createWebsiteAttribution(f.options).capture({ consent: 'granted', url: google });
  assert.ok(!JSON.stringify(result).includes('private'));
  assert.ok(!f.values.get(key).includes('private'));
});

test('configuration rejects unsafe pages and unsupported sources', () => {
  for (const page of ['javascript:alert(1)', `${base}?patient=123`, `${base}#care`, 'https://user:pass@example.com/']) {
    assert.throws(() => fixture({ pages: [page] }));
  }
  assert.throws(() => fixture({ sourceRules: [{ source: 'x', medium: 'x', value: 'invented' }] }));
});


test('clock rollback rejects observation without overwriting known first touch', () => {
  const f = fixture(); f.capture(); f.advance(-1000);
  assert.equal(f.capture(email).status, 'clock_rejected');
  f.advance(2000);
  assert.equal(f.capture(email).first.source, 'google_ads');
});

test('malformed URLs expose no existing attribution; invalid stored JSON resets safely', () => {
  const f = fixture(); f.capture();
  assert.equal(f.capture('not a URL').first, null);
  const [key] = [...f.values.keys()]; f.values.set(key, '{invalid');
  assert.equal(createWebsiteAttribution(f.options).capture({ consent: 'granted', url: email }).first.source, 'email');
});
