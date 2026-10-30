from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


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

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
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

    def last_seen(self):
        att = self.attendances.select_related("service").order_by("-service__date").first()
        return att.service.date if att else None


class Visitor(models.Model):
    class FollowUp(models.TextChoices):
        PENDING = "pending", "Pending"
        CONTACTED = "contacted", "Contacted"
        JOINED = "joined", "Joined"

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
    date = models.DateField(default=timezone.localdate)
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT, related_name="services")
    extra_headcount = models.PositiveIntegerField(default=0, help_text="Children or guests not registered individually")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "service_type__order"]
        constraints = [models.UniqueConstraint(fields=["date", "service_type"], name="unique_service_per_day")]

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
