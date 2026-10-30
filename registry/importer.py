"""Bulk upload of members and visitors from CSV. Each importer's columns match the matching export, so an export can be
edited and uploaded again (extra columns such as the visitors export's "Visits" are ignored)."""
import csv
import io
import re
from datetime import datetime

from django.utils import timezone

from .forms import MemberForm, VisitorForm
from .models import Member, Ministry, Visitor

# Day-first, as written in most places outside the US; ISO first because that's what our exports write.
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y"]
MAX_ROWS = 5000
DATE_HELP = "A date like 2026-10-18 or 18/10/2026 (day first)."
PHONE_HELP = "Format this column as Text in Excel so leading zeros and + are kept."


class UploadError(Exception):
    pass


def _choices(choices):
    """Accept either the stored value or the label, ignoring case: 'F', 'f', 'Female'."""
    return {k.lower(): v for v, label in choices for k in (v, label)}


def _labels(choices, sep):
    return sep.join(label for _, label in choices)


def _date(value):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return value  # let the form report it as invalid


def _clean(value):
    value = value.strip()
    # Undo the formula guard that views._csv adds on export ("'+256…" -> "+256…"). Older exports also wrote a
    # lone "'" for every blank cell.
    return value[1:] if value[:1] == "'" and value[1:2] in ("", "=", "+", "-", "@") else value


def _digits(phone):
    return re.sub(r"\D", "", phone)


