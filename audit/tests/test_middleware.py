"""
Tests for the audit middleware.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.contrib.auth.models import AnonymousUser

# Import the middleware we're testing
from ..middleware import AuditMiddleware

# Get the user model
User = get_user_model()

# Test settings to avoid database issues
TEST_SETTINGS = {
    'DATABASES': {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:'
        }
    },
    'MIDDLEWARE': [
        'django.middleware.security.SecurityMiddleware',
        'whitenoise.middleware.WhiteNoiseMiddleware',
        'audit.middleware.AuditMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ],
    'AUTH_USER_MODEL': 'authentication.CustomUser',
}

@override_settings(**TEST_SETTINGS)
class AuditMiddlewareTest(TestCase):
    """Test cases for the AuditMiddleware."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up data for the whole TestCase."""
        from django.contrib.auth.models import Group
        
        # Create necessary groups
        Group.objects.get_or_create(name='Admin')
        Group.objects.get_or_create(name='Claim Adjuster')
        Group.objects.get_or_create(name='Manager')
        
        cls.User = get_user_model()
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=HttpResponse('Test response'))
        self.middleware = AuditMiddleware(get_response=self.get_response)
        
        # Create a test user
        self.user = self.User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            full_name='Test User',
            role='Claim Adjuster',
            is_active=True
        )
    
    @patch('audit.middleware.log_api_call')
    def test_middleware_skips_admin_urls(self, mock_log_api_call):
        """Test that admin URLs are skipped by the middleware."""
        request = self.factory.get('/admin/')
        request.user = self.user
        response = self.middleware(request)
        
        # Verify the response is passed through
        self.assertEqual(response.status_code, 200)
        # Verify no logging was done for admin URLs
        mock_log_api_call.assert_not_called()
    
    @patch('audit.middleware.log_api_call')
    def test_middleware_logs_api_request(self, mock_log_api_call):
        """Test that API requests are logged by the middleware."""
        request = self.factory.get('/api/v1/some-endpoint/')
        request.user = self.user
        
        response = self.middleware(request)
        
        # Verify the response is passed through
        self.assertEqual(response.status_code, 200)
        # Verify the logging function was called
        mock_log_api_call.assert_called_once()
    
    @patch('audit.middleware.log_api_call')
    def test_middleware_handles_anonymous_user(self, mock_log_api_call):
        """Test that the middleware handles anonymous users correctly."""
        request = self.factory.get('/api/v1/public-endpoint/')
        request.user = AnonymousUser()
        
        response = self.middleware(request)
        
        # Verify the response is passed through
        self.assertEqual(response.status_code, 200)
        # Verify the logging function was called even for anonymous users
        mock_log_api_call.assert_called_once()
    
    @patch('audit.middleware.log_api_call')
    def test_middleware_handles_post_request(self, mock_log_api_call):
        """Test that POST requests are handled correctly."""
        data = {'key': 'value'}
        request = self.factory.post(
            '/api/v1/some-endpoint/',
            data=data,
            content_type='application/json'
        )
        request.user = self.user
        
        response = self.middleware(request)
        
        # Verify the response is passed through
        self.assertEqual(response.status_code, 200)
        # Verify the logging function was called
        mock_log_api_call.assert_called_once()
        
        # Get the call arguments
        _, call_kwargs = mock_log_api_call.call_args
        # Verify the request body is in the metadata
        self.assertIn('request_body', call_kwargs.get('metadata', {}))
