"""Audited cash dates; original facts remain in append-only snapshots."""

from django.db import migrations, models


def protect(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
        CREATE OR REPLACE FUNCTION mp_correction_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE cash record; parent_id uuid; last_revision integer; plan record;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'Cash correction history is append-only' USING ERRCODE='23514';
            END IF;
            IF NEW.created_by_id IS NULL OR NEW.reason !~ '[^[:space:]]' THEN
                RAISE EXCEPTION 'Correction requires an actor and reason' USING ERRCODE='23514';
            END IF;
            SELECT COALESCE(payment_id,id) INTO parent_id FROM mp_receipt
                WHERE id=NEW.receipt_id AND org_id=NEW.org_id AND patient_id=NEW.patient_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Correction receipt must belong to this patient and practice' USING ERRCODE='23514';
            END IF;
            PERFORM 1 FROM mp_receipt WHERE id=parent_id AND org_id=NEW.org_id
                AND patient_id=NEW.patient_id AND kind='payment' FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Correction payment must belong to this patient and practice' USING ERRCODE='23514';
            END IF;
            SELECT * INTO cash FROM mp_receipt WHERE id=NEW.receipt_id AND org_id=NEW.org_id FOR UPDATE;
            SELECT COALESCE(max(revision),0) INTO last_revision FROM mp_receipt_correction
                WHERE receipt_id=NEW.receipt_id AND org_id=NEW.org_id;
            IF NEW.revision <> last_revision+1
                OR (NEW.reference IS NULL AND NEW.occurred_at IS NULL AND NEW.amount=cash.amount)
                OR (NEW.occurred_at IS NOT NULL AND (NEW.reference IS NOT NULL OR NEW.amount<>cash.amount OR NEW.occurred_at=cash.occurred_at OR NEW.occurred_at>statement_timestamp()))
                OR (NEW.reference IS NOT NULL AND (NEW.amount<>cash.amount OR NEW.reference=cash.reference OR NEW.reference !~ '[^[:space:]]' OR NEW.reference<>btrim(NEW.reference))) THEN
                RAISE EXCEPTION 'Stale revision, unchanged value or invalid combined correction' USING ERRCODE='23514';
            END IF;
            IF EXISTS(SELECT 1 FROM mp_payment_match WHERE receipt_id=parent_id AND org_id=NEW.org_id AND active) THEN
                RAISE EXCEPTION 'Reverse the active match before correcting cash' USING ERRCODE='23514';
            END IF;
            SELECT * INTO plan FROM mp_receipt_allocation WHERE receipt_id=parent_id AND org_id=NEW.org_id ORDER BY revision DESC LIMIT 1;
            IF FOUND AND (plan.lines<>'[]'::jsonb OR plan.refund_lines<>'[]'::jsonb) THEN
                RAISE EXCEPTION 'Clear allocations before correcting cash' USING ERRCODE='23514';
            END IF;
            NEW.snapshot := to_jsonb(cash);
            RETURN NEW;
        END $$;
        CREATE OR REPLACE FUNCTION mp_correction_apply() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            UPDATE mp_receipt SET amount=NEW.amount, reference=COALESCE(NEW.reference, reference), occurred_at=COALESCE(NEW.occurred_at, occurred_at), updated_at=NEW.created_at, updated_by_id=NEW.created_by_id
                WHERE id=NEW.receipt_id AND org_id=NEW.org_id;
            RETURN NEW;
        END $$;
        CREATE OR REPLACE FUNCTION mp_receipt_audit_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'Cash records cannot be deleted' USING ERRCODE='23514';
            END IF;
            IF (NEW.id,NEW.org_id,NEW.patient_id,NEW.kind,NEW.payment_id,NEW.notes,NEW.created_at,NEW.created_by_id)
                IS DISTINCT FROM
                (OLD.id,OLD.org_id,OLD.patient_id,OLD.kind,OLD.payment_id,OLD.notes,OLD.created_at,OLD.created_by_id) THEN
                RAISE EXCEPTION 'Original cash identity and recorded details are immutable' USING ERRCODE='23514';
            END IF;
            IF NEW.occurred_at<>OLD.occurred_at AND (pg_trigger_depth()<2 OR NOT EXISTS(
                SELECT 1 FROM mp_receipt_correction WHERE receipt_id=NEW.id AND org_id=NEW.org_id
                    AND occurred_at=NEW.occurred_at AND (snapshot->>'occurred_at')::timestamptz=OLD.occurred_at
                    AND amount=OLD.amount AND NEW.amount=OLD.amount AND reference IS NULL
                    AND created_by_id=NEW.updated_by_id AND created_at=NEW.updated_at
                    AND revision=(SELECT max(revision) FROM mp_receipt_correction WHERE receipt_id=NEW.id AND org_id=NEW.org_id)
            )) THEN
                RAISE EXCEPTION 'Date changes require audited cash correction' USING ERRCODE='23514';
            END IF;
            IF NEW.reference<>OLD.reference AND (pg_trigger_depth()<2 OR NOT EXISTS(
                SELECT 1 FROM mp_receipt_correction WHERE receipt_id=NEW.id AND org_id=NEW.org_id
                    AND reference=NEW.reference AND snapshot->>'reference'=OLD.reference
                    AND amount=OLD.amount AND NEW.amount=OLD.amount
                    AND created_by_id=NEW.updated_by_id AND created_at=NEW.updated_at
                    AND revision=(SELECT max(revision) FROM mp_receipt_correction WHERE receipt_id=NEW.id AND org_id=NEW.org_id)
            )) THEN
                RAISE EXCEPTION 'Original cash reference is immutable outside audited correction' USING ERRCODE='23514';
            END IF;
            IF NEW.amount<>OLD.amount AND (pg_trigger_depth()<2 OR NOT EXISTS(
                SELECT 1 FROM mp_receipt_correction WHERE receipt_id=NEW.id AND org_id=NEW.org_id
                    AND amount=NEW.amount AND (snapshot->>'amount')::numeric=OLD.amount
                    AND created_by_id=NEW.updated_by_id AND created_at=NEW.updated_at
            )) THEN
                RAISE EXCEPTION 'Amount changes require audited cash correction' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;

        CREATE OR REPLACE FUNCTION mp_receipt_refund_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
                IF (TG_OP='INSERT' OR NEW.occurred_at IS DISTINCT FROM OLD.occurred_at)
                    AND (NEW.occurred_at < cash.occurred_at OR NEW.occurred_at > statement_timestamp()) THEN
                    RAISE EXCEPTION 'Refund date must be between payment and now' USING ERRCODE='23514';
                END IF;
                SELECT COALESCE(sum(amount),0) INTO refunded FROM mp_receipt
                    WHERE payment_id=NEW.payment_id AND org_id=NEW.org_id
                        AND kind='refund' AND id<>NEW.id;
                IF refunded + NEW.amount > cash.amount THEN
                    RAISE EXCEPTION 'Refunds exceed the original payment'
                        USING ERRCODE='23514';
                END IF;
            ELSIF NEW.kind = 'payment' AND TG_OP = 'UPDATE' THEN
                IF NEW.occurred_at IS DISTINCT FROM OLD.occurred_at AND
                    (NEW.occurred_at > statement_timestamp() OR EXISTS(
                        SELECT 1 FROM mp_receipt WHERE payment_id=NEW.id AND org_id=NEW.org_id
                            AND kind='refund' AND occurred_at<NEW.occurred_at
                    )) THEN
                    RAISE EXCEPTION 'Payment date cannot follow its refunds or now' USING ERRCODE='23514';
                END IF;
                SELECT COALESCE(sum(amount),0) INTO refunded FROM mp_receipt
                    WHERE payment_id=NEW.id AND org_id=NEW.org_id AND kind='refund';
                IF NEW.amount < refunded THEN
                    RAISE EXCEPTION 'Payment cannot be less than its recorded refunds'
                        USING ERRCODE='23514';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        """)


class Migration(migrations.Migration):
    dependencies = [("patients", "0012_receipt_reference_corrections")]
    operations = [
        migrations.AddField(
            model_name="receiptcorrection",
            name="occurred_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.RunPython(protect),
    ]
