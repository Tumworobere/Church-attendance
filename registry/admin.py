from django.contrib import admin

from .models import Attendance, Branch, Member, Ministry, Service, ServiceType, Visitor


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["full_name", "branch", "phone", "ministry", "cell", "status", "member_since"]
    list_filter = ["branch", "status", "ministry", "gender"]
    search_fields = ["first_name", "last_name", "phone", "email", "cell"]


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ["name", "branch", "phone", "first_visit", "follow_up", "member"]
    list_filter = ["branch", "follow_up"]
    search_fields = ["name", "phone", "email"]


class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0
    autocomplete_fields = ["member", "visitor"]
    readonly_fields = ["checked_in_at", "checked_in_by"]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["date", "branch", "service_type", "extra_headcount"]
    list_filter = ["branch", "service_type"]
    date_hierarchy = "date"
    inlines = [AttendanceInline]


admin.site.register(Branch)
admin.site.register(Ministry)
admin.site.register(ServiceType)
