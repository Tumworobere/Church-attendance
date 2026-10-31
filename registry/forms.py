from django import forms
from django.utils import timezone

from .models import MONTHS, Member, Service, ServiceType, Visitor, birthday_error

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class BirthdayWidget(forms.MultiWidget):
    """Day and month pickers side by side in one field."""
    template_name = "registry/widgets/birthday.html"

    def __init__(self, attrs=None):
        super().__init__([
            forms.Select(choices=[("", "Day")] + [(d, d) for d in range(1, 32)], attrs={"aria-label": "Birthday day"}),
            forms.Select(choices=[("", "Month")] + MONTHS, attrs={"aria-label": "Birthday month"}),
        ], attrs)

    def decompress(self, value):
        return list(value) if value else [None, None]


class BirthdayField(forms.MultiValueField):
    """Cleans to (day, month) as ints, or (None, None) when left blank."""
    widget = BirthdayWidget

    def __init__(self, **kwargs):
        super().__init__(fields=[forms.TypedChoiceField(choices=[(d, d) for d in range(1, 32)], coerce=int),
                                 forms.TypedChoiceField(choices=MONTHS, coerce=int)],
                         require_all_fields=False, required=False, **kwargs)

    def compress(self, data_list):
        day, month = (list(data_list) + [None, None])[:2]
        return (day or None, month or None)


class MemberForm(forms.ModelForm):
    birthday = BirthdayField(label="Birthday")
    field_order = ["first_name", "last_name", "gender", "birthday"]

    class Meta:
        model = Member
        fields = ["first_name", "last_name", "gender", "phone", "email", "address",
                  "cell", "ministry", "member_since", "status", "notes"]
        widgets = {
            "member_since": DATE,
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Baptism date, pastoral notes, etc."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.birth_day:
            self.initial.setdefault("birthday", (self.instance.birth_day, self.instance.birth_month))

    def clean(self):
        cleaned = super().clean()
        day, month = cleaned.get("birthday") or (None, None)
        if error := birthday_error(day, month):
            self.add_error("birthday", error)
            day = month = None  # keep Member.clean from repeating the error on fields this form doesn't have
        self.instance.birth_day, self.instance.birth_month = day, month
        return cleaned


class VisitorForm(forms.ModelForm):
    mark_present = forms.BooleanField(required=False, initial=True, label="Mark present at this service")

    class Meta:
        model = Visitor
        fields = ["name", "phone", "email", "address", "first_visit", "invited_by", "follow_up", "notes"]
        widgets = {"first_visit": DATE, "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, for_service=None, **kwargs):
        super().__init__(*args, **kwargs)
        if for_service is None:
            del self.fields["mark_present"]
        elif not self.is_bound:
            self.initial.setdefault("first_visit", for_service.date)


class OpenServiceForm(forms.Form):
    date = forms.DateField(widget=DATE, initial=timezone.localdate)
    service_type = forms.ModelChoiceField(queryset=ServiceType.objects.all(), empty_label=None, label="Service")


class ExtraHeadcountForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["extra_headcount"]


class DateRangeForm(forms.Form):
    start = forms.DateField(widget=DATE, required=False, label="From")
    end = forms.DateField(widget=DATE, required=False, label="To")
