from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Attendance, Member, Ministry, Service, ServiceType, Visitor
from .stats import absence_streaks


class RegisterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("usher", password="pw")
        self.client.force_login(self.user)
        self.sunday = ServiceType.objects.get(name="Sunday Service")
        self.member = Member.objects.create(first_name="Grace", last_name="Akello", member_since=date(2026, 1, 1))

    def test_pages_require_login(self):
        self.client.logout()
        resp = self.client.get(reverse("dashboard"))
        self.assertRedirects(resp, reverse("login") + "?next=/")

    def test_all_pages_render(self):
        service = Service.objects.create(date=date(2026, 10, 18), service_type=self.sunday)
        visitor = Visitor.objects.create(name="John Doe")
        for name, args in [("dashboard", []), ("member_list", []), ("member_new", []), ("member_edit", [self.member.pk]),
                           ("visitor_list", []), ("visitor_new", []), ("visitor_edit", [visitor.pk]),
                           ("service_open", []), ("checkin", [service.pk]), ("reports", []),
                           ("export_members", []), ("export_visitors", []), ("export_attendance", []),
                           ("member_import", []), ("member_import_template", []),
                           ("visitor_import", []), ("visitor_import_template", [])]:
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)

    def test_open_service_reuses_existing(self):
        data = {"date": "2026-10-18", "service_type": self.sunday.pk}
        self.client.post(reverse("service_open"), data)
        self.client.post(reverse("service_open"), data)
        self.assertEqual(Service.objects.count(), 1)

    def test_toggle_attendance(self):
        service = Service.objects.create(date=date(2026, 10, 18), service_type=self.sunday)
        url = reverse("toggle_attendance", args=[service.pk, self.member.pk])
        resp = self.client.post(url, headers={"x-requested-with": "fetch"})
        self.assertEqual(resp.json()["present"], True)
        self.assertEqual(resp.json()["counts"]["members"], 1)
        resp = self.client.post(url, headers={"x-requested-with": "fetch"})
        self.assertEqual(resp.json()["present"], False)
        self.assertFalse(Attendance.objects.exists())

    def test_visitor_registered_at_service_is_checked_in(self):
        service = Service.objects.create(date=date(2026, 10, 18), service_type=self.sunday)
        self.client.post(reverse("visitor_new") + f"?service={service.pk}",
                         {"name": "New Person", "first_visit": "2026-10-18", "follow_up": "pending", "mark_present": "on"})
        self.assertEqual(service.counts()["visitors"], 1)

    def test_convert_visitor_to_member(self):
        visitor = Visitor.objects.create(name="Peter Okello", phone="0700")
        self.client.post(reverse("member_new") + f"?from_visitor={visitor.pk}",
                         {"first_name": "Peter", "last_name": "Okello", "member_since": "2026-10-18", "status": "active"})
        visitor.refresh_from_db()
        self.assertEqual(visitor.follow_up, Visitor.FollowUp.JOINED)
        self.assertEqual(visitor.member.full_name, "Peter Okello")

    def test_absence_streak(self):
        for d in (4, 11, 18):
            Service.objects.create(date=date(2026, 10, d), service_type=self.sunday)
        self.assertEqual(absence_streaks()[0]["missed"], 3)
        Attendance.objects.create(service=Service.objects.get(date=date(2026, 10, 18)), member=self.member)
        self.assertEqual(absence_streaks(), [])

    def _upload(self, text, encoding="utf-8"):
        return self.client.post(reverse("member_import"), {"file": SimpleUploadedFile("m.csv", text.encode(encoding))})

    def test_import_members(self):
        ministry = Ministry.objects.first()
        resp = self._upload(
            "First name,Last name,Gender,Date of birth,Phone,Ministry,Member since,Status\n"
            f"Sarah,Namata,female,18/10/1990,'+256700111222,{ministry.name.upper()},,\n"
            ",,,,,,,\n"
            "Grace,Akello,F,,,,,\n"  # already in the register (same name, no phone)
            "Paul,Ouma,M,1985-02-03,0772000111,,2020-01-05,Inactive\n")
        self.assertRedirects(resp, reverse("member_list"))
        sarah = Member.objects.get(first_name="Sarah")
        self.assertEqual((sarah.gender, sarah.date_of_birth, sarah.phone, sarah.ministry, sarah.status),
                         ("F", date(1990, 10, 18), "+256700111222", ministry, "active"))
        self.assertEqual(Member.objects.get(first_name="Paul").status, "inactive")
        self.assertEqual(Member.objects.count(), 3)

    def test_import_with_errors_saves_nothing(self):
        resp = self._upload("First name;Last name;Email;Ministry\nAnn;Mugisha;;\nBob;;not-an-email;Nowhere\n")
        self.assertEqual(Member.objects.count(), 1)
        errors = resp.context["errors"]
        self.assertTrue(any(e.startswith("Row 3: Last name") for e in errors))
        self.assertTrue(any(e.startswith("Row 3: Email") for e in errors))
        self.assertTrue(any("Nowhere" in e for e in errors))

    def test_import_needs_name_columns(self):
        resp = self._upload("Name,Phone\nAnn Mugisha,0700\n")
        self.assertIn("Missing column", resp.context["errors"][0])

    def test_export_round_trips_through_import(self):
        Member.objects.create(first_name="Ruth", last_name="Nambi", phone="+256 700 000 000", gender="F")
        exported = self.client.get(reverse("export_members")).content.decode("utf-8")
        self._upload(exported)
        self.assertEqual(Member.objects.count(), 2)  # everyone already there, nothing duplicated
        self._upload(exported.lstrip("\ufeff").replace("Ruth", "Ruthie"), encoding="cp1252")
        self.assertEqual(Member.objects.get(first_name="Ruthie").phone, "+256 700 000 000")

    def test_csv_export_leaves_blank_cells_blank(self):
        Member.objects.create(first_name="Ruth", last_name="Nambi", phone="+256 700")
        rows = self.client.get(reverse("export_members")).content.decode("utf-8-sig").splitlines()
        self.assertIn("Ruth,Nambi,,,'+256 700,,,,,", rows[2])

    def test_import_accepts_old_exports_with_quote_in_blank_cells(self):
        self._upload("First name,Last name,Gender,Email,Ministry\nRuth,Nambi,',',',\n")
        self.assertTrue(Member.objects.filter(first_name="Ruth", email="").exists())

    def test_import_visitors(self):
        Visitor.objects.create(name="John  Doe", phone="0700 123")
        resp = self.client.post(reverse("visitor_import"), {"file": SimpleUploadedFile("v.csv", (
            "Name,Phone,First visit,Invited by,Follow-up\n"
            "Mary Atim,'+256 711,18/10/2026,Grace,contacted\n"
            "john doe,0700123,,,\n"  # already there: same name and phone digits
            "Sam Kato,,,,\n").encode())})
        self.assertRedirects(resp, reverse("visitor_list"))
        mary = Visitor.objects.get(name="Mary Atim")
        self.assertEqual((mary.phone, mary.first_visit, mary.invited_by, mary.follow_up),
                         ("+256 711", date(2026, 10, 18), "Grace", "contacted"))
        self.assertEqual(Visitor.objects.get(name="Sam Kato").follow_up, "pending")
        self.assertEqual(Visitor.objects.count(), 3)

    def test_visitor_export_round_trips_through_import(self):
        Visitor.objects.create(name="Mary Atim", phone="+256 711")
        exported = self.client.get(reverse("export_visitors")).content.decode("utf-8")
        resp = self.client.post(reverse("visitor_import"), {"file": SimpleUploadedFile("v.csv", exported.replace("Mary", "Maria").encode())})
        self.assertRedirects(resp, reverse("visitor_list"))
        self.assertEqual(Visitor.objects.get(name="Maria Atim").phone, "+256 711")

    def test_visitor_import_errors(self):
        resp = self.client.post(reverse("visitor_import"), {"file": SimpleUploadedFile("v.csv", b"Name,Follow-up\nAnn,maybe\n")})
        self.assertTrue(resp.context["errors"][0].startswith("Row 2: Follow-up"))
        self.assertFalse(Visitor.objects.exists())

    def test_member_cell(self):
        self.client.post(reverse("member_new"), {"first_name": "Ann", "last_name": "Mugisha", "cell": "Kisaasi Central",
                                                 "member_since": "2026-10-18", "status": "active"})
        self.assertEqual(Member.objects.get(first_name="Ann").cell, "Kisaasi Central")
        self.assertContains(self.client.get(reverse("member_list") + "?q=central"), "Kisaasi Central")
        # exports made before the rename used a "Household" column
        self._upload("First name,Last name,Household\nBen,Ouma,Bukoto\n")
        self.assertEqual(Member.objects.get(first_name="Ben").cell, "Bukoto")
