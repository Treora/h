# -*- coding: utf-8 -*-

"""This API mostly mimics the annotator-store REST API, but is based on Pyramid
rather than Flask. Also it includes Hypothes.is-specific modifications."""

import json
import logging
import os

from elasticsearch import exceptions as elasticsearch_exceptions
from pyramid import httpexceptions
from pyramid.view import view_config, view_defaults
from pyramid.settings import asbool
from pyramid.security import NO_PERMISSION_REQUIRED
from annotator import auth, es

from h import events, models, interfaces, resources
from h.auth.local.oauth import LocalAuthenticationPolicy
from h.auth.local.views import token as access_token

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

"""
A quick explanation for those unfamiliar with the Pyramid Web Framework.
The resources defined in resources.py create the tree ('folder') structure using
Pyramid's "traversal" pattern. For example, "/api/annotations/" will result in
h.resources.AnnotationFactory being selected as the request's Context. For each
group of Views, we specify (using @view_defaults) by which type of context these
views can be triggered. That is, which class or interface the context should
have.
For a context (= resource = /some/path/) that implements different actions, we
use @view_config to specify in which situation these views are to be triggered,
for example to use a different view method on a GET than on a POST request.

For more information about Traversal and View configuration, see (respectively):
http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/traversal.html
http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/viewconfig.html
"""

