from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from InventoryManager.models import Category, Device, ParameterModel


class CategoryCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="inventory_user")
        cls.category = Category.objects.create(name="Komputery")
        cls.component = Category.objects.create(name="Karty graficzne")

    def setUp(self):
        self.client.force_login(self.user)

    def test_all_category_views_require_login(self):
        self.client.logout()
        urls = [
            reverse("category_list"),
            reverse("category_create"),
            reverse("category_update", args=[self.category.pk]),
            reverse("category_delete", args=[self.category.pk]),
        ]
        for url in urls:
            for method in (self.client.get, self.client.post):
                with self.subTest(url=url, method=method.__name__):
                    response = method(url)
                    self.assertRedirects(response, reverse("login") + f"?next={url}")
        self.assertEqual(Category.objects.count(), 2)

    def test_list_displays_categories_and_allowed_components(self):
        self.category.allowed_sub_components.add(self.component)
        response = self.client.get(reverse("category_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "categories/list.html")
        self.assertContains(response, self.category.name)
        self.assertContains(response, self.component.name)
        self.assertContains(
            response, reverse("category_update", args=[self.category.pk])
        )

    def test_empty_list_displays_message(self):
        Category.objects.all().delete()
        response = self.client.get(reverse("category_list"))
        self.assertContains(response, "Nie dodano jeszcze żadnych kategorii.")

    def test_create_page_displays_existing_component_choices(self):
        response = self.client.get(reverse("category_create"))
        self.assertTemplateUsed(response, "categories/form.html")
        self.assertContains(response, self.component.name)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_create_saves_name_and_directional_component_relationship(self):
        response = self.client.post(
            reverse("category_create"),
            {
                "name": "  Stacje robocze  ",
                "allowed_sub_components": [self.component.pk],
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("category_list"))
        category = Category.objects.get(name="Stacje robocze")
        self.assertEqual(list(category.allowed_sub_components.all()), [self.component])
        self.assertFalse(
            self.component.allowed_sub_components.filter(pk=category.pk).exists()
        )
        self.assertContains(response, "Dodano kategorię")

    def test_create_allows_no_components(self):
        response = self.client.post(reverse("category_create"), {"name": "Monitory"})
        self.assertRedirects(response, reverse("category_list"))
        self.assertFalse(
            Category.objects.get(name="Monitory").allowed_sub_components.exists()
        )

    def test_invalid_create_does_not_save_category(self):
        for data in (
            {"name": "   "},
            {"name": "Monitory", "allowed_sub_components": [999999]},
        ):
            with self.subTest(data=data):
                response = self.client.post(reverse("category_create"), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(Category.objects.count(), 2)

    def test_update_page_prefills_name_and_components(self):
        self.category.allowed_sub_components.add(self.component)
        response = self.client.get(reverse("category_update", args=[self.category.pk]))
        self.assertEqual(response.context["form"].initial["name"], self.category.name)
        self.assertEqual(
            list(response.context["form"].initial["allowed_sub_components"]),
            [self.component],
        )

    def test_update_renames_existing_category_and_updates_components(self):
        device = Device.objects.create(name="Komputer biurowy", category=self.category)
        response = self.client.post(
            reverse("category_update", args=[self.category.pk]),
            {"name": "Stacje robocze", "allowed_sub_components": [self.component.pk]},
        )
        self.assertRedirects(response, reverse("category_list"))
        self.category.refresh_from_db()
        device.refresh_from_db()
        self.assertEqual(self.category.name, "Stacje robocze")
        self.assertEqual(
            list(self.category.allowed_sub_components.all()), [self.component]
        )
        self.assertEqual(device.category_id, self.category.pk)
        self.assertEqual(Category.objects.count(), 2)

    def test_update_can_clear_allowed_components(self):
        self.category.allowed_sub_components.add(self.component)
        response = self.client.post(
            reverse("category_update", args=[self.category.pk]), {"name": "Komputery"}
        )
        self.assertRedirects(response, reverse("category_list"))
        self.assertFalse(self.category.allowed_sub_components.exists())

    def test_invalid_update_preserves_name_and_components(self):
        self.category.allowed_sub_components.add(self.component)
        response = self.client.post(
            reverse("category_update", args=[self.category.pk]), {"name": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Komputery")
        self.assertEqual(
            list(self.category.allowed_sub_components.all()), [self.component]
        )

    def test_delete_confirmation_does_not_delete_and_shows_parent_categories(self):
        self.category.allowed_sub_components.add(self.component)
        response = self.client.get(reverse("category_delete", args=[self.component.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Potwierdź usunięcie")
        self.assertContains(response, self.category.name)
        self.assertTrue(Category.objects.filter(pk=self.component.pk).exists())
        self.assertTrue(self.category.allowed_sub_components.exists())

    def test_post_deletes_unused_category_and_clears_incoming_component_links(self):
        self.category.allowed_sub_components.add(self.component)
        response = self.client.post(
            reverse("category_delete", args=[self.component.pk]), follow=True
        )
        self.assertRedirects(response, reverse("category_list"))
        self.assertFalse(Category.objects.filter(pk=self.component.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        self.assertFalse(self.category.allowed_sub_components.exists())
        self.assertContains(response, "Usunięto kategorię")

    def test_delete_rechecks_device_usage_after_confirmation(self):
        url = reverse("category_delete", args=[self.category.pk])
        self.client.get(url)
        device = Device.objects.create(name="Komputer biurowy", category=self.category)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "Nie można usunąć kategorii", status_code=409)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        self.assertTrue(Device.objects.filter(pk=device.pk).exists())

    def test_delete_blocks_categories_used_by_parameters(self):
        device = Device.objects.create(name="Komputer biurowy", category=self.category)
        parameter = ParameterModel.objects.create(
            name="Pamięć",
            category=self.component,
            unit="GB",
            value="16",
            device=device,
            can_be_leased=False,
            can_be_repaired=False,
        )
        url = reverse("category_delete", args=[self.component.pk])
        page = self.client.get(url)
        self.assertContains(page, "Nie można usunąć kategorii")
        self.assertNotContains(page, "Potwierdź usunięcie")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Category.objects.filter(pk=self.component.pk).exists())
        self.assertTrue(ParameterModel.objects.filter(pk=parameter.pk).exists())

    def test_missing_category_returns_404(self):
        for name in ("category_update", "category_delete"):
            for method in (self.client.get, self.client.post):
                with self.subTest(name=name, method=method.__name__):
                    response = method(reverse(name, args=[999999]))
                    self.assertEqual(response.status_code, 404)

    def test_unsupported_methods_are_rejected(self):
        self.assertEqual(self.client.post(reverse("category_list")).status_code, 405)
        for name, args in (
            ("category_create", []),
            ("category_update", [self.category.pk]),
            ("category_delete", [self.category.pk]),
        ):
            with self.subTest(name=name):
                response = self.client.delete(reverse(name, args=args))
                self.assertEqual(response.status_code, 405)

    def test_category_writes_require_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for name, args in (
            ("category_create", []),
            ("category_update", [self.category.pk]),
            ("category_delete", [self.category.pk]),
        ):
            with self.subTest(name=name):
                response = client.post(reverse(name, args=args), {"name": "Nowa nazwa"})
                self.assertEqual(response.status_code, 403)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Komputery")
        self.assertEqual(Category.objects.count(), 2)
        client.get(reverse("category_create"))
        response = client.post(
            reverse("category_create"),
            {
                "name": "Monitory",
                "csrfmiddlewaretoken": client.cookies[settings.CSRF_COOKIE_NAME].value,
            },
        )
        self.assertRedirects(response, reverse("category_list"))
        self.assertTrue(Category.objects.filter(name="Monitory").exists())
