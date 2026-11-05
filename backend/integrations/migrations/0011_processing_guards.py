"""Frozen RLS and same-practice guards for scheduling and claim evidence."""

from django.db import migrations

SQL = """
ALTER TABLE mp_integration_work ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_integration_work FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON mp_integration_work USING
 (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE POLICY org_insert_check ON mp_integration_work FOR INSERT WITH CHECK
 (org_id::text=NULLIF(current_setting('app.current_org',true),''));
ALTER TABLE mp_integration_attempt ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_integration_attempt FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON mp_integration_attempt USING
 (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE POLICY org_insert_check ON mp_integration_attempt FOR INSERT WITH CHECK
 (org_id::text=NULLIF(current_setting('app.current_org',true),''));

CREATE FUNCTION mp_processing_work_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN
  RAISE EXCEPTION 'Processing history cannot be deleted' USING ERRCODE='23514';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM mp_integration_pending
   WHERE id=NEW.pending_id AND org_id=NEW.org_id) THEN
  RAISE EXCEPTION 'Invalid pending work binding' USING ERRCODE='23514';
 END IF;
 IF TG_OP='INSERT' AND (NEW.state<>'accepted' OR NEW.attempt_count<>0
   OR NEW.reason_code<>'') THEN
  RAISE EXCEPTION 'Work must start accepted' USING ERRCODE='23514';
 END IF;
 IF TG_OP='UPDATE' AND (NEW.id<>OLD.id OR NEW.org_id<>OLD.org_id
   OR NEW.pending_id<>OLD.pending_id OR NEW.created_at<>OLD.created_at
   OR NEW.attempt_count<OLD.attempt_count OR NEW.attempt_count>OLD.attempt_count+1) THEN
  RAISE EXCEPTION 'Invalid processing history change' USING ERRCODE='23514';
 END IF;
 IF NEW.state NOT IN ('accepted','processing','retry_due','quarantined','terminal_failure','applied')
   OR NEW.attempt_count>6
   OR NEW.reason_code NOT IN ('','revoked','evidence_unavailable','transient','attempts_exhausted','lease_expired')
   OR (NEW.state='processing' AND (NEW.lease_token IS NULL OR NEW.lease_expires_at IS NULL OR NEW.attempt_count=0))
   OR (NEW.state<>'processing' AND (NEW.lease_token IS NOT NULL OR NEW.lease_expires_at IS NOT NULL)) THEN
  RAISE EXCEPTION 'Invalid scheduling shape' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER mp_processing_work_guard BEFORE INSERT OR UPDATE OR DELETE
 ON mp_integration_work FOR EACH ROW EXECUTE FUNCTION mp_processing_work_guard();

CREATE FUNCTION mp_processing_attempt_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP<>'INSERT' THEN
  RAISE EXCEPTION 'Claim evidence is immutable' USING ERRCODE='23514';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM mp_integration_work WHERE id=NEW.work_id
   AND org_id=NEW.org_id AND state='processing' AND attempt_count=NEW.number
   AND lease_token=NEW.lease_token AND lease_expires_at=NEW.lease_expires_at)
   OR NEW.number NOT BETWEEN 1 AND 6 OR NEW.lease_expires_at<=NEW.created_at THEN
  RAISE EXCEPTION 'Invalid processing claim binding' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER mp_processing_attempt_guard BEFORE INSERT OR UPDATE OR DELETE
 ON mp_integration_attempt FOR EACH ROW EXECUTE FUNCTION mp_processing_attempt_guard();
"""


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0010_processing_storage")]
    operations = [migrations.RunPython(protect)]
