"""Frozen fictional manifests and irreversible history/tenant guards."""

from django.db import migrations

SQL = """
CREATE FUNCTION mp_integration_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent record; member uuid; selected jsonb; frozen jsonb; allowed boolean; current_status text;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Integration metadata history cannot be deleted' USING ERRCODE='23514'; END IF;
 IF TG_TABLE_NAME='mp_integration_namespace' THEN
  IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'Namespace is immutable' USING ERRCODE='23514'; END IF;
  IF NEW.environment<>'fictional' OR NEW.provider_key NOT IN ('fixture_a','fixture_b') OR NEW.account_key !~ '^test_[A-Za-z0-9_-]{1,123}$' THEN RAISE EXCEPTION 'Invalid fictional namespace' USING ERRCODE='23514'; END IF;
  member:=NEW.created_by_profile_id;
 ELSIF TG_TABLE_NAME='mp_integration_connection' THEN
  SELECT * INTO parent FROM mp_integration_namespace WHERE id=NEW.namespace_id AND org_id=NEW.org_id;
  IF NOT FOUND OR parent.provider_key<>NEW.adapter_key OR NEW.mode<>'fictional' OR NEW.label !~ '^[A-Za-z0-9 _.-]{1,100}$' THEN RAISE EXCEPTION 'Invalid namespace or mode' USING ERRCODE='23514'; END IF;
  frozen := '{"fixture_a:acquisition":{"value":{"id":"fixture_a:acquisition","version":"1.0","contract":"1.0","fictional":true,"source_class":"acquisition","observations":["marketing.touch_observed","inquiry.created","inquiry.qualified","inquiry.disqualified"],"object_kinds":["inquiry","touch"],"transport":"fixture-json-a","history":"synthetic-only","coverage":"no-live-coverage"},"digest":"15aa775b8596236393bb635b5e4dfb9cba76c624a9ea6271df18fafdc91ff26b"},"fixture_a:booking":{"value":{"id":"fixture_a:booking","version":"1.0","contract":"1.0","fictional":true,"source_class":"booking","observations":["appointment.requested","appointment.booked","appointment.rescheduled","appointment.cancelled","appointment.no_show"],"object_kinds":["appointment"],"transport":"fixture-json-a","history":"synthetic-only","coverage":"no-live-coverage"},"digest":"a897334c9e8e032f5d6f07c0294283a4eeb6ef7b7870df2fe5fb3a842efa6f28"},"fixture_a:clinical":{"value":{"id":"fixture_a:clinical","version":"1.0","contract":"1.0","fictional":true,"source_class":"clinical","observations":["appointment.attended","consultation.completed","treatment.completed"],"object_kinds":["encounter","outcome"],"transport":"fixture-json-a","history":"synthetic-only","coverage":"no-live-coverage"},"digest":"db0e3b978288db32dccb08f2784efeecdec4946d451ab6d88f7f6c2269b2fd31"},"fixture_a:financial":{"value":{"id":"fixture_a:financial","version":"1.0","contract":"1.0","fictional":true,"source_class":"financial","observations":["payment.recorded","payment.authorized","payment.captured","payment.settled","refund.recorded","refund.settled","payment.disputed","chargeback.posted","chargeback.reversed"],"object_kinds":["transaction"],"transport":"fixture-json-a","history":"synthetic-only","coverage":"no-live-coverage"},"digest":"77f4cc8015e4d50c9dfb82d17341ffe2fe315422b63d296d2901719927ac5aeb"},"fixture_b:acquisition":{"value":{"id":"fixture_b:acquisition","version":"1.0","contract":"1.0","fictional":true,"source_class":"acquisition","observations":["marketing.touch_observed","inquiry.created","inquiry.qualified","inquiry.disqualified"],"object_kinds":["inquiry","touch"],"transport":"fixture-json-b","history":"synthetic-only","coverage":"no-live-coverage"},"digest":"1382635d4b5873c9b0da53af23b029e62acc5519bacff85416ffc900501e55df"},"fixture_b:booking":{"value":{"id":"fixture_b:booking","version":"1.0","contract":"1.0","fictional":true,"source_class":"booking","observations":["appointment.requested","appointment.booked","appointment.rescheduled","appointment.cancelled","appointment.no_show"],"object_kinds":["appointment"],"transport":"fixture-json-b","history":"synthetic-only","coverage":"no-live-coverage"},"digest":"5dabb085cc5af47adf3c12831352ffb31a29c879dd987231965818b75e47506b"},"fixture_b:clinical":{"value":{"id":"fixture_b:clinical","version":"1.0","contract":"1.0","fictional":true,"source_class":"clinical","observations":["appointment.attended","consultation.completed","treatment.completed"],"object_kinds":["encounter","outcome"],"transport":"fixture-json-b","history":"synthetic-only","coverage":"no-live-coverage"},"digest":"2c1d24ab934a188d81e1156af2387b676a1c5b47ff790b9d876e0f4b09f834b4"},"fixture_b:financial":{"value":{"id":"fixture_b:financial","version":"1.0","contract":"1.0","fictional":true,"source_class":"financial","observations":["payment.recorded","payment.authorized","payment.captured","payment.settled","refund.recorded","refund.settled","payment.disputed","chargeback.posted","chargeback.reversed"],"object_kinds":["transaction"],"transport":"fixture-json-b","history":"synthetic-only","coverage":"no-live-coverage"},"digest":"763ae61248a339f653f460ba883d389c3f77c9bb7a9d856695fed14a607bc8d8"}}'::jsonb;
  selected := frozen->(NEW.capabilities->>'id');
  IF selected IS NULL OR NEW.capabilities<>selected->'value' OR NEW.manifest_digest<>selected->>'digest' OR NEW.manifest_version<>'1.0' OR split_part(NEW.capabilities->>'id',':',1)<>NEW.adapter_key THEN RAISE EXCEPTION 'Invalid pinned manifest' USING ERRCODE='23514'; END IF;
  IF NEW.status NOT IN ('active','paused','revoked') OR (NEW.revoked_at IS NOT NULL)<>(NEW.status='revoked') OR NEW.authorization_generation<>NEW.revision OR NEW.revision<1 THEN RAISE EXCEPTION 'Invalid connection lifecycle' USING ERRCODE='23514'; END IF;
  IF TG_OP='INSERT' THEN
   IF NEW.revision<>1 OR NEW.status<>'active' THEN RAISE EXCEPTION 'Invalid initial state' USING ERRCODE='23514'; END IF;
   member:=NEW.created_by_profile_id;
  ELSE
   IF (to_jsonb(NEW)-ARRAY['status','revoked_at','revision','authorization_generation'])<>(to_jsonb(OLD)-ARRAY['status','revoked_at','revision','authorization_generation']) OR OLD.status='revoked' OR NEW.revision<>OLD.revision+1 OR (NEW.status<>OLD.status AND NOT ((OLD.status='active' AND NEW.status IN ('paused','revoked')) OR (OLD.status='paused' AND NEW.status IN ('active','revoked')))) THEN RAISE EXCEPTION 'Illegal connection change' USING ERRCODE='23514'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='mp_integration_credential' THEN
  SELECT * INTO parent FROM mp_integration_connection WHERE id=NEW.connection_id AND org_id=NEW.org_id FOR UPDATE;
  IF NOT FOUND OR NEW.scopes<>'["integration.probe"]'::jsonb OR NEW.digest_version<>'sha256-v1' OR NEW.token_digest !~ '^[0-9a-f]{64}$' OR NEW.locator_key_version !~ '^[A-Za-z0-9_-]{1,32}$' OR NEW.expires_at<=NEW.issued_at OR NEW.expires_at>NEW.issued_at+interval '30 days' OR (NEW.retire_at IS NOT NULL AND NEW.retire_at<NEW.issued_at) THEN RAISE EXCEPTION 'Invalid credential fields' USING ERRCODE='23514'; END IF;
  IF (NEW.revoked_at IS NULL)<>(NEW.revoked_by_profile_id IS NULL) OR (NEW.revoked_at IS NULL)<>(NEW.revocation_reason_code IS NULL) OR (NEW.revocation_reason_code IS NOT NULL AND NEW.revocation_reason_code NOT IN ('rotation','compromise','retired','operator_revoke')) THEN RAISE EXCEPTION 'Invalid revocation' USING ERRCODE='23514'; END IF;
  IF NEW.replaces_credential_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM mp_integration_credential WHERE id=NEW.replaces_credential_id AND org_id=NEW.org_id AND connection_id=NEW.connection_id AND id<>NEW.id) THEN RAISE EXCEPTION 'Foreign replacement' USING ERRCODE='23514'; END IF;
  IF TG_OP='INSERT' THEN
   IF parent.status<>'active' OR NEW.retire_at IS NOT NULL OR NEW.revoked_at IS NOT NULL OR (SELECT count(*) FROM mp_integration_credential WHERE connection_id=NEW.connection_id AND revoked_at IS NULL)>=2 THEN RAISE EXCEPTION 'Invalid issuance or credential slots full' USING ERRCODE='23514'; END IF;
   member:=NEW.issued_by_profile_id;
  ELSE
   IF (to_jsonb(NEW)-ARRAY['retire_at','revoked_at','revoked_by_profile_id','revocation_reason_code'])<>(to_jsonb(OLD)-ARRAY['retire_at','revoked_at','revoked_by_profile_id','revocation_reason_code']) OR OLD.revoked_at IS NOT NULL OR (OLD.retire_at IS NOT NULL AND (NEW.retire_at IS NULL OR NEW.retire_at>OLD.retire_at)) OR (NEW.retire_at IS DISTINCT FROM OLD.retire_at AND NEW.retire_at>statement_timestamp()+interval '24 hours') THEN RAISE EXCEPTION 'Credential fields cannot be extended or rewritten' USING ERRCODE='23514'; END IF;
   member:=NEW.revoked_by_profile_id;
  END IF;
 ELSIF TG_TABLE_NAME='mp_integration_audit' THEN
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Audit is append-only' USING ERRCODE='23514'; END IF;
  IF NEW.actor_kind<>'human' OR NEW.actor_profile_id IS NULL OR NEW.actor_credential_id IS NOT NULL OR NEW.request_fingerprint !~ '^[0-9a-f]{64}$' OR jsonb_typeof(NEW.details)<>'object' OR NEW.details-ARRAY['status','scopes','expires_at','replaces_credential_id','retire_at']<>'{}'::jsonb THEN RAISE EXCEPTION 'Invalid audit facts' USING ERRCODE='23514'; END IF;
  IF (NEW.details ? 'status' AND (jsonb_typeof(NEW.details->'status')<>'string' OR NEW.details->>'status' NOT IN ('active','paused','revoked')))
    OR (NEW.details ? 'scopes' AND NEW.details->'scopes'<>'["integration.probe"]'::jsonb)
    OR (NEW.details ? 'expires_at' AND (jsonb_typeof(NEW.details->'expires_at')<>'string' OR length(NEW.details->>'expires_at')>40))
    OR (NEW.details ? 'retire_at' AND jsonb_typeof(NEW.details->'retire_at') NOT IN ('string','null'))
    OR (NEW.details ? 'replaces_credential_id' AND jsonb_typeof(NEW.details->'replaces_credential_id') NOT IN ('string','null'))
    OR length(NEW.details::text)>400 THEN RAISE EXCEPTION 'Invalid audit value shape' USING ERRCODE='23514'; END IF;
  member:=NEW.actor_profile_id;
  IF NOT EXISTS(SELECT 1 FROM mp_integration_namespace WHERE id=NEW.namespace_id AND org_id=NEW.org_id) THEN RAISE EXCEPTION 'Foreign audit namespace' USING ERRCODE='23514'; END IF;
  IF NEW.connection_id IS NOT NULL THEN
   SELECT * INTO parent FROM mp_integration_connection WHERE id=NEW.connection_id AND org_id=NEW.org_id AND namespace_id=NEW.namespace_id;
   IF NOT FOUND OR NEW.new_generation<>parent.revision THEN RAISE EXCEPTION 'Foreign audit connection or generation' USING ERRCODE='23514'; END IF;
  END IF;
  IF NEW.credential_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM mp_integration_credential WHERE id=NEW.credential_id AND org_id=NEW.org_id AND connection_id=NEW.connection_id) THEN RAISE EXCEPTION 'Foreign audit credential' USING ERRCODE='23514'; END IF;
  IF NEW.connection_id IS NOT NULL THEN current_status:=parent.status; END IF;
  allowed := CASE NEW.action
   WHEN 'namespace.created' THEN NEW.reason_code='fixture_setup' AND NEW.connection_id IS NULL AND NEW.credential_id IS NULL AND NEW.new_generation IS NULL AND NEW.previous_generation IS NULL
   WHEN 'connection.created' THEN NEW.reason_code='fixture_setup' AND NEW.connection_id IS NOT NULL AND NEW.credential_id IS NULL AND NEW.new_generation=1 AND NEW.previous_generation IS NULL
   WHEN 'connection.paused' THEN NEW.reason_code='maintenance' AND current_status='paused'
   WHEN 'connection.resumed' THEN NEW.reason_code='resume' AND current_status='active'
   WHEN 'connection.revoked' THEN NEW.reason_code IN ('compromise','retired','operator_revoke') AND current_status='revoked'
   WHEN 'credential.issued' THEN NEW.reason_code='fixture_setup' AND NEW.credential_id IS NOT NULL
   WHEN 'credential.rotated' THEN NEW.reason_code='rotation' AND NEW.credential_id IS NOT NULL
   WHEN 'credential.revoked' THEN NEW.reason_code IN ('retired','operator_revoke') AND NEW.credential_id IS NOT NULL
   ELSE false END;
  IF NOT coalesce(allowed,false) THEN RAISE EXCEPTION 'Invalid audit action and reason' USING ERRCODE='23514'; END IF;
  IF NEW.action NOT IN ('namespace.created','connection.created') AND (NEW.connection_id IS NULL OR NEW.previous_generation IS NULL OR NEW.new_generation<>NEW.previous_generation+1) THEN RAISE EXCEPTION 'Invalid audit generation' USING ERRCODE='23514'; END IF;
 END IF;
 IF member IS NOT NULL AND NOT EXISTS(SELECT 1 FROM profile WHERE id=member AND org_id=NEW.org_id AND is_active AND role='ADMIN') THEN RAISE EXCEPTION 'Active same-practice administrator required' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION mp_integration_audit_required() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_TABLE_NAME='mp_integration_namespace' THEN
  IF NOT EXISTS(SELECT 1 FROM mp_integration_audit WHERE namespace_id=NEW.id AND org_id=NEW.org_id AND action='namespace.created') THEN RAISE EXCEPTION 'Namespace requires audit' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='mp_integration_connection' THEN
  IF NOT EXISTS(SELECT 1 FROM mp_integration_audit WHERE connection_id=NEW.id AND org_id=NEW.org_id AND new_generation=NEW.revision) THEN RAISE EXCEPTION 'Connection change requires audit' USING ERRCODE='23514'; END IF;
 ELSE
  IF TG_OP='INSERT' THEN
   IF NOT EXISTS(SELECT 1 FROM mp_integration_audit WHERE credential_id=NEW.id AND org_id=NEW.org_id AND action IN ('credential.issued','credential.rotated')) THEN RAISE EXCEPTION 'Issuance requires audit' USING ERRCODE='23514'; END IF;
  ELSIF NEW.revoked_at IS DISTINCT FROM OLD.revoked_at THEN
   IF NOT EXISTS(SELECT 1 FROM mp_integration_audit WHERE org_id=NEW.org_id AND connection_id=NEW.connection_id AND occurred_at=NEW.revoked_at AND (credential_id=NEW.id OR details->>'replaces_credential_id'=NEW.id::text OR action='connection.revoked')) THEN RAISE EXCEPTION 'Revocation requires audit' USING ERRCODE='23514'; END IF;
  ELSIF NEW.retire_at IS DISTINCT FROM OLD.retire_at THEN
   IF NOT EXISTS(SELECT 1 FROM mp_integration_audit WHERE org_id=NEW.org_id AND connection_id=NEW.connection_id AND action='credential.rotated' AND details->>'replaces_credential_id'=NEW.id::text AND (details->>'retire_at')::timestamptz=NEW.retire_at) THEN RAISE EXCEPTION 'Retirement requires audit' USING ERRCODE='23514'; END IF;
  END IF;
 END IF;
 RETURN NULL;
END $$;

ALTER TABLE mp_integration_namespace ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_integration_namespace FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON mp_integration_namespace FOR ALL USING (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE POLICY org_insert_check ON mp_integration_namespace FOR INSERT WITH CHECK (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE TRIGGER mp_integration_namespace_guard BEFORE INSERT OR UPDATE OR DELETE ON mp_integration_namespace FOR EACH ROW EXECUTE FUNCTION mp_integration_guard();
CREATE CONSTRAINT TRIGGER mp_integration_namespace_audit_required AFTER INSERT OR UPDATE ON mp_integration_namespace DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mp_integration_audit_required();

ALTER TABLE mp_integration_connection ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_integration_connection FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON mp_integration_connection FOR ALL USING (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE POLICY org_insert_check ON mp_integration_connection FOR INSERT WITH CHECK (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE TRIGGER mp_integration_connection_guard BEFORE INSERT OR UPDATE OR DELETE ON mp_integration_connection FOR EACH ROW EXECUTE FUNCTION mp_integration_guard();
CREATE CONSTRAINT TRIGGER mp_integration_connection_audit_required AFTER INSERT OR UPDATE ON mp_integration_connection DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mp_integration_audit_required();

ALTER TABLE mp_integration_credential ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_integration_credential FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON mp_integration_credential FOR ALL USING (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE POLICY org_insert_check ON mp_integration_credential FOR INSERT WITH CHECK (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE TRIGGER mp_integration_credential_guard BEFORE INSERT OR UPDATE OR DELETE ON mp_integration_credential FOR EACH ROW EXECUTE FUNCTION mp_integration_guard();
CREATE CONSTRAINT TRIGGER mp_integration_credential_audit_required AFTER INSERT OR UPDATE ON mp_integration_credential DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mp_integration_audit_required();

ALTER TABLE mp_integration_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_integration_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON mp_integration_audit FOR ALL USING (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE POLICY org_insert_check ON mp_integration_audit FOR INSERT WITH CHECK (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE TRIGGER mp_integration_audit_guard BEFORE INSERT OR UPDATE OR DELETE ON mp_integration_audit FOR EACH ROW EXECUTE FUNCTION mp_integration_guard();
"""


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0001_initial")]
    operations = [migrations.RunPython(protect)]
