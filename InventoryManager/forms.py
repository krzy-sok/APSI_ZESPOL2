from django import forms

from .models import Category, Device

PAGE_SIZE_CHOICES = [(size, str(size)) for size in (10, 25, 50, 100)]


class CategoryListForm(forms.Form):
    q = forms.CharField(label="Szukaj po nazwie", required=False, max_length=200)
    sort = forms.ChoiceField(
        label="Sortowanie",
        required=False,
        choices=[("name", "Nazwa A–Z"), ("-name", "Nazwa Z–A")],
    )
    components = forms.ChoiceField(
        label="Dozwolone kategorie komponentów",
        required=False,
        choices=[
            ("", "Wszystkie"),
            ("yes", "Z dozwolonymi kategoriami komponentów"),
            ("no", "Bez dozwolonych kategorii komponentów"),
        ],
    )
    per_page = forms.TypedChoiceField(
        label="Elementów na stronie",
        choices=PAGE_SIZE_CHOICES,
        coerce=int,
        required=False,
        empty_value=25,
        initial=25,
    )


class DeviceListForm(forms.Form):
    q = forms.CharField(label="Szukaj po nazwie", required=False, max_length=200)
    category = forms.ModelChoiceField(
        label="Kategoria",
        queryset=Category.objects.none(),
        required=False,
        empty_label="Wszystkie kategorie",
    )
    components = forms.ChoiceField(
        label="Komponenty",
        required=False,
        choices=[
            ("", "Wszystkie"),
            ("yes", "Z komponentami"),
            ("no", "Bez komponentów"),
        ],
    )
    sort = forms.ChoiceField(
        label="Sortowanie",
        required=False,
        choices=[
            ("name", "Nazwa A–Z"),
            ("-name", "Nazwa Z–A"),
            ("category", "Kategoria A–Z"),
            ("-category", "Kategoria Z–A"),
        ],
    )
    per_page = forms.TypedChoiceField(
        label="Elementów na stronie",
        choices=PAGE_SIZE_CHOICES,
        coerce=int,
        required=False,
        empty_value=25,
        initial=25,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.order_by("name", "pk")


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "allowed_sub_components"]
        labels = {
            "name": "Nazwa",
            "allowed_sub_components": "Dozwolone kategorie komponentów",
        }
        widgets = {
            "allowed_sub_components": forms.CheckboxSelectMultiple(),
        }

    def clean_allowed_sub_components(self):
        allowed = self.cleaned_data["allowed_sub_components"]
        if self.instance.pk:
            used_category_ids = set(
                Device.objects.filter(
                    category=self.instance, components__isnull=False
                ).values_list("components__category_id", flat=True)
            )
            if used_category_ids - set(allowed.values_list("pk", flat=True)):
                raise forms.ValidationError(
                    "Nie można wyłączyć kategorii komponentów używanych już "
                    "w urządzeniach. Najpierw odłącz te komponenty."
                )
        return allowed


class DeviceComponentChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.name} — {obj.category.name}"


class DeviceForm(forms.ModelForm):
    components = DeviceComponentChoiceField(
        queryset=Device.objects.none(),
        required=False,
        label="Komponenty",
        widget=forms.CheckboxSelectMultiple(),
        help_text=(
            "Najpierw dodaj komponent jako osobne urządzenie. "
            "Jego kategoria musi być dozwolona w kategorii tego urządzenia."
        ),
    )

    class Meta:
        model = Device
        fields = ["name", "category", "components"]
        labels = {"name": "Nazwa", "category": "Kategoria"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.order_by("name", "pk")
        components = Device.objects.select_related("category").order_by("name", "pk")
        if self.instance.pk:
            components = components.exclude(pk=self.instance.pk)
        self.fields["components"].queryset = components

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        components = cleaned_data.get("components")
        if category and components is not None:
            allowed_ids = set(
                category.allowed_sub_components.values_list("pk", flat=True)
            )
            invalid = [
                device.name
                for device in components
                if device.category_id not in allowed_ids
            ]
            if invalid:
                self.add_error(
                    "components",
                    "Niedozwolona kategoria komponentów: " + ", ".join(invalid) + ".",
                )

        if self.instance.pk:
            if category and category.pk != self.instance.category_id:
                parents = Device.objects.filter(
                    components=self.instance
                ).select_related("category")
                for parent in parents:
                    if not parent.category.allowed_sub_components.filter(
                        pk=category.pk
                    ).exists():
                        self.add_error(
                            "category",
                            f"Kategoria nie jest dozwolona dla urządzenia „{parent.name}”, "
                            "które zawiera ten komponent. Najpierw odłącz komponent.",
                        )
                        break

            if components is not None:
                # Follow existing component links to reject both direct and nested cycles.
                pending = {device.pk for device in components}
                visited = set()
                while pending:
                    if self.instance.pk in pending:
                        self.add_error(
                            "components",
                            "Urządzenie nie może zawierać siebie, także pośrednio.",
                        )
                        break
                    visited.update(pending)
                    descendants = Device.objects.filter(pk__in=pending).values_list(
                        "components__pk", flat=True
                    )
                    pending = {pk for pk in descendants if pk is not None} - visited
        return cleaned_data
