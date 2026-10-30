from django import forms
from django.utils import timezone

from .models import Member, Service, ServiceType, Visitor

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["first_name", "last_name", "gender", "date_of_birth", "phone", "email", "address",
                  "cell", "ministry", "member_since", "status", "notes"]
        widgets = {
            "date_of_birth": DATE,
            "member_since": DATE,
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Baptism date, pastoral notes, etc."}),
        }


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
