import os
import uuid

from django.db import models


def original_upload_path(instance, filename):
    return f"originals/{uuid.uuid4().hex}_{filename}"


def compressed_upload_path(instance, filename):
    return f"compressed/{uuid.uuid4().hex}_{filename}"


class UploadBatch(models.Model):
    """Groups images uploaded together in a single request (for ZIP download)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    quality = models.PositiveSmallIntegerField(default=70)
    max_width = models.PositiveIntegerField(default=1920)
    output_format = models.CharField(max_length=10, default="JPEG")
    remove_background = models.BooleanField(default=False)

    def __str__(self):
        return f"Batch {self.id} ({self.created_at:%Y-%m-%d %H:%M})"

    @property
    def total_original_size(self):
        return sum(img.original_size for img in self.images.all())

    @property
    def total_compressed_size(self):
        return sum(img.compressed_size for img in self.images.all())

    @property
    def total_savings_percent(self):
        total_original = self.total_original_size
        if not total_original:
            return 0
        saved = total_original - self.total_compressed_size
        return round((saved / total_original) * 100, 1)


class UploadedImage(models.Model):
    batch = models.ForeignKey(
        UploadBatch, related_name="images", on_delete=models.CASCADE
    )
    original_file = models.ImageField(upload_to=original_upload_path)
    compressed_file = models.ImageField(
        upload_to=compressed_upload_path, blank=True, null=True
    )
    original_name = models.CharField(max_length=255)
    original_size = models.PositiveIntegerField(default=0)  # bytes
    compressed_size = models.PositiveIntegerField(default=0)  # bytes
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name

    @property
    def savings_percent(self):
        if not self.original_size:
            return 0
        saved = self.original_size - self.compressed_size
        return round((saved / self.original_size) * 100, 1)

    @property
    def original_size_kb(self):
        return round(self.original_size / 1024, 1)

    @property
    def compressed_size_kb(self):
        return round(self.compressed_size / 1024, 1)

    def compressed_filename(self):
        if self.compressed_file:
            return os.path.basename(self.compressed_file.name)
        return ""