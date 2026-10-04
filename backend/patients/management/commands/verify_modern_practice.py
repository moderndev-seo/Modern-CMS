"""Read seeded demos through real HTTP; exercise rejected cross-practice writes."""

import hashlib
import json
from decimal import Decimal

import requests
from django.core.management.base import BaseCommand, CommandError
from rest_framework_simplejwt.tokens import AccessToken

from common.models import Org, Profile, User
from patients.management.commands.seed_modern_practice import demo_id


class Command(BaseCommand):
    help = "Verify seeded demo API totals and isolation over real HTTP. Does not add patient records."

    def add_arguments(self, parser):
        parser.add_argument("--member-email", required=True)
        parser.add_argument("--api-url", default="http://127.0.0.1:8000")
        parser.add_argument("--frontend-url", default="")

    def handle(self, *args, **options):
        user = User.objects.filter(
            email__iexact=options["member_email"], is_active=True
        ).first()
        if not user:
            raise CommandError("An active demo member is required.")
        sessions = {}
        snapshots = {}
        for key in ("harbor", "cedar"):
            org = Org.objects.get(id=demo_id(key))
            profile = Profile.objects.get(org=org, user=user, is_active=True)
            token = AccessToken.for_user(user)
            token["org_id"] = str(org.id)
            token["org_name"] = org.name
            token["role"] = profile.role
            token["user_email"] = user.email
            session = requests.Session()
            session.headers["Authorization"] = f"Bearer {token}"
            sessions[key] = session
            root = options["api_url"].rstrip("/") + "/api/patients/"
            listing = session.get(root, timeout=90)
            listing.raise_for_status()
            if listing.json()["count"] != 3:
                raise CommandError(
                    "Expected three demo journeys. Use an unchanged seed for this smoke check."
                )
            detail = session.get(f"{root}{demo_id(key + ':alex')}/", timeout=90)
            detail.raise_for_status()
            patient = detail.json()
            if patient["original_source"] != "google_ads" or not any(
                e["source"] == "email" for e in patient["events"]
            ):
                raise CommandError(
                    "Original source / subsequent touch verification failed."
                )
            response = session.get(
                root + "growth/?start=2026-09-01&end=2026-09-30", timeout=90
            )
            response.raise_for_status()
            growth = response.json()
            expected = Decimal("1100") if key == "harbor" else Decimal("700")
            if (
                Decimal(str(growth["totals"]["net_revenue"])) != expected
                or Decimal(str(patient["net_revenue"])) != expected
            ):
                raise CommandError("Demo receipts and report do not reconcile.")
            billing_response = session.get(
                f"{root}{demo_id(key + ':alex')}/billing/", timeout=90
            )
            billing_response.raise_for_status()
            coverage = billing_response.json()["receipt_coverage"]
            covered_net = sum(
                Decimal(str(coverage[group]["net_collected"]))
                for group in ("linked", "unmatched", "needs_review")
            )
            invoice_net = sum(
                Decimal(str(row["net_collected"]))
                for row in coverage["by_invoice"].values()
            )
            if covered_net != expected or invoice_net != Decimal(
                str(coverage["linked"]["net_collected"])
            ):
                raise CommandError(
                    "Receipt coverage does not reconcile with collections."
                )
            self.stdout.write(
                "Receipt coverage groups and invoice links reconcile with net collections."
            )
            other = "cedar" if key == "harbor" else "harbor"
            other_patient = demo_id(other + ":alex")
            attempts = [
                session.post(
                    f"{root}{other_patient}/billing/matches/", json={}, timeout=90
                ),
                session.post(
                    f"{root}{demo_id(key + ':alex')}/billing/matches/",
                    json={
                        "receipt": str(demo_id(key + ":alex:payment")),
                        "invoice_payment": str(demo_id(other + ":billing:payment")),
                        "reason": "MUST-BE-REJECTED foreign invoice payment",
                    },
                    timeout=90,
                ),
                session.post(
                    f"{root}{demo_id(key + ':alex')}/billing/matches/",
                    json={
                        "receipt": str(demo_id(other + ":alex:payment")),
                        "invoice_payment": str(demo_id(key + ":billing:payment")),
                        "reason": "MUST-BE-REJECTED foreign receipt",
                    },
                    timeout=90,
                ),
                session.get(f"{root}{other_patient}/billing/", timeout=90),
                session.get(f"{root}{other_patient}/", timeout=90),
                session.get(f"{root}{other_patient}/events/", timeout=90),
                session.get(f"{root}{other_patient}/receipts/", timeout=90),
                session.post(
                    f"{root}{other_patient}/events/",
                    json={"kind": "treated"},
                    timeout=90,
                ),
                session.post(
                    f"{root}{other_patient}/receipts/",
                    json={
                        "kind": "payment",
                        "amount": "1",
                        "reference": "MUST-BE-REJECTED",
                    },
                    timeout=90,
                ),
                session.post(
                    root,
                    json={"contact": str(demo_id(other + ":alex:contact"))},
                    timeout=90,
                ),
                session.post(
                    f"{root}{demo_id(key + ':alex')}/receipts/",
                    json={
                        "kind": "refund",
                        "amount": "1",
                        "reference": "MUST-BE-REJECTED",
                        "payment": str(demo_id(other + ":alex:payment")),
                    },
                    timeout=90,
                ),
            ]
            if [r.status_code for r in attempts] != [404] * 9 + [400, 404]:
                raise CommandError(
                    f"Cross-practice checks failed: {[r.status_code for r in attempts]}"
                )
            snapshots[key] = {
                "patients": listing.json(),
                "patient": patient,
                "growth": growth,
            }
            self.stdout.write(
                f"{org.name}: 3 leads, 2 booked, 1 treated; net USD {expected}; 11 direct HTTP isolation checks passed."
            )
            if options["frontend_url"]:
                front = requests.Session()
                front.headers["Host"] = "localhost:5181"
                front.cookies.set("jwt_access", str(token))
                front.cookies.set("org", str(org.id))
                for path, marker in (
                    ("/patients", "Patient journeys"),
                    (f"/patients/{demo_id(key + ':alex')}", "Original attribution"),
                    (
                        "/growth?start=2026-09-01&end=2026-09-30",
                        "Revenue by original source",
                    ),
                    ("/patients/new", "Create patient journey"),
                    (
                        f"/patients/{demo_id(key + ':alex')}/billing",
                        "Patient collections",
                    ),
                    (
                        f"/patients/{demo_id(key + ':alex')}/appointments",
                        "Scheduled times and outcomes",
                    ),
                    ("/practice-modules/reviews", "Not implemented"),
                ):
                    page = front.get(
                        options["frontend_url"].rstrip("/") + path, timeout=180
                    )
                    if page.status_code != 200 or marker not in page.text:
                        raise CommandError(
                            f"Frontend page {path} failed: HTTP {page.status_code}"
                        )
                self.stdout.write(
                    "Seven authenticated frontend routes rendered successfully over HTTP."
                )
        reversal_checks = 0
        for key, session in sessions.items():
            other = "cedar" if key == "harbor" else "harbor"
            own_patient = demo_id(key + ":alex")
            foreign_patient = demo_id(other + ":alex")
            rejected = [
                session.post(
                    f"{root}{foreign_patient}/billing/reversals/", json={}, timeout=90
                )
            ]
            foreign_billing = sessions[other].get(
                f"{root}{foreign_patient}/billing/", timeout=90
            )
            foreign_billing.raise_for_status()
            before = foreign_billing.json()["matching"]
            for item in before["matches"]:
                rejected.append(
                    session.post(
                        f"{root}{own_patient}/billing/reversals/",
                        json={
                            "match": item["id"],
                            "reason": "MUST-BE-REJECTED foreign match",
                        },
                        timeout=90,
                    )
                )
            if any(response.status_code != 404 for response in rejected):
                raise CommandError("Match reversal cross-practice rejection failed.")
            after = sessions[other].get(f"{root}{foreign_patient}/billing/", timeout=90)
            after.raise_for_status()
            if after.json()["matching"] != before:
                raise CommandError(
                    "Foreign matching records changed during rejection checks."
                )
            reversal_checks += len(rejected)
        self.stdout.write(
            f"{reversal_checks} match reversal HTTP isolation checks passed."
        )
        appointment_checks = 0
        for key, session in sessions.items():
            other = "cedar" if key == "harbor" else "harbor"
            own_patient = demo_id(key + ":alex")
            foreign_patient = demo_id(other + ":alex")
            foreign_root = f"{root}{foreign_patient}/appointments/"
            rejected = [
                session.get(foreign_root, timeout=90),
                session.post(foreign_root, json={}, timeout=90),
            ]
            # Read with the rightful membership, then attempt a foreign link.
            appointments = sessions[other].get(foreign_root, timeout=90)
            appointments.raise_for_status()
            for appointment in appointments.json()["results"]:
                path = f"{root}{own_patient}/appointments/{appointment['id']}/"
                rejected.extend(
                    [
                        session.get(path, timeout=90),
                        session.patch(
                            path,
                            json={
                                "action": "cancelled",
                                "revision": appointment["revision"],
                                "reason": "MUST-BE-REJECTED cross-practice check",
                            },
                            timeout=90,
                        ),
                        session.patch(
                            path,
                            json={
                                "action": "reopened",
                                "revision": appointment["revision"],
                                "reason": "MUST-BE-REJECTED foreign correction",
                                "starts_at": appointment["starts_at"],
                                "ends_at": appointment["ends_at"],
                            },
                            timeout=90,
                        ),
                    ]
                )
            if any(response.status_code != 404 for response in rejected):
                raise CommandError("Appointment cross-practice rejection failed.")
            appointment_checks += len(rejected)
        self.stdout.write(
            f"{appointment_checks} appointment HTTP isolation checks passed."
        )
        anonymous = requests.get(root, timeout=90)
        if anonymous.status_code not in (401, 403):
            raise CommandError("Anonymous patient request was not rejected.")
        fingerprint = hashlib.sha256(
            json.dumps(snapshots, sort_keys=True).encode()
        ).hexdigest()
        self.stdout.write(f"Demo snapshot SHA256: {fingerprint}")
        self.stdout.write(
            self.style.SUCCESS(
                "Actual HTTP verification passed; no successful patient writes performed."
            )
        )
