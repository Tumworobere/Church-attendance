from django.contrib import admin

from .models import Attendance, Member, Ministry, Service, ServiceType, Visitor


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["full_name", "phone", "ministry", "cell", "status", "member_since"]
    list_filter = ["status", "ministry", "gender"]
    search_fields = ["first_name", "last_name", "phone", "email", "cell"]


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "first_visit", "follow_up", "member"]
    list_filter = ["follow_up"]
    search_fields = ["name", "phone", "email"]


class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0
    autocomplete_fields = ["member", "visitor"]
    readonly_fields = ["checked_in_at", "checked_in_by"]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["date", "service_type", "extra_headcount"]
    list_filter = ["service_type"]
    date_hierarchy = "date"
    inlines = [AttendanceInline]


admin.site.register(Ministry)
admin.site.register(ServiceType)