class ViewGrouping(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

@view_defaults(context='h.resources.APIResource',
               name='',
               permission=NO_PERMISSION_REQUIRED,
               accept="application/json",
               renderer="json",
               )
class API(ViewGrouping):
    """Triggered on /api. Return the API descriptor from which the front-end
       application will determine the endpoints to use for each action.
    """
    @view_config()
    def index(self):
        return _api_descriptor(self.request)


@view_defaults(context='h.resources.APISearchResource',
               name='',
               permission="search",
               accept="application/json",
               renderer="json",
               )
class API_Search(ViewGrouping):
    """Triggered on /api/search. Searches the database for annotations matching
    with the given query."""
    @view_config()
    def api_search(self):
        request = self.request
        registry = request.registry

        kwargs = dict()
        params = dict(request.params)
        # Take limit and offset out of the parameters
        if 'offset' in params:
            try:
                kwargs['offset'] = int(params.pop('offset'))
            except ValueError:
                pass # raise error?
        if 'limit' in params:
            try:
                kwargs['limit'] = int(params.pop('limit'))
            except ValueError:
                pass # raise error?

        # All remaining parameters are considered searched fields.
        kwargs['query'] = params
        # Lowercase all.
        # See https://github.com/openannotation/annotator-store/issues/77 and 73
        for field in params: params[field] = params[field].lower()

        # The search results are filtered for the authenticated user
        user = _create_annotator_user(request)
        log.debug("Searching with user=%s, for uri=%s"
            % (user.id if user else 'None',
                params.get('uri')))
        kwargs['user'] = user

        Annotation = registry.queryUtility(interfaces.IAnnotationClass)
        results = Annotation.search(**kwargs)
        total = Annotation.count(**kwargs)

        return {
            'rows': results,
            'total': total,
        }

@view_defaults(context="h.resources.APITokenResource",
               name='',
               permission=NO_PERMISSION_REQUIRED, # or other permission?
               renderer="string",
               )
class API_Token(ViewGrouping):
    """Triggered on /api/token. Return the user's API authentication token."""
    @view_config()
    def api_token(self):
        # Get the OAuth token (correct?) and obtain the token string from it
        tokenbody = json.loads(access_token(self.request).body)
        return tokenbody.get('access_token', '')


@view_defaults(context='h.resources.AnnotationFactory',
               # Check if we are in /api/..., to prevent being triggered on /a/
               containment='h.resources.APIResource',
               name='',
               accept="application/json",
               renderer="json",
               )
class AnnotationStorage_no_id_specified(ViewGrouping):
    """Triggered when /api/annotations/ is requested (without an annotation ID)
       Actions:
       * GET: Read the most recent annotations
       * PUSH: Create a new annotation
    """
    @view_config(request_method="GET", permission="search")
    def annotations_index(self):
        """Do a search for all annotations on anything and return results.
           This will use the default limit, 20 at time of writing, and results
           are ordered most recent first.
        """
        Annotation = self.context.Annotation
        log.debug("Getting the most recent annotations in the store")
        user = _create_annotator_user(self.request)
        return Annotation.search(user=user)

    @view_config(request_method="POST", permission="create")
    def create(self):
        """Read the POSTed JSON-encoded annotation and stored it into
           annotator-store.
        """
        request = self.request
        Annotation = self.context.Annotation
        log.debug("Creating annotation")

        # Read the annotation that is to be stored
        try:
            fields = request.json_body
        except:
            raise httpexceptions.HTTPBadRequest(
                body_template="No JSON payload sent. Annotation not created.")

        # These fields are not to be set by the user
        fields_to_remove = ['created', 'updated', 'user', 'consumer', 'id']
        for field in fields_to_remove:
            fields.pop(field, None)
        # Create Annotation instance
        annotation = Annotation(fields)

        # Set user and consumer fields
        user = _create_annotator_user(request)
        if user is not None:
            # Check if user id of annotation matches with current user
            if _get_annotation_user(annotation) != user.id:
                # If not, use user id as user string
                annotation['user'] = user.id
            annotation['consumer'] = user.consumer.key
            log.debug("User: %s" % user.id)
            log.debug("Consumer key: %s" % user.consumer.key)
        else:
            # Should not occur as view requires an authenticated user
            raise # Error type?

        # Save it in the database
        annotation.save()

        # Notify any subscribers
        _notify_event(request, annotation, 'create')

        # Return it so the client gets to know its ID and such
        return annotation

@view_defaults(context='h.interfaces.IAnnotationClass',
               # The containment predicate ensures we only respond to an API
               # call, by checking that the parent resource is the one
               # associated with /api/annotations/<id>, and not /a/<id>.
               containment='h.resources.AnnotationFactory_API',
               name='',
               accept="application/json",
               renderer="json",
               )
class AnnotationStorage_with_specific_id(ViewGrouping):
    """Triggered on /api/annotations/<annotation_id>
       Actions:
       * GET: Read the annotation
       * PUT: Update the annotation
       * DELETE: Delete the annotation
       The permissions for each action are assigned in the Annotation's __acl__,
       and are directly converted from the annotation's 'permissions' field. See
       the Annotation class for details.
    """

    @view_config(request_method="GET", permission="read")
    def index(self):
        """Return the annotation (simply how it was stored in the database)"""
        request = self.request
        annotation = self.context
        log.debug("Returning single annotation")

        # Notify any subscribers
        _notify_event(request, annotation, 'read')

        return annotation

    @view_config(request_method="PUT", permission="update")
    def update(self):
        """Update the fields we received and store the updated version"""
        request = self.request
        annotation = self.context
        log.debug("Updating annotation")

        # Read the new fields for the annotation
        try:
            fields = request.json_body
        except:
            raise
        # These fields are not to be set by the user
        fields_to_remove = ['created', 'updated', 'user', 'consumer', 'id']
        for field in fields_to_remove:
            fields.pop(field, None)

        # If the user is changing access permissions, check if it's allowed.
        changing_permissions = (
            'permissions' in fields
            and fields['permissions'] != annotation.get('permissions', {})
        )
        if changing_permissions:
            if not request.has_permission('admin', annotation):
                raise httpexceptions.HTTPUnauthorized(body_template=
                    "Not authorized to change annotation permissions.")

        # Update the annotation with the new data
        annotation.update(fields)

        # If the annotation is flagged as deleted, remove mentions of the user
        # When and why do we do this? Why flag things as deleted?
        if annotation.get('deleted', False):
            _anonymize_deletes(annotation)

        # Save the annotation in the database, overwriting the old version.
        annotation.save()

        # Notify any subscribers
        _notify_event(request, annotation, 'update')

        # Return the updated version that was just stored.
        return annotation

    @view_config(request_method="DELETE", permission="delete")
    def delete(self):
        request = self.request
        annotation = self.context
        # Delete the annotation from the database.
        annotation.delete()

        # Notify any subscribers
        _notify_event(request, annotation, 'delete')

        request.response.status_code = 204 # Success, No Content
        return ''


def _anonymize_deletes(annotation):
    """Clear the author and remove the user from the annotation permissions"""

    # Empty the 'user' field (the annotation author)
    user = annotation.get('user', '')
    if user:
        annotation['user'] = ''

    # Remove the user from the permissions, but keep any others in place.
    permissions = annotation.get('permissions', {})
    for action in permissions.keys():
        filtered = [
            role
            for role in annotation['permissions'][action]
            if role != user
        ]
        annotation['permissions'][action] = filtered

def _create_annotator_user(request):
    """Create a User object for annotator-store"""
    settings = request.registry.settings
    key = settings['api.key']
    secret = settings.get('api.secret')
    ttl = settings.get('api.ttl', auth.DEFAULT_TTL)

    consumer = auth.Consumer(key)
    if secret is not None:
        consumer.secret = secret # rudimentary, not used
        consumer.ttl = ttl # rudimentary, not used

    userid = request.authenticated_userid
    if userid is not None:
        return auth.User(userid, consumer, False)
    return None

def _get_annotation_user(ann):
    """Returns the best guess at this annotation's owner user id"""
    # Do we want to support both string userids and objects with an id field?
    user = ann.get('user')
    if not user:
        return None
    try:
        # If user is a dict (thus json object), look at its id property
        return user.get('id', None)
    except AttributeError:
        # Assume user is just the id string
        return user


def _notify_event(request, annotation, action):
    """Notify any subscribers that some action has been performed.
       The possible actions are: 'read', 'create', 'update', 'delete'
    """
    event = events.AnnotationEvent(request, annotation, action)
    request.registry.notify(event)


def _configure_elasticsearch(settings):
    if 'ELASTICSEARCH_PORT' in os.environ:
        # Why exactly is this here?
        es.host = 'http%s' % (
            os.environ['ELASTICSEARCH_PORT'][3:], # Why three?
        )
    elif 'es.host' in settings:
        es.host = settings['es.host']

    if 'es.index' in settings:
        es.index = settings['es.index']

    if 'es.compatibility' in settings:
        es.compatibility_mode = settings['es.compatibility']

    # We want search results to be filtered according to their read-permissions,
    # which is done in the store itself.
    es.authorization_enabled = True

def _url_for(request, action):
    # Can we somehow use resource_url instead to get a single source of truth?
    api_path = ['api']
    store_path = api_path + ['annotations']
    paths = {
        'create': store_path,
        'read': store_path + [':id'],
        'update': store_path + [':id'],
        'delete': store_path + [':id'],

        'search': api_path + ['search'],
    }
    path = paths[action]
    url = request.resource_url(request.root, *path)
    return url


def _api_descriptor(request):
    return {
        'message': "Annotator Store API",
        'links': {
            'annotation': {
                'create': {
                    'method': 'POST',
                    'url': _url_for(request, 'create'),
                    'desc': "Create a new annotation"
                },
                'read': {
                    'method': 'GET',
                    'url': _url_for(request, 'read'),
                    'desc': "Get an existing annotation"
                },
                'update': {
                    'method': 'PUT',
                    'url': _url_for(request, 'update'),
                    'desc': "Update an existing annotation"
                },
                'delete': {
                    'method': 'DELETE',
                    'url': _url_for(request, 'delete'),
                    'desc': "Delete an annotation"
                }
            },
            'search': {
                'method': 'GET',
                'url': _url_for(request, 'search'),
                'desc': 'Basic search API'
            },
        }
    }


def _create_db():
    """Create the ElasticSearch index for Annotations and Documents"""
    try:
        es.conn.indices.create(es.index)
    except elasticsearch_exceptions.RequestError as e:
        if not e.error.startswith('IndexAlreadyExistsException'):
            raise
    except elasticsearch_exceptions.ConnectionError as e:
        msg = 'Can not access ElasticSearch at {0}! ' \
                'Check to ensure it is running.' \
                .format(es.host)
        raise elasticsearch_exceptions.ConnectionError('N/A', msg, e)
    es.conn.cluster.health(wait_for_status='yellow')
    # Should we use registry.queryUtility(interfaces.IAnnotationClass) ?
    models.Annotation.update_settings()
    models.Annotation.create_all()
    models.Document.create_all()

def _delete_db():
    # Should we use registry.queryUtility(interfaces.IAnnotationClass) ?
    models.Annotation.drop_all()
    models.Document.drop_all()


def includeme(config):
    registry = config.registry
    settings = registry.settings

    # The code block below also appears in auth/local/oauth.py. Should we
    # include that file's includeme instead?
    # Configure the token policy
    authn_debug = settings.get('pyramid.debug_authorization') \
        or settings.get('debug_authorization')
    authn_policy = LocalAuthenticationPolicy(
        environ_key='HTTP_X_ANNOTATOR_AUTH_TOKEN',
        debug=authn_debug,
    )
    config.set_authentication_policy(authn_policy)

    _configure_elasticsearch(settings)

    # Maybe initialize the models
    if asbool(settings.get('basemodel.should_drop_all', False)):
        _delete_db()
    if asbool(settings.get('basemodel.should_create_all', True)):
        _create_db()


    config.scan(__name__)
