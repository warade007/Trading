from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from brokers.errors import BrokerError, MESSAGES
from brokers.views import administrator
from research.historical import eligible, fetch_history, latest_weekday, normal_sessions, read_master, sync_instruments
from research.models import HistoricalDownloadJob, InstrumentMasterSnapshot


class HistoricalForm(forms.Form):
    master_id = forms.IntegerField(widget=forms.HiddenInput)
    symbol = forms.ChoiceField(label="NSE instrument")
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, instruments=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["symbol"].choices = [(r["tradingsymbol"], r["tradingsymbol"]) for r in sorted(instruments, key=lambda item: item["tradingsymbol"])]

    def clean(self):
        values = super().clean()
        if "start_date" in values and "end_date" in values:
            try:
                normal_sessions(values["start_date"], values["end_date"])
            except BrokerError:
                raise forms.ValidationError("Choose a past date range of up to seven calendar days within the last 90 days, containing a weekday. Today is excluded.")
        return values


def page(request, *, bound=False):
    master = InstrumentMasterSnapshot.objects.order_by("-observed_at", "-id").first()
    if bound:
        try:
            master = InstrumentMasterSnapshot.objects.get(pk=int(request.POST.get("master_id", "")), exchange="NSE")
        except (ValueError, InstrumentMasterSnapshot.DoesNotExist):
            master = None
    instruments, error = [], ""
    if master:
        try:
            instruments = [r for r in read_master(master) if eligible(r)]
        except BrokerError as exc:
            error = str(exc)
    day = latest_weekday()
    form = HistoricalForm(request.POST if bound else None, instruments=instruments, initial={
        "master_id": master.pk if master else None, "symbol": "NIFTY 50", "start_date": day, "end_date": day,
    })
    return master, form, error


def render_page(request, master, form, error=""):
    jobs = list(HistoricalDownloadJob.objects.select_related("dataset").order_by("-created_at")[:30])
    for job in jobs:
        job.safe_error = MESSAGES.get(job.error_code, "")
    return render(request, "research/historical.html", {"master": master, "form": form, "catalog_error": error, "jobs": jobs})


@administrator
@require_GET
def historical_page(request):
    return render_page(request, *page(request))


@administrator
@require_POST
def sync_master(request):
    try:
        master, created = sync_instruments(request.user)
    except BrokerError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"NSE master saved: {master.instrument_count} records; {'new snapshot' if created else 'unchanged content'}.")
    return redirect("historical_data")


@administrator
@require_POST
def download_history(request):
    master, form, error = page(request, bound=True)
    if not master:
        messages.error(request, MESSAGES["CATALOG_REQUIRED"])
        return redirect("historical_data")
    if form.is_valid() and not error:
        try:
            job, created = fetch_history(master.pk, form.cleaned_data["symbol"], form.cleaned_data["start_date"], form.cleaned_data["end_date"], request.user)
        except BrokerError as exc:
            messages.error(request, str(exc))
        else:
            if job.status == "COMPLETE":
                messages.success(request, f"Dataset {job.dataset_id}: {job.dataset.imported_minutes}/{job.dataset.expected_minutes} 1m candles; complete 5m/15m bars derived. {'Downloaded' if created else 'Already stored; no new broker request'}.")
            else:
                messages.error(request, MESSAGES.get(job.error_code, MESSAGES["DATA_REJECTED"]))
            return redirect("historical_data")
    return render_page(request, master, form, error)
