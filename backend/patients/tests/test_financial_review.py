import csv
import io
from decimal import Decimal

from common.testing import rls_org
from patients.models import Receipt
from patients.statements import csv_cell
from patients.tests.test_corrections import cash
from patients.tests.test_credits import credit, reverse_credit
from patients.tests.test_journey import BASE, create
from patients.tests.test_matching import pair


def test_financial_paging_reaches_older_records_without_changing_totals(
    admin_client, org_a
):
    patient, receipt = cash(admin_client, org_a)
    with rls_org(org_a):
        for number in range(100):
            Receipt.objects.create(
                org=org_a,
                patient_id=patient["id"],
                kind="payment",
                amount=1,
                reference=f"TEST-page-{number}",
                occurred_at=receipt.occurred_at,
            )
    for route in ("billing", "allocations", "corrections", "exclusions"):
        first = admin_client.get(f"{BASE}{patient['id']}/{route}/").data
        result = admin_client.get(
            f"{BASE}{patient['id']}/{route}/", {"receipts_page": 2}
        )
        assert result.status_code == 200, result.data
        second = result.data
        records1 = (
            first["matching"]["receipts"] if route == "billing" else first["receipts"]
        )
        records2 = (
            second["matching"]["receipts"] if route == "billing" else second["receipts"]
        )
        assert len(records1) == 100 and len(records2) == 1
        assert len({r["id"] for r in records1 + records2}) == 101
        if route == "billing":
            assert first["net_collected"] == second["net_collected"] == 200
        if route == "allocations":
            assert first["totals"] == second["totals"]
        if route == "exclusions":
            assert len(second["retained_choices"]) == 101
        for invalid in ("0", "-1", "bad", "1000001"):
            assert (
                admin_client.get(
                    f"{BASE}{patient['id']}/{route}/", {"receipts_page": invalid}
                ).status_code
                == 400
            )


def test_statement_includes_credits_reversals_cash_and_unavailable_balances(
    admin_client, org_a
):
    patient, payment, receipt = pair(admin_client, org_a, "100.00")
    original_billed = payment.invoice.total_amount
    credited = credit(admin_client, patient, payment.invoice, amount="10.00")
    assert credited.status_code == 201, credited.data
    url = f"{BASE}{patient['id']}/statement/"
    data = admin_client.get(url).data
    assert (
        data["available"] is False and data["invoices"][0]["recorded_balance"] is None
    )
    assert data["invoices"][0]["active_credits"] == 10
    assert data["invoices"][0]["adjusted_billed"] == payment.invoice.total_amount - 10
    assert data["cash"]["net_collected"] == 100
    exported = admin_client.get(url, {"download": "csv"})
    assert exported["Cache-Control"] == "private, no-store"
    rows = list(csv.reader(io.StringIO(exported.data["csv"])))
    invoice_row = next(
        row for row in rows if row and row[0] == payment.invoice.invoice_number
    )
    assert (
        Decimal(invoice_row[3]) == 10
        and Decimal(invoice_row[4]) == payment.invoice.total_amount - 10
    )
    assert invoice_row[7] == ""
    assert reverse_credit(admin_client, patient, credited.data["id"]).status_code == 201
    restored = admin_client.get(url).data
    assert len(restored["credits"]) == 2
    assert restored["invoices"][0]["active_credits"] == 0
    payment.invoice.refresh_from_db()
    assert payment.invoice.total_amount == original_billed


def test_statement_permissions_and_safe_csv_text(
    admin_client, user_client, org_b_client, unauthenticated_client, org_a
):
    patient, _ = cash(admin_client, org_a)
    for client, expected in (
        (user_client, (403, 404)),
        (org_b_client, (404,)),
        (unauthenticated_client, (401, 403)),
    ):
        for query in ({}, {"download": "csv"}):
            assert (
                client.get(f"{BASE}{patient['id']}/statement/", query).status_code
                in expected
            )
    own = create(user_client)
    assert user_client.get(f"{BASE}{own['id']}/statement/").status_code == 403
    assert (
        admin_client.post(
            f"{BASE}{patient['id']}/statement/", {}, format="json"
        ).status_code
        == 405
    )
    for text in ("=1+1", " @SUM(1)", "\tformula", "-formula", "+formula"):
        assert csv_cell(text).startswith("'")
    assert csv_cell(Decimal("-10.00")) == "-10.00"
    assert csv_cell(None) == ""
