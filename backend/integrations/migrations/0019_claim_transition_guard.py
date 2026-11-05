"""A released lease cannot be reused or an active claim silently replaced."""

from django.db import migrations

SQL = """
CREATE FUNCTION mp_processing_transition_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.state='processing' AND OLD.state<>'processing' THEN
  IF OLD.state NOT IN ('accepted','retry_due') OR
     NEW.attempt_count<>OLD.attempt_count+1 THEN
   RAISE EXCEPTION 'Processing requires a new claim attempt' USING ERRCODE='23514';
  END IF;
 ELSIF NEW.attempt_count<>OLD.attempt_count THEN
  RAISE EXCEPTION 'Attempt count changes only on a new claim' USING ERRCODE='23514';
 END IF;
 IF OLD.state='processing' AND NEW.state='processing' AND
    (NEW.lease_token IS DISTINCT FROM OLD.lease_token OR
     NEW.lease_expires_at IS DISTINCT FROM OLD.lease_expires_at) THEN
  RAISE EXCEPTION 'An active claim cannot be replaced' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER mp_processing_transition_guard BEFORE UPDATE ON mp_integration_work
 FOR EACH ROW EXECUTE FUNCTION mp_processing_transition_guard();
"""


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0018_applied_prefix_guards")]
    operations = [migrations.RunPython(protect)]
