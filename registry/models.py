import calendar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


MONTHS = [(i, calendar.month_name[i]) for i in range(1, 13)]
# Leap-year lengths, so a 29 February birthday is allowed
DAYS_IN_MONTH = {i: calendar.monthrange(2000, i)[1] for i in range(1, 13)}


def birthday_error(day, month):
    """Why a day/month birthday is invalid, or None if it's fine (both blank is fine)."""
    if bool(day) != bool(month):
        return "Choose both the day and the month, or leave both blank."
    if day and day > DAYS_IN_MONTH[month]:
        return f"{calendar.month_name[month]} has only {DAYS_IN_MONTH[month]} days."
    return None


class Branch(models.Model):
    """A church branch. Members, visitors and services each belong to one; ministries and service types are shared."""
    name = models.CharField(max_length=100, unique=True, help_text="As shown in the header, e.g. Kisaasi Branch")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "branches"

    def __str__(self):
        return self.name


class Ministry(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "ministries"

    def __str__(self):
        return self.name


class ServiceType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Member(models.Model):
    class Gender(models.TextChoices):
        FEMALE = "F", "Female"
        MALE = "M", "Male"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="members")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)
    # Birthday without the year: the church records day and month only
    birth_day = models.PositiveSmallIntegerField(null=True, blank=True, choices=[(d, d) for d in range(1, 32)],
                                                 verbose_name="Birthday (day)")
    birth_month = models.PositiveSmallIntegerField(null=True, blank=True, choices=MONTHS, verbose_name="Birthday (month)")
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    cell = models.CharField(max_length=100, blank=True, help_text="The cell group this member belongs to")
    ministry = models.ForeignKey(Ministry, null=True, blank=True, on_delete=models.SET_NULL, related_name="members")
    member_since = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def initials(self):
        return (self.first_name[:1] + self.last_name[:1]).upper() or "?"

    @property
    def birthday(self):
        """e.g. "18 October", or "" if not recorded."""
        return f"{self.birth_day} {calendar.month_name[self.birth_month]}" if self.birth_day and self.birth_month else ""

    def clean(self):
        super().clean()
        if error := birthday_error(self.birth_day, self.birth_month):
            raise ValidationError({"birth_day": error})

    def last_seen(self):
        att = self.attendances.select_related("service").order_by("-service__date").first()
        return att.service.date if att else None


class Visitor(models.Model):
    class FollowUp(models.TextChoices):
        PENDING = "pending", "Pending"
        CONTACTED = "contacted", "Contacted"
        JOINED = "joined", "Joined"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="visitors")
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    first_visit = models.DateField(default=timezone.localdate)
    invited_by = models.CharField(max_length=200, blank=True, help_text="Member name, flyer, online…")
    follow_up = models.CharField(max_length=10, choices=FollowUp.choices, default=FollowUp.PENDING)
    notes = models.TextField(blank=True, verbose_name="Prayer requests / notes")
    member = models.OneToOneField(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="visitor_record")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-first_visit", "name"]

    def __str__(self):
        return self.name

    @property
    def initials(self):
        return "".join(w[0] for w in self.name.split()[:2]).upper() or "?"


class Service(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="services")
    date = models.DateField(default=timezone.localdate)
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT, related_name="services")
    extra_headcount = models.PositiveIntegerField(default=0, help_text="Children or guests not registered individually")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "service_type__order"]
        constraints = [models.UniqueConstraint(fields=["branch", "date", "service_type"], name="unique_service_per_day")]

    def __str__(self):
        return f"{self.service_type} · {self.date:%d %b %Y}"

    def counts(self):
        members = self.attendances.filter(member__isnull=False).count()
        visitors = self.attendances.filter(visitor__isnull=False).count()
        return {"members": members, "visitors": visitors, "extra": self.extra_headcount,
                "total": members + visitors + self.extra_headcount}


class Attendance(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="attendances")
    member = models.ForeignKey(Member, null=True, blank=True, on_delete=models.CASCADE, related_name="attendances")
    visitor = models.ForeignKey(Visitor, null=True, blank=True, on_delete=models.CASCADE, related_name="attendances")
    checked_in_at = models.DateTimeField(auto_now_add=True)
    checked_in_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(member__isnull=False, visitor__isnull=True) | Q(member__isnull=True, visitor__isnull=False)),
                name="attendance_member_xor_visitor",
            ),
            models.UniqueConstraint(fields=["service", "member"], condition=Q(member__isnull=False), name="unique_member_per_service"),
            models.UniqueConstraint(fields=["service", "visitor"], condition=Q(visitor__isnull=False), name="unique_visitor_per_service"),
        ]

    def __str__(self):
        return f"{self.member or self.visitor} @ {self.service}"
