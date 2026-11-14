from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from InventoryManager.models import Category, Device


class ListFilteringTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="inventory_user")
        cls.computers = Category.objects.create(name="Komputery")
        cls.cards = Category.objects.create(name="Karty")
        cls.phones = Category.objects.create(name="Telefony")
        cls.computers.allowed_sub_components.add(cls.cards, cls.phones)
        cls.desktop = Device.objects.create(
            name="alpha desktop", category=cls.computers
        )
        cls.laptop = Device.objects.create(name="Beta laptop", category=cls.computers)
        cls.card = Device.objects.create(name="Card gamma", category=cls.cards)
        cls.second_card = Device.objects.create(name="Card gamma 2", category=cls.cards)
        cls.phone = Device.objects.create(name="Delta phone", category=cls.phones)
        cls.desktop.components.add(cls.card, cls.second_card)

    def setUp(self):
        self.client.force_login(self.user)

    def test_category_search_matches_partial_name_ignoring_case_and_surrounding_spaces(
        self,
    ):
        response = self.client.get(reverse("category_list"), {"q": "  KOM  "})
        self.assertEqual(list(response.context["categories"]), [self.computers])
        self.assertEqual(response.context["page_obj"].paginator.count, 1)

    def test_device_search_matches_partial_name_ignoring_case_and_surrounding_spaces(
        self,
    ):
        response = self.client.get(reverse("device_list"), {"q": "  LAPTOP  "})
        self.assertEqual(list(response.context["devices"]), [self.laptop])

    def test_category_sorting_in_both_directions(self):
        for sort, expected in (
            ("name", [self.cards, self.computers, self.phones]),
            ("-name", [self.phones, self.computers, self.cards]),
        ):
            with self.subTest(sort=sort):
                response = self.client.get(reverse("category_list"), {"sort": sort})
                self.assertEqual(list(response.context["categories"]), expected)

    def test_device_sorting_by_name_and_category_in_both_directions(self):
        for sort, expected in (
            (
                "name",
                [self.desktop, self.laptop, self.card, self.second_card, self.phone],
            ),
            (
                "-name",
                [self.phone, self.second_card, self.card, self.laptop, self.desktop],
            ),
            (
                "category",
                [self.card, self.second_card, self.desktop, self.laptop, self.phone],
            ),
            (
                "-category",
                [self.phone, self.desktop, self.laptop, self.card, self.second_card],
            ),
        ):
            with self.subTest(sort=sort):
                response = self.client.get(reverse("device_list"), {"sort": sort})
                self.assertEqual(list(response.context["devices"]), expected)

    def test_sorting_duplicate_names_uses_stable_primary_key_order(self):
        duplicate = Device.objects.create(
            name=self.laptop.name, category=self.computers
        )
        for sort in ("name", "-name"):
            with self.subTest(sort=sort):
                response = self.client.get(
                    reverse("device_list"), {"q": "laptop", "sort": sort}
                )
                self.assertEqual(
                    list(response.context["devices"]), [self.laptop, duplicate]
                )

    def test_device_category_filter(self):
        response = self.client.get(reverse("device_list"), {"category": self.cards.pk})
        self.assertEqual(
            list(response.context["devices"]), [self.card, self.second_card]
        )

    def test_device_component_filter_returns_each_parent_only_once(self):
        response = self.client.get(reverse("device_list"), {"components": "yes"})
        self.assertEqual(list(response.context["devices"]), [self.desktop])
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        response = self.client.get(reverse("device_list"), {"components": "no"})
        self.assertEqual(
            list(response.context["devices"]),
            [self.laptop, self.card, self.second_card, self.phone],
        )

    def test_category_component_filter_returns_each_category_only_once(self):
        response = self.client.get(reverse("category_list"), {"components": "yes"})
        self.assertEqual(list(response.context["categories"]), [self.computers])
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        response = self.client.get(reverse("category_list"), {"components": "no"})
        self.assertEqual(
            list(response.context["categories"]), [self.cards, self.phones]
        )

    def test_device_search_filters_and_sorting_can_be_combined(self):
        response = self.client.get(
            reverse("device_list"),
            {
                "q": "a",
                "category": self.computers.pk,
                "components": "no",
                "sort": "-name",
            },
        )
        self.assertEqual(list(response.context["devices"]), [self.laptop])
        self.assertEqual(
            response.context["filter_form"].cleaned_data["category"], self.computers
        )

    def test_category_search_filter_and_sorting_can_be_combined(self):
        response = self.client.get(
            reverse("category_list"), {"q": "k", "components": "no", "sort": "-name"}
        )
        self.assertEqual(list(response.context["categories"]), [self.cards])

    def test_no_matches_displays_search_message_instead_of_empty_registry_message(self):
        for name, message in (
            ("device_list", "Brak urządzeń pasujących do podanych kryteriów."),
            ("category_list", "Brak kategorii pasujących do podanych kryteriów."),
        ):
            with self.subTest(name=name):
                response = self.client.get(reverse(name), {"q": "nieistniejąca nazwa"})
                self.assertContains(response, message)
                self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_invalid_filter_values_show_errors_without_exposing_unfiltered_results(
        self,
    ):
        for name in ("device_list", "category_list"):
            for params in (
                {"sort": "category__not_a_sort_field"},
                {"components": "invalid"},
                {"q": "x" * 201},
                {"per_page": "0"},
                {"per_page": "-10"},
                {"per_page": "999999"},
                {"per_page": "invalid"},
            ):
                with self.subTest(name=name, params=params):
                    response = self.client.get(reverse(name), params)
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.context["filter_form"].errors)
                    self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_invalid_or_missing_category_id_displays_validation_error(self):
        for category in ("not-an-id", "999999"):
            with self.subTest(category=category):
                response = self.client.get(
                    reverse("device_list"), {"category": category}
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("category", response.context["filter_form"].errors)
                self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_device_pagination_preserves_search_filters_sort_and_encoded_characters(
        self,
    ):
        query = "extra & +"
        Device.objects.bulk_create(
            [
                Device(name=f"{query} {number:02}", category=self.computers)
                for number in range(27)
            ]
        )
        filters = {
            "q": query,
            "category": self.computers.pk,
            "components": "no",
            "sort": "-name",
            "per_page": 10,
        }
        first = self.client.get(reverse("device_list"), filters)
        self.assertEqual(len(first.context["devices"]), 10)
        self.assertEqual(first.context["page_obj"].paginator.count, 27)
        self.assertContains(first, escape("?" + urlencode({**filters, "page": 2})))
        second = self.client.get(reverse("device_list"), {**filters, "page": 2})
        self.assertEqual(len(second.context["devices"]), 10)
        first_ids = {device.pk for device in first.context["devices"]}
        second_ids = {device.pk for device in second.context["devices"]}
        self.assertFalse(first_ids & second_ids)
        self.assertEqual(second.context["page_obj"].number, 2)
        self.assertContains(second, escape("?" + urlencode({**filters, "page": 1})))

    def test_category_pagination_preserves_filters_and_sort(self):
        Category.objects.bulk_create(
            [Category(name=f"Extra {number:02}") for number in range(27)]
        )
        filters = {"q": "Extra", "components": "no", "sort": "-name", "per_page": 10}
        first = self.client.get(reverse("category_list"), filters)
        self.assertEqual(len(first.context["categories"]), 10)
        self.assertEqual(first.context["page_obj"].paginator.count, 27)
        self.assertContains(first, escape("?" + urlencode({**filters, "page": 2})))
        second = self.client.get(reverse("category_list"), {**filters, "page": 2})
        self.assertEqual(len(second.context["categories"]), 10)
        self.assertEqual(second.context["page_obj"].number, 2)

    def test_invalid_page_numbers_do_not_cause_server_errors(self):
        for name in ("device_list", "category_list"):
            for page in ("not-a-number", "-1", "999999"):
                with self.subTest(name=name, page=page):
                    response = self.client.get(reverse(name), {"page": page})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.context["page_obj"].number, 1)

    def test_search_treats_sql_wildcards_as_literal_characters(self):
        special = Device.objects.create(
            name="Monitor 100%_test", category=self.computers
        )
        response = self.client.get(reverse("device_list"), {"q": "%_"})
        self.assertEqual(list(response.context["devices"]), [special])

    def test_page_size_choices_limit_both_lists_and_default_to_25(self):
        Category.objects.bulk_create(
            [Category(name=f"Sized {number:03}") for number in range(105)]
        )
        Device.objects.bulk_create(
            [
                Device(name=f"Sized {number:03}", category=self.computers)
                for number in range(105)
            ]
        )
        for name in ("device_list", "category_list"):
            for size in (None, 10, 25, 50, 100):
                with self.subTest(name=name, size=size):
                    params = {"q": "Sized"}
                    if size is not None:
                        params["per_page"] = size
                    response = self.client.get(reverse(name), params)
                    page = response.context["page_obj"]
                    self.assertEqual(len(page), size or 25)
                    self.assertEqual(page.paginator.count, 105)
                    self.assertFalse(response.context["filter_form"].errors)
