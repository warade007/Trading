from decimal import Decimal

from django.db.models import Count
from django.shortcuts import render
from django.views.decorators.http import require_safe

from research.models import DataIngestJob


@require_safe
def dashboard(request):
    jobs = DataIngestJob.objects.select_related("snapshot__instrument").order_by("-imported_at")
    selected = request.GET.get("dataset", "")
    job = jobs.filter(pk=int(selected)).first() if selected.isascii() and selected.isdecimal() and len(selected) < 12 else jobs.first()
    bars, glyphs, counts, issues = [], [], [], []
    chart_min = chart_max = None
    if job:
        counts = list(job.candles.values("interval").annotate(total=Count("id")).order_by("interval"))
        bars = list(job.candles.filter(interval=5).order_by("-timestamp")[:75])[::-1]
        issues = list(job.issues.order_by("id")[:100])
    if bars:
        chart_min, chart_max = min(b.low for b in bars), max(b.high for b in bars)
        span = chart_max - chart_min or Decimal(1)

        def y(value):
            return round(20 + float((chart_max - value) / span) * 180, 2)

        for index, bar in enumerate(bars):
            opening, closing = y(bar.open), y(bar.close)
            x = round(20 + index * 760 / max(len(bars) - 1, 1), 2)
            glyphs.append({"x": x, "left": x - 2,
                           "high": y(bar.high), "low": y(bar.low),
                           "top": min(opening, closing), "height": max(1, abs(opening - closing)),
                           "color": "#67d8bd" if bar.close >= bar.open else "#f69e9e"})
    return render(request, "research/dashboard.html", {
        "jobs": jobs[:30], "job": job, "counts": counts, "issues": issues,
        "issue_count": job.issues.count() if job else 0,
        "glyphs": glyphs, "chart_min": chart_min, "chart_max": chart_max,
        "first_bar": bars[0] if bars else None, "last_bar": bars[-1] if bars else None,
        "recent": list(job.candles.filter(interval=1).order_by("-timestamp")[:10]) if job else [],
    })
