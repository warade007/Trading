from django.db import models
from django.db.models import F, Q


class Instrument(models.Model):
    exchange = models.CharField(max_length=16)
    symbol = models.CharField(max_length=64)
    kind = models.CharField(max_length=16, choices=[(x, x) for x in ("EQUITY", "ETF", "INDEX", "FUTURE", "OPTION")])
    source_kind = models.CharField(max_length=16, choices=[("SYNTHETIC", "Synthetic"), ("USER_SUPPLIED", "User supplied")])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["exchange", "symbol", "source_kind"], name="instrument_source_identity")]

    def __str__(self):
        return f"{self.exchange}:{self.symbol} ({self.source_kind})"


class InstrumentSnapshot(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT)
    as_of = models.DateField()
    token = models.CharField(max_length=64, blank=True)
    underlying = models.CharField(max_length=64, blank=True)
    expiry = models.DateField(null=True, blank=True)
    strike = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    option_type = models.CharField(max_length=2, blank=True)
    lot_size = models.PositiveIntegerField()
    tick_size = models.DecimalField(max_digits=14, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["instrument", "as_of"], name="dated_instrument_snapshot"),
            models.CheckConstraint(condition=Q(lot_size__gt=0) & Q(tick_size__gt=0), name="positive_contract_units"),
        ]


class DataIngestJob(models.Model):
    fingerprint = models.CharField(max_length=64, unique=True)
    csv_sha256 = models.CharField(max_length=64)
    manifest_sha256 = models.CharField(max_length=64)
    manifest = models.JSONField(default=dict)
    label = models.CharField(max_length=200)
    source_kind = models.CharField(max_length=16)
    source_reference = models.CharField(max_length=200)
    engine_version = models.CharField(max_length=32)
    imported_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.ForeignKey(InstrumentSnapshot, null=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=[("ACCEPTED", "Accepted"), ("REJECTED", "Rejected")])
    expected_minutes = models.PositiveIntegerField(default=0)
    imported_minutes = models.PositiveIntegerField(default=0)

    @property
    def coverage(self):
        return round(100 * self.imported_minutes / self.expected_minutes, 2) if self.expected_minutes else 0


class Candle(models.Model):
    # Data from separate manifests/sources is intentionally never merged.
    dataset = models.ForeignKey(DataIngestJob, on_delete=models.PROTECT, related_name="candles")
    timestamp = models.DateTimeField(help_text="Bar open in UTC")
    available_at = models.DateTimeField(help_text="Bar close in UTC; earliest strategy availability")
    interval = models.PositiveSmallIntegerField(choices=[(1, "1m"), (5, "5m"), (15, "15m")])
    open = models.DecimalField(max_digits=14, decimal_places=4)
    high = models.DecimalField(max_digits=14, decimal_places=4)
    low = models.DecimalField(max_digits=14, decimal_places=4)
    close = models.DecimalField(max_digits=14, decimal_places=4)
    volume = models.PositiveBigIntegerField(null=True, help_text="NULL for non-traded index reference values")

    class Meta:
        ordering = ["timestamp"]
        constraints = [
            models.UniqueConstraint(fields=["dataset", "interval", "timestamp"], name="unique_dataset_bar"),
            models.CheckConstraint(condition=Q(interval__in=[1, 5, 15]), name="supported_bar_interval"),
            models.CheckConstraint(condition=Q(low__gt=0) & Q(low__lte=F("open")) & Q(low__lte=F("close")) & Q(high__gte=F("open")) & Q(high__gte=F("close")), name="valid_bar_prices"),
            models.CheckConstraint(condition=Q(available_at__gt=F("timestamp")), name="bar_available_after_open"),
        ]


class DataQualityIssue(models.Model):
    dataset = models.ForeignKey(DataIngestJob, on_delete=models.PROTECT, related_name="issues")
    code = models.CharField(max_length=32)
    severity = models.CharField(max_length=8)
    row = models.PositiveIntegerField(null=True)
    message = models.TextField()
