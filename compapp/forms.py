from django import forms


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultiFileInput(attrs={"multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        return single_file_clean(data, initial)


class ImageUploadForm(forms.Form):
    FORMAT_CHOICES = [
        ("JPEG", "JPEG"),
        ("PNG", "PNG"),
        ("WEBP", "WebP"),
    ]

    images = MultiFileField(
        widget=MultiFileInput(
            attrs={"multiple": True, "class": "form-control", "accept": "image/*"}
        )
    )
    quality = forms.IntegerField(
        min_value=10,
        max_value=95,
        initial=70,
        widget=forms.NumberInput(attrs={"class": "form-range", "type": "range"}),
    )
    max_width = forms.IntegerField(
        min_value=100,
        max_value=8000,
        initial=1920,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    output_format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        initial="JPEG",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    remove_background = forms.BooleanField(
        required=False,
        initial=False,
        label="Remove background",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )