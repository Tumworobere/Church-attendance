import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import Resolver404, resolve
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import importer, stats
from .forms import DateRangeForm, ExtraHeadcountForm, MemberForm, OpenServiceForm, VisitorForm
from .middleware import SESSION_KEY
from .models import Attendance, Branch, Member, Ministry, Service, Visitor


# ---------- dashboard ----------

@login_required
def dashboard(request):
    today = timezone.localdate()
    b = request.branch
    recent = stats.services_with_counts(Service.objects.filter(branch=b).order_by("-date", "-service_type__order")[:12])
    recent.reverse()
    last8 = recent[-8:]
    active = Member.objects.filter(branch=b, status=Member.Status.ACTIVE)
    pending = Visitor.objects.filter(branch=b, follow_up=Visitor.FollowUp.PENDING)
    context = {
        "active_count": active.count(),
        "member_total": Member.objects.filter(branch=b).count(),
        "last_service": recent[-1] if recent else None,
        "average": round(sum(s.total for s in last8) / len(last8)) if last8 else None,
        "average_over": len(last8),
        "new_visitors": Visitor.objects.filter(branch=b, first_visit__year=today.year, first_visit__month=today.month).count(),
        "pending_count": pending.count(),
        "pending": pending[:8],
        "birthdays": active.filter(birth_month=today.month).order_by("birth_day"),
        "chart": stats.chart_bars(recent) if recent else None,
        "today": today,
    }
    return render(request, "registry/dashboard.html", context)


# ---------- branch ----------

@login_required
@require_POST
def branch_switch(request):
    branch = get_object_or_404(Branch, pk=request.POST.get("branch"))
    request.session[SESSION_KEY] = branch.pk
    # Stay in the same section, but not on a record page: that record belongs to the old branch.
    next_url = request.POST.get("next", "")
    if next_url.startswith("/") and not next_url.startswith("//"):
        try:
            name = resolve(next_url.split("?")[0]).url_name
        except Resolver404:
            name = None
        if name in ("member_list", "visitor_list", "service_open", "reports"):
            return redirect(name)
    return redirect("dashboard")


# ---------- members ----------

@login_required
def member_list(request):
    members = Member.objects.filter(branch=request.branch).select_related("ministry")
    q = request.GET.get("q", "").strip()
    if q:
        for word in q.split():
            members = members.filter(Q(first_name__icontains=word) | Q(last_name__icontains=word) | Q(phone__icontains=word)
                                     | Q(email__icontains=word) | Q(cell__icontains=word))
    if request.GET.get("ministry"):
        members = members.filter(ministry_id=request.GET["ministry"])
    if request.GET.get("status"):
        members = members.filter(status=request.GET["status"])
    last8 = list(Service.objects.filter(branch=request.branch).order_by("-date", "-service_type__order")[:8])
    rows = stats.member_rates(members, last8)
    return render(request, "registry/member_list.html", {
        "rows": rows, "q": q, "total": Member.objects.filter(branch=request.branch).count(), "ministries": Ministry.objects.all(),
        "statuses": Member.Status.choices, "selected_ministry": request.GET.get("ministry", ""),
        "selected_status": request.GET.get("status", ""),
    })


@login_required
def member_form(request, pk=None):
    member = get_object_or_404(Member, pk=pk, branch=request.branch) if pk else None
    visitor = None
    if not member and request.GET.get("from_visitor"):
        visitor = get_object_or_404(Visitor, pk=request.GET["from_visitor"], branch=request.branch)
    if request.method == "POST":
        form = MemberForm(request.POST, instance=member)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.branch = request.branch if not member else member.branch
            saved.save()
            if visitor:
                visitor.member = saved
                visitor.follow_up = Visitor.FollowUp.JOINED
                visitor.save()
            messages.success(request, f"{saved.full_name} {'updated' if member else 'registered'}.")
            return redirect("member_list")
    else:
        initial = {}
        if visitor:
            first, _, last = visitor.name.partition(" ")
            initial = {"first_name": first, "last_name": last, "phone": visitor.phone, "email": visitor.email,
                       "address": visitor.address, "notes": visitor.notes}
        form = MemberForm(instance=member, initial=initial)
    context = {"form": form, "member": member, "visitor": visitor}
    if member:
        all_services = list(Service.objects.filter(branch=request.branch))
        context["rate"] = stats.member_rates([member], all_services)[0]
        context["last_seen"] = member.last_seen()
        context["history"] = member.attendances.select_related("service__service_type").order_by("-service__date")[:10]
    return render(request, "registry/member_form.html", context)


