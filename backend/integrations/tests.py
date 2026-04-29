import os

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from users.views import _create_jwt_for_user


User = get_user_model()


class GmailIntegrationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='gmailuser', password='pass1234')
        self.access_token = _create_jwt_for_user(self.user)

    def test_connect_requires_authentication(self):
        response = self.client.post('/api/integrations/gmail/connect', data={}, format='json')
        self.assertEqual(response.status_code, 401)

    def test_fetch_requires_connected_gmail_account(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        response = self.client.get('/api/integrations/gmail/fetch')
        self.assertEqual(response.status_code, 404)


class WhatsAppIntegrationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='wauser', password='pass1234')
        self.access_token = _create_jwt_for_user(self.user)

    def test_connect_requires_authentication(self):
        response = self.client.post('/api/integrations/whatsapp/connect', data={}, format='json')
        self.assertEqual(response.status_code, 401)

    def test_connect_and_fetch(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        connect_response = self.client.post(
            '/api/integrations/whatsapp/connect',
            data={'phone_number_id': '12345', 'business_phone_number': '+15551234567'},
            format='json',
        )
        self.assertEqual(connect_response.status_code, 200)

        fetch_response = self.client.get('/api/integrations/whatsapp/fetch')
        self.assertEqual(fetch_response.status_code, 200)
        self.assertEqual(fetch_response.data['fetched'], 0)

    def test_webhook_verification_success(self):
        previous = os.environ.get('WHATSAPP_VERIFY_TOKEN')
        os.environ['WHATSAPP_VERIFY_TOKEN'] = 'verify-token'
        try:
            response = self.client.get(
                '/api/integrations/whatsapp/webhook',
                {
                    'hub.mode': 'subscribe',
                    'hub.verify_token': 'verify-token',
                    'hub.challenge': '123456',
                },
            )
        finally:
            if previous is None:
                os.environ.pop('WHATSAPP_VERIFY_TOKEN', None)
            else:
                os.environ['WHATSAPP_VERIFY_TOKEN'] = previous
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode('utf-8'), '123456')
