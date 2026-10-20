"""Allow only one-way expired evidence erasure; keep immutable receipt identity."""

from django.db import migrations

SQL = """

CREATE OR REPLACE FUNCTION mp_ingress_storage_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent record;
BEGIN
 IF TG_TABLE_NAME='mp_integration_inbox' AND TG_OP='UPDATE' THEN
  IF OLD.replay_purged_at IS NOT NULL OR NEW.replay_purged_at IS NULL
   OR NEW.replay_ciphertext<>'' OR OLD.replay_retention_policy<>'fixture-24h-v1'
   OR OLD.created_at+interval '24 hours'>statement_timestamp()
   OR (to_jsonb(NEW)-ARRAY['replay_ciphertext','replay_purged_at'])
      <>(to_jsonb(OLD)-ARRAY['replay_ciphertext','replay_purged_at']) THEN
   RAISE EXCEPTION 'Only expired replay evidence may be purged once' USING ERRCODE='23514';
  END IF;
  NEW.replay_purged_at:=statement_timestamp();
  RETURN NEW;
 END IF;
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
  IF NEW.replay_retention_policy<>'fixture-24h-v1' OR NEW.replay_purged_at IS NOT NULL
   OR NEW.schema_version<>'fixture.ingress/1'
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

"""


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0008_replay_retention")]
    operations = [migrations.RunPython(protect)]