@login_required
def member_delete(request, pk):
    member = get_object_or_404(Member, pk=pk, branch=request.branch)
    if request.method == "POST":
        member.delete()
        messages.success(request, f"{member.full_name} deleted.")
        return redirect("member_list")
    return render(request, "registry/confirm_delete.html", {"object": member, "kind": "member", "cancel": "member_edit", "pk": pk})


# ---------- visitors ----------

@login_required
def visitor_list(request):
    visitors = Visitor.objects.filter(branch=request.branch).select_related("member")
    q = request.GET.get("q", "").strip()
    if q:
        visitors = visitors.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q) | Q(invited_by__icontains=q))
    if request.GET.get("follow_up"):
        visitors = visitors.filter(follow_up=request.GET["follow_up"])
    visitors = visitors.annotate(visits=Count("attendances"))
    return render(request, "registry/visitor_list.html", {
        "visitors": visitors, "q": q, "total": Visitor.objects.filter(branch=request.branch).count(),
        "choices": Visitor.FollowUp.choices, "selected": request.GET.get("follow_up", ""),
    })


@login_required
def visitor_form(request, pk=None):
    visitor = get_object_or_404(Visitor, pk=pk, branch=request.branch) if pk else None
    service = None
    if not visitor and request.GET.get("service"):
        service = get_object_or_404(Service, pk=request.GET["service"], branch=request.branch)
    if request.method == "POST":
        form = VisitorForm(request.POST, instance=visitor, for_service=service)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.branch = request.branch if not visitor else visitor.branch
            saved.save()
            if service and form.cleaned_data.get("mark_present"):
                Attendance.objects.get_or_create(service=service, visitor=saved, defaults={"checked_in_by": request.user})
                messages.success(request, f"{saved.name} registered and checked in.")
                return redirect("checkin", pk=service.pk)
            messages.success(request, f"{saved.name} {'updated' if visitor else 'registered'}.")
            return redirect("checkin", pk=service.pk) if service else redirect("visitor_list")
    else:
        form = VisitorForm(instance=visitor, for_service=service)
    return render(request, "registry/visitor_form.html", {"form": form, "visitor": visitor, "service": service})


@login_required
@require_POST
def visitor_follow_up(request, pk):
    visitor = get_object_or_404(Visitor, pk=pk, branch=request.branch)
    if request.POST.get("follow_up") in Visitor.FollowUp.values:
        visitor.follow_up = request.POST["follow_up"]
        visitor.save(update_fields=["follow_up"])
        messages.success(request, f"Follow-up for {visitor.name} set to {visitor.get_follow_up_display()}.")
    next_url = request.POST.get("next", "")
    return redirect(next_url if next_url.startswith("/") and not next_url.startswith("//") else "visitor_list")


@login_required
def visitor_delete(request, pk):
    visitor = get_object_or_404(Visitor, pk=pk, branch=request.branch)
    if request.method == "POST":
        visitor.delete()
        messages.success(request, f"{visitor.name} deleted.")
        return redirect("visitor_list")
    return render(request, "registry/confirm_delete.html", {"object": visitor, "kind": "visitor", "cancel": "visitor_edit", "pk": pk})


# ---------- uploads ----------

