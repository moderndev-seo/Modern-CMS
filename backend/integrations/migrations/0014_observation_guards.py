"""Immutable fictional observations and atomic applied-state binding."""

from django.db import migrations

SQL = """
ALTER TABLE mp_integration_observation ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_integration_observation FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON mp_integration_observation USING
 (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE POLICY org_insert_check ON mp_integration_observation FOR INSERT WITH CHECK
 (org_id::text=NULLIF(current_setting('app.current_org',true),''));

CREATE FUNCTION mp_observation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP<>'INSERT' THEN
  RAISE EXCEPTION 'Observations are immutable' USING ERRCODE='23514';
 END IF;
 IF NEW.mapping_version<>'fixture.normalized/1'
  OR NEW.event_type NOT IN ('marketing.touch_observed','inquiry.created','inquiry.qualified','inquiry.disqualified')
  OR NOT EXISTS (
    SELECT 1 FROM mp_integration_work w
    JOIN mp_integration_pending p ON p.id=w.pending_id AND p.org_id=w.org_id
    JOIN mp_integration_inbox i ON i.id=p.inbox_id AND i.org_id=p.org_id
    JOIN mp_integration_connection c ON c.id=i.connection_id AND c.org_id=i.org_id
    WHERE w.id=NEW.work_id AND w.org_id=NEW.org_id AND w.state='processing'
      AND w.lease_token=NEW.lease_token AND w.lease_expires_at>clock_timestamp()
      AND i.semantic_digest=NEW.semantic_digest AND i.replay_purged_at IS NULL
      AND i.created_at+interval '24 hours'>clock_timestamp()
      AND c.status='active' AND c.mode='fictional'
      AND c.authorization_generation=i.authorization_generation
      AND c.manifest_digest=i.manifest_digest
      AND c.capabilities->>'ingress'='fixture.ingress/1'
      AND c.capabilities->>'source_class'='acquisition'
  ) THEN
  RAISE EXCEPTION 'Invalid observation authority or binding' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER mp_observation_guard BEFORE INSERT OR UPDATE OR DELETE
 ON mp_integration_observation FOR EACH ROW EXECUTE FUNCTION mp_observation_guard();

CREATE FUNCTION mp_observation_result_required() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target_id uuid; target_org uuid; result_state text; has_observation boolean;
BEGIN
 IF TG_TABLE_NAME='mp_integration_work' THEN
  target_id:=NEW.id; target_org:=NEW.org_id;
 ELSE
  target_id:=NEW.work_id; target_org:=NEW.org_id;
 END IF;
 SELECT state INTO result_state FROM mp_integration_work WHERE id=target_id AND org_id=target_org;
 SELECT EXISTS(SELECT 1 FROM mp_integration_observation WHERE work_id=target_id AND org_id=target_org) INTO has_observation;
 IF result_state IS NULL OR (result_state='applied')<>has_observation THEN
  RAISE EXCEPTION 'Applied state and observation must commit together' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER mp_work_observation_required AFTER INSERT OR UPDATE
 ON mp_integration_work DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION mp_observation_result_required();
CREATE CONSTRAINT TRIGGER mp_observation_result_required AFTER INSERT
 ON mp_integration_observation DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION mp_observation_result_required();
"""


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0013_fictional_observation")]
    operations = [migrations.RunPython(protect)]
