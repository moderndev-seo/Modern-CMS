"""Fictional cursor cannot advance past a missing or foreign receipt."""

from django.db import migrations

SQL = """
ALTER TABLE mp_integration_stream_page ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_integration_stream_page FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON mp_integration_stream_page USING
 (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE POLICY org_insert_check ON mp_integration_stream_page FOR INSERT WITH CHECK
 (org_id::text=NULLIF(current_setting('app.current_org',true),''));
CREATE FUNCTION mp_stream_page_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE authority record; head record; receipt text;
BEGIN
 IF TG_OP<>'INSERT' THEN
  RAISE EXCEPTION 'Stream pages are immutable' USING ERRCODE='23514';
 END IF;
 SELECT * INTO authority FROM mp_integration_connection
  WHERE id=NEW.connection_id AND org_id=NEW.org_id FOR UPDATE;
 IF NOT FOUND OR authority.mode<>'fictional' OR authority.status<>'active'
  OR authority.authorization_generation<>NEW.authorization_generation
  OR authority.capabilities->>'ingress' IS DISTINCT FROM 'fixture.ingress/1'
  OR NEW.stream<>'acquisition' OR NEW.cursor IS NOT DISTINCT FROM NEW.previous_cursor THEN
  RAISE EXCEPTION 'Invalid fictional stream authority' USING ERRCODE='23514';
 END IF;
 IF jsonb_typeof(NEW.receipt_ids)<>'array' THEN
  RAISE EXCEPTION 'Invalid page receipt list' USING ERRCODE='23514';
 END IF;
 IF jsonb_array_length(NEW.receipt_ids)>100 OR
  (SELECT count(DISTINCT value) FROM jsonb_array_elements_text(NEW.receipt_ids))<>jsonb_array_length(NEW.receipt_ids) THEN
  RAISE EXCEPTION 'Invalid page receipt bounds' USING ERRCODE='23514';
 END IF;
 FOR receipt IN SELECT jsonb_array_elements_text(NEW.receipt_ids) LOOP
  IF receipt IS NULL OR receipt !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
   RAISE EXCEPTION 'Invalid receipt reference' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM mp_integration_inbox WHERE id=receipt::uuid
    AND org_id=NEW.org_id AND connection_id=NEW.connection_id
    AND authorization_generation=NEW.authorization_generation) THEN
   RAISE EXCEPTION 'Page requires durable same-stream receipts' USING ERRCODE='23514';
  END IF;
 END LOOP;
 SELECT * INTO head FROM mp_integration_stream_page
  WHERE org_id=NEW.org_id AND connection_id=NEW.connection_id AND stream=NEW.stream
  ORDER BY position DESC LIMIT 1;
 IF FOUND THEN
  IF NEW.previous_cursor IS DISTINCT FROM head.cursor THEN
   RAISE EXCEPTION 'Page must extend current cursor' USING ERRCODE='23514';
  END IF;
  NEW.position:=head.position+1;
 ELSE
  IF NEW.previous_cursor IS NOT NULL THEN
   RAISE EXCEPTION 'First page cannot skip a predecessor' USING ERRCODE='23514';
  END IF;
  NEW.position:=1;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER mp_stream_page_guard BEFORE INSERT OR UPDATE OR DELETE
 ON mp_integration_stream_page FOR EACH ROW EXECUTE FUNCTION mp_stream_page_guard();
"""


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0015_fictional_stream_pages")]
    operations = [migrations.RunPython(protect)]