def _import(request, imp, list_url):
    errors = []
    if request.method == "POST":
        upload = request.FILES.get("file")
        if not upload:
            errors = ["Choose a CSV file to upload."]
        elif upload.size > 5 * 1024 * 1024:
            errors = ["That file is larger than 5 MB. Split it into smaller files."]
        else:
            forms, skipped, errors = imp.read(upload, request.branch)
            if not errors and not forms and not skipped:
                errors = [f"The file has no {imp.noun} rows below the column names."]
            if not errors:
                with transaction.atomic():
                    for form in forms:
                        obj = form.save(commit=False)
                        obj.branch = request.branch
                        obj.save()
                msg = f"Imported {len(forms)} {imp.noun if len(forms) == 1 else imp.plural}."
                if skipped:
                    names = ", ".join(skipped[:10]) + (f" and {len(skipped) - 10} more" if len(skipped) > 10 else "")
                    msg += f" Skipped {len(skipped)} already in the register: {names}."
                messages.success(request, msg)
                return redirect(list_url)
    return render(request, "registry/import.html", {
        "errors": errors, "imp": imp, "guide": imp.guide(), "list_url": list_url,
        "template_url": f"{imp.noun}_import_template",
    })


@login_required
def member_import(request):
    return _import(request, importer.MEMBERS, "member_list")


@login_required
def visitor_import(request):
    return _import(request, importer.VISITORS, "visitor_list")


@login_required
def member_import_template(request):
    return _csv("members_template.csv", list(importer.MEMBERS.columns), [])


@login_required
def visitor_import_template(request):
    return _csv("visitors_template.csv", list(importer.VISITORS.columns), [])


# ---------- services & check-in ----------

@login_required
def service_open(request):
    form = OpenServiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        service, _ = Service.objects.get_or_create(branch=request.branch, date=form.cleaned_data["date"],
                                                   service_type=form.cleaned_data["service_type"])
        return redirect("checkin", pk=service.pk)
    services = Service.objects.filter(branch=request.branch)
    today_services = services.filter(date=timezone.localdate()).select_related("service_type")
    recent = stats.services_with_counts(services.order_by("-date", "-service_type__order")[:10])
    return render(request, "registry/service_open.html", {"form": form, "today_services": today_services, "recent": recent})


@login_required
def checkin(request, pk):
    service = get_object_or_404(Service.objects.select_related("service_type"), pk=pk, branch=request.branch)
    present_ids = set(service.attendances.filter(member__isnull=False).values_list("member_id", flat=True))
    members = Member.objects.filter(branch=request.branch).select_related("ministry").filter(
        Q(status=Member.Status.ACTIVE) | Q(id__in=present_ids))
    q = request.GET.get("q", "").strip()
    if q:
        for word in q.split():
            members = members.filter(Q(first_name__icontains=word) | Q(last_name__icontains=word)
                                     | Q(phone__icontains=word) | Q(cell__icontains=word))
    show = request.GET.get("show", "all")
    if show == "in":
        members = members.filter(id__in=present_ids)
    elif show == "out":
        members = members.exclude(id__in=present_ids)
    visitors = Visitor.objects.filter(attendances__service=service)
    return render(request, "registry/checkin.html", {
        "service": service, "members": members, "present_ids": present_ids, "visitors": visitors,
        "counts": service.counts(), "q": q, "show": show, "extra_form": ExtraHeadcountForm(instance=service),
        "has_members": Member.objects.filter(branch=request.branch).exists(),
    })


@login_required
@require_POST
def toggle_attendance(request, pk, member_id):
    service = get_object_or_404(Service, pk=pk, branch=request.branch)
    member = get_object_or_404(Member, pk=member_id, branch=request.branch)
    deleted, _ = Attendance.objects.filter(service=service, member=member).delete()
    if not deleted:
        try:
            Attendance.objects.create(service=service, member=member, checked_in_by=request.user)
        except IntegrityError:  # another usher checked them in at the same moment
            pass
    present = not deleted
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"present": present, "counts": service.counts()})
    next_url = request.POST.get("next", "")
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect("checkin", pk=pk)


@login_required
@require_POST
def remove_visitor_attendance(request, pk, visitor_id):
    Attendance.objects.filter(service_id=pk, service__branch=request.branch, visitor_id=visitor_id).delete()
    return redirect("checkin", pk=pk)


