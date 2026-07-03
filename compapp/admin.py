from django.contrib import admin
from django.utils.html import format_html

from .models import UploadBatch, UploadedImage


class UploadedImageInline(admin.TabularInline):
    model = UploadedImage
    extra = 0
    readonly_fields = (
        "thumbnail",
        "original_name",
        "original_size_kb",
        "compressed_size_kb",
        "savings_percent",
        "width",
        "height",
        "created_at",
    )
    fields = (
        "thumbnail",
        "original_name",
        "original_size_kb",
        "compressed_size_kb",
        "savings_percent",
        "width",
        "height",
        "created_at",
    )
    can_delete = True

    def thumbnail(self, obj):
        if obj.compressed_file:
            return format_html(
                '<img src="{}" style="height:60px; border-radius:4px;" />',
                obj.compressed_file.url,
            )
        return "—"

    thumbnail.short_description = "Preview"


@admin.register(UploadBatch)
class UploadBatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "image_count",
        "output_format",
        "quality",
        "max_width",
        "total_original_size_kb",
        "total_compressed_size_kb",
        "total_savings_percent",
    )
    list_filter = ("output_format", "created_at")
    readonly_fields = (
        "id",
        "created_at",
        "total_original_size_kb",
        "total_compressed_size_kb",
        "total_savings_percent",
    )
    inlines = [UploadedImageInline]
    ordering = ("-created_at",)

    def image_count(self, obj):
        return obj.images.count()

    image_count.short_description = "Images"

    def total_original_size_kb(self, obj):
        return f"{round(obj.total_original_size / 1024, 1)} KB"

    total_original_size_kb.short_description = "Total original"

    def total_compressed_size_kb(self, obj):
        return f"{round(obj.total_compressed_size / 1024, 1)} KB"

    total_compressed_size_kb.short_description = "Total compressed"

    def total_savings_percent(self, obj):
        return f"{obj.total_savings_percent}%"

    total_savings_percent.short_description = "Savings"


@admin.register(UploadedImage)
class UploadedImageAdmin(admin.ModelAdmin):
    list_display = (
        "original_name",
        "batch",
        "thumbnail",
        "original_size_kb",
        "compressed_size_kb",
        "savings_percent",
        "width",
        "height",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("original_name",)
    readonly_fields = (
        "thumbnail",
        "original_size_kb",
        "compressed_size_kb",
        "savings_percent",
        "created_at",
    )
    ordering = ("-created_at",)

    def thumbnail(self, obj):
        if obj.compressed_file:
            return format_html(
                '<img src="{}" style="height:50px; border-radius:4px;" />',
                obj.compressed_file.url,
            )
        return "—"

    thumbnail.short_description = "Preview"