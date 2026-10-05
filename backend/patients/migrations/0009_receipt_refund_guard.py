"""Enforce refund budgets even for writes outside the receipt API."""

from django.db import migrations


def protect(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
        CREATE FUNCTION mp_receipt_refund_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE cash record; refunded numeric;
        BEGIN
            IF TG_OP = 'UPDATE' AND
                (NEW.org_id, NEW.patient_id, NEW.kind) IS DISTINCT FROM
                (OLD.org_id, OLD.patient_id, OLD.kind) AND
                EXISTS (SELECT 1 FROM mp_receipt WHERE payment_id=OLD.id) THEN
                RAISE EXCEPTION 'A refunded payment cannot change patient, practice or kind'
                    USING ERRCODE='23514';
            END IF;
            IF NEW.kind = 'refund' THEN
                -- Updating the parent version serializes budgets at READ COMMITTED
                -- and forces a serialization failure for stale repeatable-read writers.
                -- No financial fields or audit timestamps change.
                UPDATE mp_receipt SET amount=amount
                    WHERE id=NEW.payment_id AND org_id=NEW.org_id
                        AND patient_id=NEW.patient_id AND kind='payment'
                    RETURNING * INTO cash;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'Refund payment must belong to the same patient and practice'
                        USING ERRCODE='23514';
                END IF;
                SELECT COALESCE(sum(amount),0) INTO refunded FROM mp_receipt
                    WHERE payment_id=NEW.payment_id AND org_id=NEW.org_id
                        AND kind='refund' AND id<>NEW.id;
                IF refunded + NEW.amount > cash.amount THEN
                    RAISE EXCEPTION 'Refunds exceed the original payment'
                        USING ERRCODE='23514';
                END IF;
            ELSIF NEW.kind = 'payment' AND TG_OP = 'UPDATE' THEN
                SELECT COALESCE(sum(amount),0) INTO refunded FROM mp_receipt
                    WHERE payment_id=NEW.id AND org_id=NEW.org_id AND kind='refund';
                IF NEW.amount < refunded THEN
                    RAISE EXCEPTION 'Payment cannot be less than its recorded refunds'
                        USING ERRCODE='23514';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER mp_receipt_refund_guard BEFORE INSERT OR UPDATE ON mp_receipt
            FOR EACH ROW EXECUTE FUNCTION mp_receipt_refund_guard();
        """)


def unprotect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("DROP TRIGGER mp_receipt_refund_guard ON mp_receipt")
            cursor.execute("DROP FUNCTION mp_receipt_refund_guard()")


class Migration(migrations.Migration):
    dependencies = [("patients", "0008_refund_allocation_lines")]
    operations = [migrations.RunPython(protect, unprotect)]
