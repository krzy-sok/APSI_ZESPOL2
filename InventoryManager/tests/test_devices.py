from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from InventoryManager.models import (
    Category,
    Device,
    DeviceLease,
    DeviceLocation,
    DeviceRepair,
    Employee,
    ParameterModel,
)


class DeviceCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="inventory_user")
        cls.computer_category = Category.objects.create(name="Komputery")
        cls.gpu_category = Category.objects.create(name="Karty graficzne")
        cls.computer_category.allowed_sub_components.add(
            cls.gpu_category, cls.computer_category
        )
        cls.computer = Device.objects.create(
            name="Komputer biurowy", category=cls.computer_category
        )
        cls.gpu = Device.objects.create(name="Karta RTX", category=cls.gpu_category)

    def setUp(self):
        self.client.force_login(self.user)

    def update(self, device, **changes):
        return self.client.post(
            reverse("device_update", args=[device.pk]),
            {"name": device.name, "category": device.category_id, **changes},
        )

    def test_all_device_views_require_login(self):
        self.client.logout()
        urls = [
            reverse("device_list"),
            reverse("device_create"),
            reverse("device_detail", args=[self.computer.pk]),
            reverse("device_update", args=[self.computer.pk]),
            reverse("device_delete", args=[self.computer.pk]),
        ]
        for url in urls:
            for method in (self.client.get, self.client.post):
                with self.subTest(url=url, method=method.__name__):
                    self.assertRedirects(method(url), reverse("login") + f"?next={url}")
        self.assertEqual(Device.objects.count(), 2)

    def test_list_displays_names_categories_and_components(self):
        self.computer.components.add(self.gpu)
        response = self.client.get(reverse("device_list"))
        self.assertTemplateUsed(response, "devices/list.html")
        for text in (self.computer.name, self.gpu.name, self.computer_category.name):
            self.assertContains(response, text)
        self.assertContains(response, reverse("device_detail", args=[self.gpu.pk]))

    def test_empty_list_displays_message(self):
        Device.objects.all().delete()
        response = self.client.get(reverse("device_list"))
        self.assertContains(response, "Nie dodano jeszcze żadnych urządzeń.")

    def test_detail_displays_components_and_parent_devices(self):
        self.computer.components.add(self.gpu)
        response = self.client.get(reverse("device_detail", args=[self.computer.pk]))
        self.assertContains(response, self.gpu.name)
        response = self.client.get(reverse("device_detail", args=[self.gpu.pk]))
        self.assertEqual(list(response.context["parent_devices"]), [self.computer])
        self.assertContains(response, reverse("device_detail", args=[self.computer.pk]))

    def test_create_page_displays_category_and_component_choices(self):
        response = self.client.get(reverse("device_create"))
        self.assertTemplateUsed(response, "devices/form.html")
        self.assertContains(response, self.computer_category.name)
        self.assertContains(response, f"{self.gpu.name} — {self.gpu_category.name}")

    def test_create_saves_name_category_and_existing_component(self):
        response = self.client.post(
            reverse("device_create"),
            {
                "name": "  Nowy komputer  ",
                "category": self.computer_category.pk,
                "components": [self.gpu.pk],
            },
        )
        device = Device.objects.get(name="Nowy komputer")
        self.assertRedirects(response, reverse("device_detail", args=[device.pk]))
        self.assertEqual(device.category, self.computer_category)
        self.assertEqual(list(device.components.all()), [self.gpu])
        self.assertFalse(self.gpu.components.exists())

    def test_create_allows_device_without_components(self):
        response = self.client.post(
            reverse("device_create"),
            {"name": "Druga karta", "category": self.gpu_category.pk},
        )
        device = Device.objects.get(name="Druga karta")
        self.assertRedirects(response, reverse("device_detail", args=[device.pk]))
        self.assertFalse(device.components.exists())

    def test_invalid_create_does_not_save_device(self):
        for changes in (
            {"name": "   "},
            {"category": ""},
            {"category": 999999},
            {"components": [999999]},
        ):
            with self.subTest(changes=changes):
                response = self.client.post(
                    reverse("device_create"),
                    {
                        "name": "Nowy komputer",
                        "category": self.computer_category.pk,
                        **changes,
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(Device.objects.count(), 2)

    def test_disallowed_component_category_is_rejected_on_create(self):
        response = self.client.post(
            reverse("device_create"),
            {
                "name": "Druga karta",
                "category": self.gpu_category.pk,
                "components": [self.computer.pk],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("components", response.context["form"].errors)
        self.assertEqual(Device.objects.count(), 2)

    def test_update_prefills_fields_and_excludes_device_itself_from_choices(self):
        self.computer.components.add(self.gpu)
        response = self.client.get(reverse("device_update", args=[self.computer.pk]))
        form = response.context["form"]
        self.assertEqual(form.initial["name"], self.computer.name)
        self.assertEqual(list(form.initial["components"]), [self.gpu])
        self.assertFalse(
            form.fields["components"].queryset.filter(pk=self.computer.pk).exists()
        )

    def test_update_renames_and_attaches_component_without_recreating_device(self):
        response = self.update(
            self.computer, name="Zmieniona nazwa", components=[self.gpu.pk]
        )
        self.assertRedirects(
            response, reverse("device_detail", args=[self.computer.pk])
        )
        self.computer.refresh_from_db()
        self.assertEqual(self.computer.name, "Zmieniona nazwa")
        self.assertEqual(list(self.computer.components.all()), [self.gpu])
        self.assertEqual(Device.objects.count(), 2)

    def test_update_can_detach_component_without_deleting_it(self):
        self.computer.components.add(self.gpu)
        response = self.update(self.computer)
        self.assertRedirects(
            response, reverse("device_detail", args=[self.computer.pk])
        )
        self.assertFalse(self.computer.components.exists())
        self.assertTrue(Device.objects.filter(pk=self.gpu.pk).exists())

    def test_invalid_update_preserves_name_category_and_components(self):
        self.computer.components.add(self.gpu)
        response = self.update(self.computer, name="", category=self.gpu_category.pk)
        self.assertEqual(response.status_code, 200)
        self.computer.refresh_from_db()
        self.assertEqual(self.computer.name, "Komputer biurowy")
        self.assertEqual(self.computer.category, self.computer_category)
        self.assertEqual(list(self.computer.components.all()), [self.gpu])

    def test_update_rejects_category_incompatible_with_existing_parent(self):
        self.computer.components.add(self.gpu)
        category = Category.objects.create(name="Telefony")
        response = self.update(self.gpu, category=category.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn("category", response.context["form"].errors)
        self.gpu.refresh_from_db()
        self.assertEqual(self.gpu.category, self.gpu_category)

    def test_update_allows_category_compatible_with_existing_parent(self):
        self.computer.components.add(self.gpu)
        category = Category.objects.create(name="Karty rozszerzeń")
        self.computer_category.allowed_sub_components.add(category)
        response = self.update(self.gpu, category=category.pk)
        self.assertRedirects(response, reverse("device_detail", args=[self.gpu.pk]))
        self.gpu.refresh_from_db()
        self.assertEqual(self.gpu.category, category)

    def test_update_rejects_new_parent_category_incompatible_with_its_components(self):
        self.computer.components.add(self.gpu)
        category = Category.objects.create(name="Telefony")
        response = self.update(
            self.computer, category=category.pk, components=[self.gpu.pk]
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("components", response.context["form"].errors)
        self.computer.refresh_from_db()
        self.assertEqual(self.computer.category, self.computer_category)

    def test_device_cannot_be_its_own_component(self):
        response = self.update(self.computer, components=[self.computer.pk])
        self.assertEqual(response.status_code, 200)
        self.assertIn("components", response.context["form"].errors)
        self.assertFalse(self.computer.components.exists())

    def test_device_cannot_contain_an_ancestor(self):
        middle = Device.objects.create(name="Moduł", category=self.computer_category)
        leaf = Device.objects.create(name="Podmoduł", category=self.computer_category)
        self.computer.components.add(middle)
        middle.components.add(leaf)
        response = self.update(leaf, components=[self.computer.pk])
        self.assertEqual(response.status_code, 200)
        self.assertIn("components", response.context["form"].errors)
        self.assertFalse(leaf.components.exists())

    def test_nested_components_with_shared_descendant_are_allowed(self):
        module = Device.objects.create(name="Moduł", category=self.computer_category)
        module.components.add(self.gpu)
        response = self.update(self.computer, components=[module.pk, self.gpu.pk])
        self.assertRedirects(
            response, reverse("device_detail", args=[self.computer.pk])
        )
        self.assertEqual(set(self.computer.components.all()), {module, self.gpu})

    def test_delete_confirmation_does_not_delete_and_shows_parent(self):
        self.computer.components.add(self.gpu)
        response = self.client.get(reverse("device_delete", args=[self.gpu.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.computer.name)
        self.assertContains(response, "Potwierdź usunięcie")
        self.assertTrue(Device.objects.filter(pk=self.gpu.pk).exists())

    def test_delete_component_detaches_it_without_deleting_parent(self):
        self.computer.components.add(self.gpu)
        response = self.client.post(reverse("device_delete", args=[self.gpu.pk]))
        self.assertRedirects(response, reverse("device_list"))
        self.assertFalse(Device.objects.filter(pk=self.gpu.pk).exists())
        self.assertTrue(Device.objects.filter(pk=self.computer.pk).exists())
        self.assertFalse(self.computer.components.exists())

    def test_delete_parent_keeps_components_and_removes_its_related_records(self):
        self.computer.components.add(self.gpu)
        employee = Employee.objects.create(
            name="Jan Kowalski",
            hired_date=date(2026, 1, 1),
            department="IT",
            address_info="Warszawa",
        )
        lease = DeviceLease.objects.create(
            device=self.computer,
            owner=employee,
            lease_start=date(2026, 1, 1),
            lease_end=date(2026, 2, 1),
            description="Przydział",
            title="Przydział",
        )
        repair = DeviceRepair.objects.create(
            device=self.computer,
            repair_start=date(2026, 1, 1),
            repair_end=date(2026, 1, 2),
            description="Naprawa",
            title="Naprawa",
        )
        parameter = ParameterModel.objects.create(
            name="RAM",
            category=self.computer_category,
            unit="GB",
            value="16",
            device=self.computer,
            can_be_leased=False,
            can_be_repaired=False,
        )
        location = DeviceLocation.objects.create(device=self.computer, location="Biuro")
        confirmation = self.client.get(
            reverse("device_delete", args=[self.computer.pk])
        )
        self.assertEqual(
            confirmation.context["related_records"],
            {"Przydziały": 1, "Naprawy": 1, "Parametry": 1, "Lokalizacje": 1},
        )
        response = self.client.post(reverse("device_delete", args=[self.computer.pk]))
        self.assertRedirects(response, reverse("device_list"))
        self.assertFalse(Device.objects.filter(pk=self.computer.pk).exists())
        self.assertTrue(Device.objects.filter(pk=self.gpu.pk).exists())
        self.assertTrue(Employee.objects.filter(pk=employee.pk).exists())
        for record in (lease, repair, parameter, location):
            self.assertFalse(type(record).objects.filter(pk=record.pk).exists())

    def test_missing_device_returns_404(self):
        self.assertEqual(
            self.client.get(reverse("device_detail", args=[999999])).status_code, 404
        )
        for name in ("device_update", "device_delete"):
            for method in (self.client.get, self.client.post):
                with self.subTest(name=name, method=method.__name__):
                    self.assertEqual(
                        method(reverse(name, args=[999999])).status_code, 404
                    )

    def test_unsupported_methods_are_rejected(self):
        for url in (
            reverse("device_list"),
            reverse("device_detail", args=[self.computer.pk]),
        ):
            self.assertEqual(self.client.post(url).status_code, 405)
        for name, args in (
            ("device_create", []),
            ("device_update", [self.computer.pk]),
            ("device_delete", [self.computer.pk]),
        ):
            self.assertEqual(
                self.client.delete(reverse(name, args=args)).status_code, 405
            )

    def test_device_writes_require_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for name, args in (
            ("device_create", []),
            ("device_update", [self.computer.pk]),
            ("device_delete", [self.computer.pk]),
        ):
            self.assertEqual(
                client.post(
                    reverse(name, args=args), {"name": "Nowa nazwa"}
                ).status_code,
                403,
            )
        self.computer.refresh_from_db()
        self.assertEqual(self.computer.name, "Komputer biurowy")
        self.assertEqual(Device.objects.count(), 2)
        client.get(reverse("device_create"))
        response = client.post(
            reverse("device_create"),
            {
                "name": "Nowy komputer",
                "category": self.computer_category.pk,
                "csrfmiddlewaretoken": client.cookies[settings.CSRF_COOKIE_NAME].value,
            },
        )
        device = Device.objects.get(name="Nowy komputer")
        self.assertRedirects(response, reverse("device_detail", args=[device.pk]))

    def test_category_edit_cannot_disallow_components_already_in_use(self):
        self.computer.components.add(self.gpu)
        response = self.client.post(
            reverse("category_update", args=[self.computer_category.pk]),
            {"name": "Komputery"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("allowed_sub_components", response.context["form"].errors)
        self.assertTrue(
            self.computer_category.allowed_sub_components.filter(
                pk=self.gpu_category.pk
            ).exists()
        )

    def test_category_edit_can_disallow_component_category_after_detachment(self):
        self.computer.components.add(self.gpu)
        self.computer.components.clear()
        response = self.client.post(
            reverse("category_update", args=[self.computer_category.pk]),
            {"name": "Komputery"},
        )
        self.assertRedirects(response, reverse("category_list"))
        self.assertFalse(self.computer_category.allowed_sub_components.exists())
