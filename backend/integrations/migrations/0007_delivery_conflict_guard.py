"""Append-only same-practice conflict metadata; no rejected payload storage."""

from django.db import migrations

SQL = """
CREATE FUNCTION mp_ingress_conflict_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP<>'INSERT' THEN
  RAISE EXCEPTION 'Delivery conflict audit is immutable' USING ERRCODE='23514';
 END IF;
 IF NEW.attempted_digest !~ '^[0-9a-f]{64}$' OR NOT EXISTS(
   SELECT 1 FROM mp_integration_inbox i
   JOIN mp_integration_connection c ON c.namespace_id=i.namespace_id AND c.org_id=i.org_id
   JOIN mp_integration_credential k ON k.connection_id=c.id AND k.org_id=c.org_id
   WHERE i.id=NEW.inbox_id AND i.org_id=NEW.org_id AND k.id=NEW.credential_id
   AND i.semantic_digest<>NEW.attempted_digest
 ) THEN
  RAISE EXCEPTION 'Invalid conflict evidence binding' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
ALTER TABLE mp_integration_delivery_conflict ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_integration_delivery_conflict FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON mp_integration_delivery_conflict FOR ALL
 USING (org_id::text=NULLIF(current_setting('app.current_org',true),''))
 WITH CHECK (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE TRIGGER mp_ingress_conflict_guard BEFORE INSERT OR UPDATE OR DELETE
 ON mp_integration_delivery_conflict FOR EACH ROW EXECUTE FUNCTION mp_ingress_conflict_guard();
"""


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0006_delivery_conflict")]
    operations = [migrations.RunPython(protect)]
