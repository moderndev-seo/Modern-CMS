"""A cached prefix cannot advance over an unapplied receipt, even via SQL."""

from django.db import migrations

SQL = """
ALTER TABLE mp_integration_applied_prefix ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_integration_applied_prefix FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON mp_integration_applied_prefix USING
 (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE POLICY org_insert_check ON mp_integration_applied_prefix FOR INSERT WITH CHECK
 (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE FUNCTION mp_applied_prefix_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous_position bigint;
BEGIN
 IF TG_OP='DELETE' THEN
  RAISE EXCEPTION 'Applied prefix cannot be deleted' USING ERRCODE='23514';
 END IF;
 IF TG_OP='UPDATE' AND (NEW.id IS DISTINCT FROM OLD.id OR
   NEW.org_id IS DISTINCT FROM OLD.org_id OR
   NEW.connection_id IS DISTINCT FROM OLD.connection_id OR
   NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
  RAISE EXCEPTION 'Applied prefix identity is immutable' USING ERRCODE='23514';
 END IF;
 PERFORM 1 FROM mp_integration_connection WHERE id=NEW.connection_id
  AND org_id=NEW.org_id AND mode='fictional' FOR UPDATE;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'Invalid prefix connection' USING ERRCODE='23514';
 END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.position<>0 THEN
   RAISE EXCEPTION 'Applied prefix starts at zero' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
 END IF;
 previous_position:=OLD.position;
 IF NEW.position<previous_position OR NEW.position>previous_position+100 THEN
  RAISE EXCEPTION 'Invalid prefix advancement bounds' USING ERRCODE='23514';
 END IF;
 IF (SELECT count(*) FROM mp_integration_stream_page p
     WHERE p.org_id=NEW.org_id AND p.connection_id=NEW.connection_id
      AND p.stream='acquisition' AND p.position>previous_position
      AND p.position<=NEW.position) <> NEW.position-previous_position THEN
  RAISE EXCEPTION 'Applied prefix requires contiguous pages' USING ERRCODE='23514';
 END IF;
 IF EXISTS(
  SELECT 1 FROM mp_integration_stream_page p,
   LATERAL jsonb_array_elements_text(p.receipt_ids) r(receipt)
  WHERE p.org_id=NEW.org_id AND p.connection_id=NEW.connection_id
   AND p.stream='acquisition' AND p.position>previous_position
   AND p.position<=NEW.position AND NOT EXISTS(
    SELECT 1 FROM mp_integration_observation o
     JOIN mp_integration_work w ON w.id=o.work_id AND w.org_id=o.org_id
     JOIN mp_integration_pending pending ON pending.id=w.pending_id AND pending.org_id=w.org_id
    WHERE o.org_id=NEW.org_id AND pending.inbox_id=r.receipt::uuid
   )
 ) THEN
  RAISE EXCEPTION 'Applied prefix cannot skip unfinished receipts' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER mp_applied_prefix_guard BEFORE INSERT OR UPDATE OR DELETE
 ON mp_integration_applied_prefix FOR EACH ROW EXECUTE FUNCTION mp_applied_prefix_guard();
"""


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0017_applied_page_prefix")]
    operations = [migrations.RunPython(protect)]
