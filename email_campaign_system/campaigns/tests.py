from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Campaign, RecipientList, Recipient, EmailLog


class ModelTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword'
        )
        
        # Create a recipient list
        self.recipient_list = RecipientList.objects.create(
            name='Test List'
        )
        
        # Create a recipient
        self.recipient = Recipient.objects.create(
            email='test@example.com',
            name='Test User',
            recipient_list=self.recipient_list
        )
        
        # Create a campaign
        self.campaign = Campaign.objects.create(
            name='Test Campaign',
            subject='Test Subject',
            content='Hello {{name}}',
            from_name='Test Sender',
            status='draft',
            schedule_type='one_time',
            scheduled_time=timezone.now() + timezone.timedelta(days=1),
            recipient_list=self.recipient_list
        )

    def test_recipient_list_creation(self):
        recipient_list = RecipientList.objects.get(name='Test List')
        self.assertEqual(recipient_list.name, 'Test List')
        
    def test_recipient_creation(self):
        recipient = Recipient.objects.get(email='test@example.com')
        self.assertEqual(recipient.name, 'Test User')
        self.assertEqual(recipient.recipient_list, self.recipient_list)
        
    def test_campaign_creation(self):
        campaign = Campaign.objects.get(name='Test Campaign')
        self.assertEqual(campaign.subject, 'Test Subject')
        self.assertEqual(campaign.from_name, 'Test Sender')
        self.assertEqual(campaign.status, 'draft')
        self.assertEqual(campaign.recipient_list, self.recipient_list)


class ViewTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword'
        )
        
        # Create a recipient list
        self.recipient_list = RecipientList.objects.create(
            name='Test List'
        )
        
        # Create a campaign
        self.campaign = Campaign.objects.create(
            name='Test Campaign',
            subject='Test Subject',
            content='Hello {{name}}',
            from_name='Test Sender',
            status='draft',
            schedule_type='one_time',
            scheduled_time=timezone.now() + timezone.timedelta(days=1),
            recipient_list=self.recipient_list
        )

    def test_login_view(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'campaigns/login.html')
        
    def test_login_success(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpassword'
        })
        self.assertRedirects(response, reverse('dashboard'))
        
    def test_login_failure(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'campaigns/login.html')
        
    def test_dashboard_view_authentication(self):
        # Unauthenticated access should be redirected to login
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")
        
        # Authenticated access should work
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'campaigns/dashboard.html')
