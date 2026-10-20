"""Frozen tenant/immutable evidence and atomic pending-work guards."""

from django.db import migrations

SQL = """
CREATE FUNCTION mp_ingress_storage_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent record;
BEGIN
 IF TG_OP<>'INSERT' THEN
  RAISE EXCEPTION 'Ingress evidence and pending markers are immutable' USING ERRCODE='23514';
 END IF;
 IF TG_TABLE_NAME='mp_integration_inbox' THEN
  SELECT * INTO parent FROM mp_integration_connection
   WHERE id=NEW.connection_id AND org_id=NEW.org_id AND namespace_id=NEW.namespace_id;
  IF NOT FOUND OR NEW.authorization_generation<>parent.authorization_generation
   OR NEW.manifest_digest<>parent.manifest_digest THEN
   RAISE EXCEPTION 'Invalid receipt connection binding' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM mp_integration_credential
    WHERE id=NEW.credential_id AND org_id=NEW.org_id AND connection_id=NEW.connection_id) THEN
   RAISE EXCEPTION 'Invalid receipt credential binding' USING ERRCODE='23514';
  END IF;
  IF NEW.schema_version<>'fixture.ingress/1'
   OR NEW.authorization_generation<1
   OR NEW.semantic_digest !~ '^[0-9a-f]{64}$'
   OR NEW.transport_digest !~ '^[0-9a-f]{64}$'
   OR NEW.replay_key_version !~ '^[A-Za-z0-9_-]{1,32}$'
   OR length(NEW.replay_ciphertext) NOT BETWEEN 100 AND 32768
   OR NEW.replay_ciphertext !~ '^[A-Za-z0-9_=-]+$' THEN
   RAISE EXCEPTION 'Invalid receipt evidence shape' USING ERRCODE='23514';
  END IF;
 ELSE
  IF NOT EXISTS(SELECT 1 FROM mp_integration_inbox WHERE id=NEW.inbox_id AND org_id=NEW.org_id) THEN
   RAISE EXCEPTION 'Invalid pending receipt binding' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION mp_ingress_pending_required() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM mp_integration_pending WHERE inbox_id=NEW.id AND org_id=NEW.org_id) THEN
  RAISE EXCEPTION 'Receipt requires durable pending work' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;

ALTER TABLE mp_integration_inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_integration_inbox FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON mp_integration_inbox FOR ALL
 USING (org_id::text=NULLIF(current_setting('app.current_org',true),''))
 WITH CHECK (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE TRIGGER mp_ingress_inbox_guard BEFORE INSERT OR UPDATE OR DELETE
 ON mp_integration_inbox FOR EACH ROW EXECUTE FUNCTION mp_ingress_storage_guard();
CREATE CONSTRAINT TRIGGER mp_ingress_pending_required AFTER INSERT
 ON mp_integration_inbox DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION mp_ingress_pending_required();

ALTER TABLE mp_integration_pending ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_integration_pending FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON mp_integration_pending FOR ALL
 USING (org_id::text=NULLIF(current_setting('app.current_org',true),''))
 WITH CHECK (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE TRIGGER mp_ingress_pending_guard BEFORE INSERT OR UPDATE OR DELETE
 ON mp_integration_pending FOR EACH ROW EXECUTE FUNCTION mp_ingress_storage_guard();
"""


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0003_durable_receipt_storage")]
    operations = [migrations.RunPython(protect)]
