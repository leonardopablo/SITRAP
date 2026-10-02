from django.test import SimpleTestCase


class HealthTests(SimpleTestCase):
    def test_liveness_without_database_or_session(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_wsgi_and_asgi_start(self):
        from config.asgi import application as asgi
        from config.wsgi import application as wsgi

        self.assertTrue(callable(asgi))
        self.assertTrue(callable(wsgi))
