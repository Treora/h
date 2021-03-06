from mock import patch, Mock, MagicMock

from pyramid.testing import DummyRequest, testConfig
from horus.interfaces import IUserClass, IActivationClass, IUIStrings, IProfileSchema, IProfileForm
from horus.schemas import ProfileSchema
from horus.forms import SubmitForm
from horus.models import UserMixin, ActivationMixin
from horus.strings import UIStringsBase
from hem.interfaces import IDBSession

from h.accounts.views import ProfileController
from h.models import _


class FakeUser(object):
    def __init__(self, username, password, activation_id = 0):
        self.username = username
        self.password = password
        self.activation_id = activation_id


class FakeDB(object):
    def add(self):
        return True


def configure(config):
    config.registry.registerUtility(True, IDBSession)
    config.registry.registerUtility(UserMixin, IUserClass)
    config.registry.registerUtility(ActivationMixin, IActivationClass)
    config.registry.registerUtility(UIStringsBase, IUIStrings)
    config.registry.registerUtility(ProfileSchema, IProfileSchema)
    config.registry.registerUtility(SubmitForm, IProfileForm)


def _get_fake_request(username, password, with_subscriptions=False, active=True):
    fake_request = DummyRequest()

    def get_fake_token():
        return 'fake_token'

    fake_request.params['csrf_token'] = 'fake_token'
    fake_request.session.get_csrf_token = get_fake_token
    fake_request.POST['username'] = username
    fake_request.POST['pwd'] = password

    if with_subscriptions:
        subs = '{"active": activestate, "uri": "username", "id": 1}'
        subs = subs.replace('activestate', str(active).lower()).replace('username', username)
        fake_request.POST['subscriptions'] = subs
    return fake_request


def _good_password(request, username, password):
    return FakeUser(username, password)


def _good_password_simple(request, username, password):
    return True


def _bad_password(request, username, password):
    return None


# Tests for edit_profile calls
def test_profile_invalid_password():
    """ Make sure our edit_profile call validates the user password
    """
    request = _get_fake_request('john', 'doe')

    with testConfig() as config:
        configure(config)
        with patch('horus.models.UserMixin') as mock_user:
            with patch('horus.lib.FlashMessage') as mock_flash:
                mock_user.get_user = MagicMock(side_effect=_bad_password)
                profile = ProfileController(request)
                profile.User = mock_user
                profile.edit_profile()
                assert mock_flash.called_with(request, _('Invalid password.'), kind='error')


def test_profile_calls_super():
    """Make sure our method calls the superclasses edit_profile
       if the validations are successful
    """
    request = _get_fake_request('john', 'smith')
    with testConfig() as config:
        configure(config)
        with patch('horus.models.UserMixin') as mock_user:
            with patch('horus.views.ProfileController.edit_profile') as mock_super_profile:
                mock_user.get_user = MagicMock(side_effect=_good_password_simple)
                profile = ProfileController(request)
                profile.User = mock_user
                profile.edit_profile()
                assert profile.request.context is True
                assert mock_super_profile.called


# Tests for changing the subscription state
def test_subscription_update():
    """Make sure that the new status is written into the DB
    """
    request = _get_fake_request('acct:john@doe', 'smith', True, True)
    print "request", request.POST
    with testConfig() as config:
        configure(config)
        with patch('h.accounts.views.Subscriptions') as mock_subs:
            mock_subs.get_by_id = MagicMock()
            mock_subs.get_by_id.return_value = Mock(active=True)
            profile = ProfileController(request)
            profile.db = Mock()
            profile.db.add = MagicMock(name='add')
            profile.edit_profile()
            assert profile.db.add.called


# Tests for disable_user calls
def test_disable_invalid_password():
    """ Make sure our disable_user call validates the user password
    """
    request = _get_fake_request('john', 'doe')

    with testConfig() as config:
        configure(config)
        with patch('horus.models.UserMixin') as mock_user:
            with patch('horus.lib.FlashMessage') as mock_flash:
                with patch('h.accounts.schemas.EditProfileSchema') as mock_schema:
                    mock_schema.validator = MagicMock(name='validator')
                    mock_user.get_user = MagicMock(side_effect=_bad_password)
                    profile = ProfileController(request)
                    profile.User = mock_user
                    profile.disable_user()
                    assert mock_flash.called_with(request, _('Invalid password.'), kind='error')


def test_user_disabled():
    """Check if the disabled user flag is set
    """
    request = _get_fake_request('john', 'doe')

    with testConfig() as config:
        configure(config)
        with patch('horus.models.UserMixin') as mock_user:
            with patch('horus.lib.FlashMessage') as mock_flash:
                with patch('h.accounts.schemas.EditProfileSchema') as mock_schema:
                    mock_schema.validator = MagicMock(name='validator')
                    mock_user.get_user = MagicMock(side_effect=_good_password)
                    profile = ProfileController(request)
                    profile.User = mock_user
                    profile.db = FakeDB()
                    profile.db.add = MagicMock(name='add')
                    profile.disable_user()
                    assert profile.db.add.called
