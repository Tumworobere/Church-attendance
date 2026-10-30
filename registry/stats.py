"""Attendance calculations shared by the dashboard and reports."""
from collections import defaultdict

from django.db.models import Count, Q

from .models import Attendance, Member, Service


def services_with_counts(qs=None):
    """Annotate services with member/visitor counts and compute the total."""
    qs = (qs if qs is not None else Service.objects.all()).select_related("service_type").annotate(
        n_members=Count("attendances", filter=Q(attendances__member__isnull=False)),
        n_visitors=Count("attendances", filter=Q(attendances__visitor__isnull=False)),
    )
    services = list(qs)
    for s in services:
        s.total = s.n_members + s.n_visitors + s.extra_headcount
    return services


def chart_bars(services, width=680, height=240):
    """Stacked bar geometry for an inline SVG, oldest service first."""
    left, right, top, bottom = 40, 10, 14, 34
    inner_w, inner_h = width - left - right, height - top - bottom
    peak = max([s.total for s in services] + [1])
    step = next((n for n in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000) if peak / n <= 5), -(-peak // 5))
    ceiling = -(-peak // step) * step

    def y(v):
        return top + inner_h - v / ceiling * inner_h

    slot = inner_w / max(len(services), 1)
    bar_w = min(40, slot * 0.62)
    bars = []
    for i, s in enumerate(services):
        cx = left + slot * (i + 0.5)
        segments, base = [], 0
        for value, css in ((s.n_members, "members"), (s.n_visitors, "visitors"), (s.extra_headcount, "extra")):
            if value:
                segments.append({"y": y(base + value), "h": y(base) - y(base + value), "css": css, "value": value})
                base += value
        bars.append({"x": cx - bar_w / 2, "cx": cx, "w": bar_w, "segments": segments,
                     "label_y": y(s.total) - 5, "total": s.total, "date": s.date})
    ticks = [{"value": v, "y": y(v)} for v in range(0, ceiling + 1, step)]
    return {"bars": bars, "ticks": ticks, "width": width, "height": height,
            "left": left, "right_x": width - right, "date_y": height - 12}


def member_rates(members, services):
    """Attendance count/rate per member over the given services (only those after they joined)."""
    service_ids = [s.id for s in services]
    attended = defaultdict(set)
    for member_id, service_id in Attendance.objects.filter(
        service_id__in=service_ids, member__isnull=False
    ).values_list("member_id", "service_id"):
        attended[member_id].add(service_id)
    rows = []
    for m in members:
        eligible = [s for s in services if s.date >= m.member_since]
        n = sum(1 for s in eligible if s.id in attended[m.id])
        pct = round(n / len(eligible) * 100) if eligible else None
        rows.append({"member": m, "attended": n, "of": len(eligible), "pct": pct})
    return rows


def absence_streaks(min_missed=3):
    """Active members who missed the most recent `min_missed`+ services in a row."""
    services = list(Service.objects.order_by("-date", "-service_type__order").values_list("id", "date"))
    present = defaultdict(set)
    for member_id, service_id in Attendance.objects.filter(member__isnull=False).values_list("member_id", "service_id"):
        present[member_id].add(service_id)
    results = []
    for m in Member.objects.filter(status=Member.Status.ACTIVE):
        missed = 0
        for service_id, date in services:
            if date < m.member_since or service_id in present[m.id]:
                break
            missed += 1
        if missed >= min_missed:
            results.append({"member": m, "missed": missed})
    return sorted(results, key=lambda r: -r["missed"])
