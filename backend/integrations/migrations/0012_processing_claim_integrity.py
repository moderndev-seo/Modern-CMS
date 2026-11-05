"""Require complete atomic claim evidence and preserve terminal outcomes."""

from django.db import migrations

SQL = """
CREATE FUNCTION mp_processing_claim_required() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_work record;
BEGIN
 SELECT * INTO current_work FROM mp_integration_work WHERE id=NEW.id AND org_id=NEW.org_id;
 IF NOT FOUND OR (SELECT count(*) FROM mp_integration_attempt
   WHERE work_id=NEW.id AND org_id=NEW.org_id)<>current_work.attempt_count THEN
  RAISE EXCEPTION 'Work requires complete claim history' USING ERRCODE='23514';
 END IF;
 IF current_work.state='processing' AND NOT EXISTS(
   SELECT 1 FROM mp_integration_attempt WHERE work_id=NEW.id AND org_id=NEW.org_id
    AND number=current_work.attempt_count AND lease_token=current_work.lease_token
    AND lease_expires_at=current_work.lease_expires_at
 ) THEN
  RAISE EXCEPTION 'Work requires matching claim evidence' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER mp_processing_claim_required AFTER INSERT OR UPDATE
 ON mp_integration_work DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION mp_processing_claim_required();

CREATE FUNCTION mp_processing_terminal_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.state IN ('quarantined','terminal_failure','applied') AND NEW IS DISTINCT FROM OLD THEN
  RAISE EXCEPTION 'Terminal work needs separately authorized replay' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER mp_processing_terminal_guard BEFORE UPDATE ON mp_integration_work
 FOR EACH ROW EXECUTE FUNCTION mp_processing_terminal_guard();
"""


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0011_processing_guards")]
    operations = [migrations.RunPython(protect)]
