"""Enforce tenant ownership for new tables and cross-record links in PostgreSQL."""

from django.db import migrations

from common.rls import get_disable_policy_sql, get_enable_policy_sql

TABLES = ("mp_patient", "mp_journey_event", "mp_receipt", "mp_marketing_spend")


def enable(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(get_enable_policy_sql(table))
        cursor.execute("""
            CREATE FUNCTION mp_validate_tenant_link() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_TABLE_NAME = 'mp_patient' THEN
                    IF NOT EXISTS (SELECT 1 FROM contacts WHERE id = NEW.contact_id AND org_id = NEW.org_id) THEN
                        RAISE EXCEPTION 'Patient contact must belong to the same practice' USING ERRCODE = '23514';
                    END IF;
                    IF TG_OP = 'UPDATE' AND (NEW.org_id, NEW.contact_id, NEW.original_source, NEW.original_campaign, NEW.original_keyword, NEW.original_landing_page, NEW.original_at, NEW.lead_at)
                        IS DISTINCT FROM (OLD.org_id, OLD.contact_id, OLD.original_source, OLD.original_campaign, OLD.original_keyword, OLD.original_landing_page, OLD.original_at, OLD.lead_at) THEN
                        RAISE EXCEPTION 'Original patient identity and attribution are immutable' USING ERRCODE = '23514';
                    END IF;
                ELSE
                    IF NOT EXISTS (SELECT 1 FROM mp_patient WHERE id = NEW.patient_id AND org_id = NEW.org_id) THEN
                        RAISE EXCEPTION 'Journey record must belong to the same practice as its patient' USING ERRCODE = '23514';
                    END IF;
                    IF TG_TABLE_NAME = 'mp_receipt' THEN
                      IF NEW.payment_id IS NOT NULL THEN
                        IF NOT EXISTS (SELECT 1 FROM mp_receipt WHERE id = NEW.payment_id AND org_id = NEW.org_id AND patient_id = NEW.patient_id AND kind = 'payment') THEN
                            RAISE EXCEPTION 'Refund payment must belong to the same patient and practice' USING ERRCODE = '23514';
                        END IF;
                      END IF;
                    END IF;
                END IF;
                RETURN NEW;
            END $$;
            CREATE TRIGGER mp_patient_link BEFORE INSERT OR UPDATE ON mp_patient FOR EACH ROW EXECUTE FUNCTION mp_validate_tenant_link();
            CREATE TRIGGER mp_event_link BEFORE INSERT OR UPDATE ON mp_journey_event FOR EACH ROW EXECUTE FUNCTION mp_validate_tenant_link();
            CREATE TRIGGER mp_receipt_link BEFORE INSERT OR UPDATE ON mp_receipt FOR EACH ROW EXECUTE FUNCTION mp_validate_tenant_link();
        """)


def disable(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for name, table in (
            ("mp_patient_link", "mp_patient"),
            ("mp_event_link", "mp_journey_event"),
            ("mp_receipt_link", "mp_receipt"),
        ):
            cursor.execute(f"DROP TRIGGER IF EXISTS {name} ON {table}")
        cursor.execute("DROP FUNCTION IF EXISTS mp_validate_tenant_link()")
        for table in TABLES:
            cursor.execute(get_disable_policy_sql(table))


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("patients", "0001_initial")]
    operations = [migrations.RunPython(enable, disable)]
