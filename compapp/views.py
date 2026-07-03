import io
import zipfile
from pathlib import Path

from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from PIL import Image, ImageOps

from .forms import ImageUploadForm
from .models import UploadBatch, UploadedImage

FORMAT_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}

# rembg loads its ONNX model lazily and it's fairly heavy to import,
# so only import it if/when someone actually uses the feature.
_bg_session = None


class BackgroundRemovalUnavailable(Exception):
    pass


def _get_bg_session():
    global _bg_session
    if _bg_session is None:
        try:
            from rembg import new_session
        except (ImportError, ModuleNotFoundError, SystemExit) as exc:
            raise BackgroundRemovalUnavailable(
                "Background removal requires rembg with an ONNX runtime backend. "
                "Install it with pip install 'rembg[cpu]' or disable Remove background."
            ) from exc

        # "u2netp" is the lightweight model (~4MB) - faster, slightly
        # less precise than the default "u2net" (~176MB). Swap as needed.
        _bg_session = new_session("u2netp")
    return _bg_session


def strip_background(img):
    """
    Runs the image through rembg to remove its background.
    Returns an RGBA Pillow image with the background made transparent.
    """
    try:
        from rembg import remove
    except (ImportError, ModuleNotFoundError, SystemExit) as exc:
        raise BackgroundRemovalUnavailable(
            "Background removal requires rembg with an ONNX runtime backend. "
            "Install it with pip install 'rembg[cpu]' or disable Remove background."
        ) from exc

    session = _get_bg_session()
    return remove(img, session=session)


def compress_image(uploaded_file, quality, max_width, output_format, remove_bg=False):
    """
    Opens an uploaded image with Pillow, optionally strips its background,
    resizes it (if wider than max_width), converts it to the target format,
    and returns an in-memory buffer.
    """
    img = Image.open(uploaded_file)

    # Respect EXIF orientation before any processing
    img = ImageOps.exif_transpose(img)

    if remove_bg:
        img = strip_background(img)
        # Background removal produces transparency, so the output format
        # must support alpha - fall back to PNG if JPEG was requested.
        if output_format == "JPEG":
            output_format = "PNG"

    # Flatten transparency for formats that don't support alpha
    if output_format == "JPEG" and img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode == "P":
        img = img.convert("RGBA" if output_format in ("PNG", "WEBP") else "RGB")

    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    buffer = io.BytesIO()
    save_kwargs = {"format": output_format, "optimize": True}
    if output_format in ("JPEG", "WEBP"):
        save_kwargs["quality"] = quality
    img.save(buffer, **save_kwargs)
    buffer.seek(0)
    return buffer, img.width, img.height, output_format


def home(request):
    if request.method == "POST":
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            quality = form.cleaned_data["quality"]
            max_width = form.cleaned_data["max_width"]
            output_format = form.cleaned_data["output_format"]
            remove_bg = form.cleaned_data["remove_background"]
            files = request.FILES.getlist("images")

            if not files:
                form.add_error("images", "Please select at least one image.")
            else:
                batch = UploadBatch.objects.create(
                    quality=quality,
                    max_width=max_width,
                    output_format=output_format,
                    remove_background=remove_bg,
                )

                for f in files:
                    original_size = f.size
                    try:
                        buffer, width, height, actual_format = compress_image(
                            f, quality, max_width, output_format, remove_bg=remove_bg
                        )
                    except BackgroundRemovalUnavailable as exc:
                        form.add_error(
                            "remove_background",
                            str(exc),
                        )
                        break
                    except Exception:
                        # Skip files Pillow/rembg can't process (corrupt / unsupported)
                        continue

                    ext = FORMAT_EXTENSIONS.get(actual_format, "jpg")
                    base_name = Path(f.name).stem
                    compressed_name = f"{base_name}.{ext}"

                    image_obj = UploadedImage(
                        batch=batch,
                        original_name=f.name,
                        original_size=original_size,
                        compressed_size=buffer.getbuffer().nbytes,
                        width=width,
                        height=height,
                    )
                    image_obj.original_file.save(f.name, f, save=False)
                    image_obj.compressed_file.save(
                        compressed_name, ContentFile(buffer.read()), save=False
                    )
                    image_obj.save()

                if batch.images.exists():
                    return redirect("results", batch_id=batch.id)
                form.add_error(
                    "images", "None of the uploaded files could be processed."
                )
    else:
        form = ImageUploadForm()

    return render(request, "compapp/home.html", {"form": form})


def results_view(request, batch_id):
    batch = get_object_or_404(UploadBatch, id=batch_id)
    return render(request, "compapp/results.html", {"batch": batch})


def download_single(request, image_id):
    image_obj = get_object_or_404(UploadedImage, id=image_id)
    if not image_obj.compressed_file:
        raise Http404("Compressed file not found.")
    return FileResponse(
        image_obj.compressed_file.open("rb"),
        as_attachment=True,
        filename=image_obj.compressed_filename(),
    )


def download_zip(request, batch_id):
    batch = get_object_or_404(UploadBatch, id=batch_id)
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for image_obj in batch.images.all():
            if image_obj.compressed_file:
                zip_file.writestr(
                    image_obj.compressed_filename(),
                    image_obj.compressed_file.read(),
                )

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="compressed_{batch.id}.zip"'
    return response