def _decode(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")  # Excel's plain "CSV" on Windows


class Importer:
    noun = plural = ""
    form_class = None
    columns = {}  # CSV header -> form field, in template order
    aliases = {}  # older header names still accepted on upload (lowercase) -> form field
    required = []
    date_fields = []

    def guide(self):
        """(column, required, what to enter) rows for the upload page."""
        raise NotImplementedError

    def setup(self):
        """Load lookups and the keys of records already in the register."""
        raise NotImplementedError

    def prepare(self, data):
        """Normalise one row in place before validation; return {field: error} for problems the form can't word well."""
        for f in self.date_fields:
            if data.get(f):
                data[f] = _date(data[f])
        return {}

    def key(self, data):
        raise NotImplementedError

    def name(self, data):
        raise NotImplementedError

    def _rows(self, upload):
        raw = upload.read()
        if raw[:2] == b"PK":
            raise UploadError("This looks like an Excel workbook. In Excel choose File → Save As → “CSV UTF-8”, then upload that file.")
        text = _decode(raw)
        # Excel in some locales saves with ";" instead of ","; judge by the header row, which has no free text in it.
        delimiter = max(",;\t", key=text.split("\n", 1)[0].count)
        rows = csv.reader(io.StringIO(text), delimiter=delimiter)
        header = next(rows, None)
        if not header:
            raise UploadError("The file is empty.")
        by_name = {**self.aliases, **{c.lower(): f for c, f in self.columns.items()}}
        fields = [by_name.get(h.strip().lower()) for h in header]
        missing = [c for c in self.required if self.columns[c] not in fields]
        if missing:
            raise UploadError(f"Missing column: {', '.join(missing)}. Start from the template so the first row has the column names.")
        for line, row in enumerate(rows, start=2):  # row numbers as a spreadsheet shows them
            data = {f: _clean(v) for f, v in zip(fields, row) if f}
            if not any(data.values()):
                continue
            if line - 1 > MAX_ROWS:
                raise UploadError(f"Too many rows: upload at most {MAX_ROWS} {self.plural} at a time.")
            yield line, data

    def read(self, upload):
        """Return (forms, skipped, errors): valid unsaved forms, names already in the register, and error strings.
        Callers should save nothing if errors is non-empty."""
        forms, skipped, errors = [], [], []
        labels = {f: c for c, f in self.columns.items()}
        seen = self.setup()
        try:
            for line, data in self._rows(upload):
                row_errors = self.prepare(data)
                form = self.form_class(data)
                if not form.is_valid():
                    row_errors.update({f: " ".join(msgs) for f, msgs in form.errors.items() if f not in row_errors})
                if row_errors:
                    errors += [f"Row {line}: {labels.get(f, 'Row')}: {msg}" for f, msg in row_errors.items()]
                    continue
                key = self.key(data)
                if key in seen:
                    skipped.append(self.name(data))
                    continue
                seen.add(key)
                forms.append(form)
        except UploadError as e:
            return [], [], [str(e)]
        return forms, skipped, errors


class MemberImporter(Importer):
    noun, plural, form_class = "member", "members", MemberForm
    columns = {
        "First name": "first_name", "Last name": "last_name", "Gender": "gender", "Date of birth": "date_of_birth",
        "Phone": "phone", "Email": "email", "Address": "address", "Cell": "cell", "Ministry": "ministry",
        "Member since": "member_since", "Status": "status", "Notes": "notes",
    }
    aliases = {"household": "cell"}  # exports made before the field was renamed
    required = ["First name", "Last name"]
    date_fields = ["date_of_birth", "member_since"]

    def guide(self):
        ministries = [m.name for m in Ministry.objects.all()]
        return [
            ("First name", True, ""), ("Last name", True, ""),
            ("Gender", False, f"{_labels(Member.Gender.choices, ' or ')}, or just the first letter. Can be left blank."),
            ("Date of birth", False, DATE_HELP), ("Phone", False, PHONE_HELP), ("Email", False, "A valid email address."),
            ("Address", False, "Any text."), ("Cell", False, "The cell group this member belongs to."),
            ("Ministry", False, f"One of: {', '.join(ministries)}." if ministries else "No ministries yet; add them in the admin first."),
            ("Member since", False, "A date, as above. Left blank, it's set to today."),
            ("Status", False, f"{_labels(Member.Status.choices, ' or ')}. Left blank, it's set to Active."),
            ("Notes", False, "Any text."),
        ]

    def setup(self):
        self.genders, self.statuses = _choices(Member.Gender.choices), _choices(Member.Status.choices)
        self.ministries = {name.lower(): pk for pk, name in Ministry.objects.values_list("pk", "name")}
        self.today = timezone.localdate().isoformat()
        return {self.key({"first_name": f, "last_name": l, "phone": p})
                for f, l, p in Member.objects.values_list("first_name", "last_name", "phone")}

    def prepare(self, data):
        errors = super().prepare(data)
        if data.get("gender"):
            data["gender"] = self.genders.get(data["gender"].lower(), data["gender"])
        data["status"] = self.statuses.get(data.get("status", "").lower(), data.get("status")) or Member.Status.ACTIVE
        data["member_since"] = data.get("member_since") or self.today
        if data.get("ministry"):
            name = data["ministry"]
            data["ministry"] = self.ministries.get(name.lower())
            if data["ministry"] is None:
                errors["ministry"] = f"there is no ministry called “{name}”. Check the spelling or add it in the admin first."
        return errors

    def key(self, data):
        return data["first_name"].strip().lower(), data["last_name"].strip().lower(), _digits(data.get("phone", ""))

    def name(self, data):
        return f"{data['first_name']} {data['last_name']}".strip()


class VisitorImporter(Importer):
    noun, plural, form_class = "visitor", "visitors", VisitorForm
    columns = {
        "Name": "name", "Phone": "phone", "Email": "email", "Address": "address", "First visit": "first_visit",
        "Invited by": "invited_by", "Follow-up": "follow_up", "Notes": "notes",
    }
    required = ["Name"]
    date_fields = ["first_visit"]

    def guide(self):
        return [
            ("Name", True, "Full name."), ("Phone", False, PHONE_HELP), ("Email", False, "A valid email address."),
            ("Address", False, "Any text."), ("First visit", False, f"{DATE_HELP} Left blank, it's set to today."),
            ("Invited by", False, "Member name, flyer, online…"),
            ("Follow-up", False, f"{_labels(Visitor.FollowUp.choices, ', ')}. Left blank, it's set to Pending."),
            ("Notes", False, "Prayer requests or other notes."),
        ]

    def setup(self):
        self.follow_ups = _choices(Visitor.FollowUp.choices)
        self.today = timezone.localdate().isoformat()
        return {self.key({"name": n, "phone": p}) for n, p in Visitor.objects.values_list("name", "phone")}

    def prepare(self, data):
        errors = super().prepare(data)
        data["follow_up"] = self.follow_ups.get(data.get("follow_up", "").lower(), data.get("follow_up")) or Visitor.FollowUp.PENDING
        data["first_visit"] = data.get("first_visit") or self.today
        return errors

    def key(self, data):
        return " ".join(data["name"].lower().split()), _digits(data.get("phone", ""))

    def name(self, data):
        return data["name"]


MEMBERS, VISITORS = MemberImporter(), VisitorImporter()