@login_required
@require_POST
def update_extra(request, pk):
    service = get_object_or_404(Service, pk=pk, branch=request.branch)
    form = ExtraHeadcountForm(request.POST, instance=service)
    if form.is_valid():
        form.save()
        messages.success(request, "Extra headcount updated.")
    return redirect("checkin", pk=pk)


@login_required
def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk, branch=request.branch)
    if request.method == "POST":
        service.delete()
        messages.success(request, f"{service} deleted.")
        return redirect("service_open")
    return render(request, "registry/confirm_delete.html", {"object": service, "kind": "service", "cancel": "checkin", "pk": pk})


# ---------- reports & exports ----------

def _date_range(request):
    today = timezone.localdate()
    form = DateRangeForm(request.GET or {"start": today - timedelta(days=90), "end": today})
    start, end = today - timedelta(days=90), today
    if form.is_valid():
        start = form.cleaned_data["start"] or start
        end = form.cleaned_data["end"] or end
    return form, start, end


@login_required
def reports(request):
    form, start, end = _date_range(request)
    services = stats.services_with_counts(Service.objects.filter(branch=request.branch, date__range=(start, end))
                                          .order_by("date", "service_type__order"))
    totals = [s.total for s in services]
    rates = stats.member_rates(Member.objects.filter(branch=request.branch, status=Member.Status.ACTIVE), services)
    rates.sort(key=lambda r: (r["pct"] is None, -(r["pct"] or 0), r["member"].full_name))
    return render(request, "registry/reports.html", {
        "form": form, "start": start, "end": end, "services": list(reversed(services)),
        "summary": {
            "services": len(services), "total": sum(totals),
            "average": round(sum(totals) / len(totals)) if totals else 0,
            "peak": max(totals) if totals else 0,
            "visitors": sum(s.n_visitors for s in services),
        },
        "rates": rates, "absent": stats.absence_streaks(request.branch),
    })


def _csv(filename, header, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")  # BOM so Excel opens UTF-8 names correctly
    writer = csv.writer(response)
    writer.writerow(header)
    for row in rows:
        # Prefix cells that spreadsheets would treat as formulas
        writer.writerow(["'" + c if isinstance(c, str) and c.startswith(("=", "+", "-", "@")) else c for c in row])
    return response


@login_required
def export_members(request):
    return _csv("members.csv", list(importer.MEMBERS.columns),
                ([m.first_name, m.last_name, m.get_gender_display(), m.birthday, m.phone, m.email, m.address,
                  m.cell, m.ministry or "", m.member_since, m.get_status_display(), m.notes]
                 for m in Member.objects.filter(branch=request.branch).select_related("ministry")))


@login_required
def export_visitors(request):
    return _csv("visitors.csv",
                ["Name", "Phone", "Email", "Address", "First visit", "Invited by", "Visits", "Follow-up", "Notes"],
                ([v.name, v.phone, v.email, v.address, v.first_visit, v.invited_by, v.visits, v.get_follow_up_display(), v.notes]
                 for v in Visitor.objects.filter(branch=request.branch).annotate(visits=Count("attendances"))))


@login_required
def export_attendance(request):
    _, start, end = _date_range(request)
    rows = []
    for a in Attendance.objects.filter(service__branch=request.branch, service__date__range=(start, end)).select_related(
            "service__service_type", "member", "visitor").order_by("service__date", "service__service_type__order"):
        person = a.member or a.visitor
        rows.append([a.service.date, a.service.service_type.name, str(person), "Member" if a.member else "Visitor",
                     timezone.localtime(a.checked_in_at).strftime("%H:%M")])
    for s in Service.objects.filter(branch=request.branch, date__range=(start, end), extra_headcount__gt=0).select_related("service_type"):
        rows.append([s.date, s.service_type.name, f"{s.extra_headcount} extra (not named)", "Headcount", ""])
    return _csv(f"attendance_{start}_{end}.csv", ["Date", "Service", "Name", "Type", "Checked in at"], rows)
