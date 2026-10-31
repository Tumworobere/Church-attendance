from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("branch/", views.branch_switch, name="branch_switch"),
    path("members/", views.member_list, name="member_list"),
    path("members/new/", views.member_form, name="member_new"),
    path("members/import/", views.member_import, name="member_import"),
    path("members/import/template.csv", views.member_import_template, name="member_import_template"),
    path("members/<int:pk>/", views.member_form, name="member_edit"),
    path("members/<int:pk>/delete/", views.member_delete, name="member_delete"),
    path("visitors/", views.visitor_list, name="visitor_list"),
    path("visitors/new/", views.visitor_form, name="visitor_new"),
    path("visitors/import/", views.visitor_import, name="visitor_import"),
    path("visitors/import/template.csv", views.visitor_import_template, name="visitor_import_template"),
    path("visitors/<int:pk>/", views.visitor_form, name="visitor_edit"),
    path("visitors/<int:pk>/follow-up/", views.visitor_follow_up, name="visitor_follow_up"),
    path("visitors/<int:pk>/delete/", views.visitor_delete, name="visitor_delete"),
    path("services/", views.service_open, name="service_open"),
    path("services/<int:pk>/", views.checkin, name="checkin"),
    path("services/<int:pk>/toggle/<int:member_id>/", views.toggle_attendance, name="toggle_attendance"),
    path("services/<int:pk>/visitor/<int:visitor_id>/remove/", views.remove_visitor_attendance, name="remove_visitor_attendance"),
    path("services/<int:pk>/extra/", views.update_extra, name="update_extra"),
    path("services/<int:pk>/delete/", views.service_delete, name="service_delete"),
    path("reports/", views.reports, name="reports"),
    path("export/members.csv", views.export_members, name="export_members"),
    path("export/visitors.csv", views.export_visitors, name="export_visitors"),
    path("export/attendance.csv", views.export_attendance, name="export_attendance"),
]
