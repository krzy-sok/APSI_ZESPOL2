from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.sessions.models import Session
from django.test import Client, TestCase
from django.urls import reverse


class SessionAuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Inventory-demo-password-42!"
        cls.user = get_user_model().objects.create_user(
            username="inventory_user", password=cls.password
        )

    def login(self, **extra_data):
        return self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": self.password, **extra_data},
        )

    def test_anonymous_home_request_redirects_to_login(self):
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, reverse("login") + "?next=/")

    def test_login_page_contains_form_and_csrf_token(self):
        response = self.client.get(reverse("login"))
        self.assertTemplateUsed(response, "login.html")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_login_creates_database_session_and_authenticates_next_request(self):
        response = self.login()
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))
        self.assertTrue(
            Session.objects.filter(session_key=self.client.session.session_key).exists()
        )
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        page = self.client.get(reverse("home"))
        self.assertEqual(page.context["user"], self.user)
        self.assertContains(page, self.user.username)

    def test_invalid_credentials_show_errors_without_creating_auth_session(self):
        response = self.login(password="incorrect-password")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_login_preserves_local_next_destination(self):
        response = self.login(next="/?view=inventory")
        self.assertRedirects(response, "/?view=inventory")

    def test_login_rejects_external_next_destination(self):
        response = self.login(next="https://example.org/")
        self.assertRedirects(response, reverse("home"))

    def test_authenticated_user_is_redirected_away_from_login_and_registration(self):
        self.client.force_login(self.user)
        for name in ("login", "register"):
            with self.subTest(name=name):
                self.assertRedirects(self.client.get(reverse(name)), reverse("home"))

    def test_registration_creates_regular_user_and_redirects_to_login(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "new_employee",
                "password1": self.password,
                "password2": self.password,
            },
        )
        self.assertRedirects(response, reverse("login"))
        user = get_user_model().objects.get(username="new_employee")
        self.assertTrue(user.check_password(self.password))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_invalid_registration_shows_errors_without_creating_user(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "new_employee",
                "password1": self.password,
                "password2": "different",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(
            get_user_model().objects.filter(username="new_employee").exists()
        )

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)
        self.assertIn(SESSION_KEY, self.client.session)

    def test_login_and_logout_require_csrf_and_logout_invalidates_session(self):
        client = Client(enforce_csrf_checks=True)
        credentials = {"username": self.user.username, "password": self.password}
        self.assertEqual(client.post(reverse("login"), credentials).status_code, 403)
        client.get(reverse("login"))
        response = client.post(
            reverse("login"),
            {
                **credentials,
                "csrfmiddlewaretoken": client.cookies[settings.CSRF_COOKIE_NAME].value,
            },
        )
        self.assertRedirects(response, reverse("home"))
        session_key = client.session.session_key
        self.assertEqual(client.post(reverse("logout")).status_code, 403)
        response = client.post(
            reverse("logout"),
            {"csrfmiddlewaretoken": client.cookies[settings.CSRF_COOKIE_NAME].value},
        )
        self.assertRedirects(response, reverse("login"))
        self.assertNotIn(SESSION_KEY, client.session)
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        self.assertRedirects(client.get(reverse("home")), reverse("login") + "?next=/")
