import importlib
import json
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from tasks.models import Task
from tasks.forms import TaskForm


class AuthenticatedTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice")
        self.client.force_login(self.user)


class TaskModelTest(TestCase):
    """Tests liés au modèle Task"""

    def test_task_creation_defaults(self):
        task = Task.objects.create(title="Test task")

        self.assertEqual(task.title, "Test task")
        self.assertFalse(task.complete)
        self.assertIsNotNone(task.created)

    def test_task_str_representation(self):
        task = Task.objects.create(title="Ma tâche")
        self.assertEqual(str(task), "Ma tâche")


class TaskFormTest(TestCase):
    """Tests du formulaire TaskForm"""

    def test_task_form_valid(self):
        form = TaskForm(data={
            "title": "Nouvelle tâche",
            "complete": False
        })
        self.assertTrue(form.is_valid())

    def test_task_form_invalid_without_title(self):
        form = TaskForm(data={
            "complete": False
        })
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)


class TaskUrlsTest(AuthenticatedTestCase):
    """Tests de résolution des URLs"""

    def test_index_url_accessible(self):
        response = self.client.get(reverse("list"))
        self.assertEqual(response.status_code, 200)


class TaskViewsTest(AuthenticatedTestCase):
    """Tests des vues"""

    def setUp(self):
        super().setUp()
        self.task = Task.objects.create(title="Task initiale", owner=self.user)

    def test_index_view_lists_tasks(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Task initiale")

    def test_create_task_via_post(self):
        response = self.client.post("/", {
            "title": "Task POST",
            "complete": False
        })

        self.assertEqual(Task.objects.count(), 2)
        self.assertRedirects(response, "/")

    def test_update_task_get(self):
        response = self.client.get(f"/update_task/{self.task.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Task initiale")

    def test_update_task_post(self):
        response = self.client.post(
            f"/update_task/{self.task.id}/",
            {
                "title": "Task modifiée",
                "complete": True
            }
        )

        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Task modifiée")
        self.assertTrue(self.task.complete)
        self.assertRedirects(response, "/")

    def test_delete_task_get(self):
        response = self.client.get(f"/delete_task/{self.task.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Task initiale")

    def test_delete_task_post(self):
        response = self.client.post(f"/delete_task/{self.task.id}/")

        self.assertEqual(Task.objects.count(), 0)
        self.assertRedirects(response, "/")


class SecurityTests(AuthenticatedTestCase):
    def setUp(self):
        super().setUp()
        self.other = get_user_model().objects.create_user(username="bob")
        self.task = Task.objects.create(title="Private task", owner=self.user)
        self.foreign = Task.objects.create(title="Other private task", owner=self.other)

    def test_anonymous_cannot_access_tasks(self):
        self.client.logout()
        paths = ["/", "/search/", "/import/", "/admin_panel/",
                 f"/update_task/{self.task.pk}/", f"/delete_task/{self.task.pk}/"]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 302)
                self.assertEqual(self.client.post(path, {}).status_code, 302)

    def test_owner_isolation_and_mass_assignment(self):
        self.assertNotContains(self.client.get("/"), self.foreign.title)
        self.assertNotContains(self.client.get("/search/"), self.foreign.title)
        for action in ["update_task", "delete_task"]:
            with self.subTest(action=action):
                response = self.client.post(f"/{action}/{self.foreign.pk}/", {"title": "stolen"})
                self.assertEqual(response.status_code, 404)
        self.client.post("/", {"title": "Owned", "owner": self.other.pk})
        self.assertEqual(Task.objects.get(title="Owned").owner, self.user)
        self.assertTrue(Task.objects.filter(pk=self.foreign.pk).exists())

    def test_invalid_and_empty_forms_do_not_write(self):
        for payload in [{"title": ""}, {"title": "x" * 201}]:
            with self.subTest(payload_length=len(payload["title"])):
                self.assertEqual(self.client.post("/", payload).status_code, 200)
                self.assertEqual(self.client.post(f"/update_task/{self.task.pk}/", payload).status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Private task")
        self.assertEqual(Task.objects.count(), 2)

    def test_html_is_escaped_everywhere(self):
        self.task.title = '<script>alert("x")</script>'
        self.task.complete = True
        self.task.save()
        for path in ["/", "/search/", f"/delete_task/{self.task.pk}/"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, "&lt;script&gt;")
                self.assertNotContains(response, '<script>alert("x")</script>')

    def test_sql_payload_is_literal_search(self):
        response = self.client.get("/search/", {"q": "' OR 1=1 --"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.task.title)
        self.assertNotContains(response, self.foreign.title)

    def test_shell_metacharacters_are_plain_title(self):
        title = "task'; echo SHOULD_NOT_EXECUTE; #"
        response = self.client.post("/", {"title": title})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Task.objects.filter(title=title, owner=self.user).exists())

    def test_delete_cannot_redirect_offsite(self):
        response = self.client.post(f"/delete_task/{self.task.pk}/?next=https://example.org")
        self.assertRedirects(response, "/")

    def test_csrf_required_for_every_write(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for path in ["/", "/import/", f"/update_task/{self.task.pk}/", f"/delete_task/{self.task.pk}/"]:
            with self.subTest(path=path):
                self.assertEqual(client.post(path, {"title": "blocked"}).status_code, 403)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_import_json_validates_before_writing(self):
        self.assertContains(self.client.get("/import/"), "csrfmiddlewaretoken")
        malformed = ["not JSON", "{}", json.dumps(["ok", 4]), json.dumps([""]),
                     json.dumps(["x" * 201]), json.dumps(["x"] * 101), "gASVAAA="]
        for data in malformed:
            with self.subTest(data_length=len(data)):
                self.assertEqual(self.client.post("/import/", {"tasks_data": data}).status_code, 200)
                self.assertEqual(Task.objects.count(), 2)
        self.assertRedirects(self.client.post("/import/", {"tasks_data": '[" Read ", "Test"]'}), "/")
        self.assertEqual(Task.objects.filter(owner=self.user).count(), 3)
        self.assertTrue(Task.objects.filter(title="Read", owner=self.user).exists())

    def test_admin_requires_staff_and_never_returns_secret(self):
        self.assertEqual(self.client.get("/admin_panel/", {"pwd": "arbitrary"}).status_code, 403)
        self.user.is_staff = True
        self.user.save()
        response = self.client.get("/admin_panel/")
        self.assertContains(response, "Bienvenue admin")
        self.assertNotContains(response, settings.SECRET_KEY)

    def test_safe_methods_and_missing_resources(self):
        self.assertEqual(self.client.get("/update_task/999999/").status_code, 404)
        self.assertEqual(self.client.get("/delete_task/999999/").status_code, 404)
        for path in ["/", "/search/", "/import/", "/admin_panel/", "/health/"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.delete(path).status_code, 405)

    def test_login_session_and_security_headers(self):
        password = secrets.token_urlsafe(24)
        self.user.set_password(password)
        self.user.save()
        self.client.logout()
        self.assertContains(self.client.get("/accounts/login/"), "csrfmiddlewaretoken")
        response = self.client.post("/accounts/login/", {"username": self.user.username, "password": password})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.cookies[settings.SESSION_COOKIE_NAME]["httponly"])
        self.assertTrue(response.cookies[settings.SESSION_COOKIE_NAME]["secure"])
        page = self.client.get("/")
        self.assertEqual(page.headers["X-Frame-Options"], "DENY")
        self.assertEqual(page.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(self.client.post("/accounts/logout/").status_code, 302)

    def test_health_and_server_entrypoints(self):
        self.client.logout()
        self.assertEqual(self.client.get("/health/").json(), {"status": "ok"})
        self.assertIsNotNone(importlib.import_module("todo.wsgi").application)
        self.assertIsNotNone(importlib.import_module("todo.asgi").application)
