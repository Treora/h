# -*- coding: utf-8 -*-

"""This API mostly mimics the annotator-store REST API, but is based on Pyramid
rather than Flask. Also it includes Hypothes.is-specific modifications."""

import json
import logging

from annotator import auth, es
from elasticsearch import exceptions as elasticsearch_exceptions
from pyramid.view import view_config
from pyramid.renderers import render
from pyramid.settings import asbool

from h import events, models, interfaces
from h.auth.local.oauth import get_user
from h.auth.local.views import token as access_token

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

"""
A quick explanation for those unfamiliar with the Pyramid Web Framework.
The resources defined in resources.py create the tree ('folder') structure using
Pyramid's "traversal" pattern. For example, "/api/annotations/" will result in
h.resources.AnnotationFactory being selected as the request's Context.

For more information about Traversal and View configuration, see (respectively):
http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/traversal.html
http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/viewconfig.html
"""


# These annotation fields are not to be set by the user.
PROTECTED_FIELDS = ['created', 'updated', 'user', 'consumer', 'id']


def api_config(**kwargs):
    """Set common view configuration settings

       In fact this creates two view configurations, one for JSON and one for
       JSON-LD. Each triggers on the respective MIME type, and uses the
       appropriate renderer to return the requested type.
    """
    common_config = {
        # XXX: The containment predicate ensures we only respond to API calls
        'containment': 'h.resources.APIResource',
    }
    config = dict(common_config,
                  accept='application/json',
                  renderer='json')
    config_ld = dict(common_config,
                     accept='application/ld+json',
                     renderer='jsonld')
    config.update(kwargs)
    config_ld.update(kwargs)
    if config_ld == config:
        # If accept would somehow have been overridden, we need only one config.
        return view_config(**config)
    else:
        # Compose two decorators, one for json, one for json-ld.
        view_dec = view_config(**config)
        view_dec_ld = view_config(**config_ld)
        composed_dec = lambda wrapped: view_dec(view_dec_ld(wrapped))
        return composed_dec


@api_config(context='h.resources.APIResource')
def index(context, request):
    """Return the API descriptor document

    Clients may use this to discover endpoints for the API.
    """
    return {
        'message': "Annotator Store API",
        'links': {
            'annotation': {
                'create': {
                    'method': 'POST',
                    'url': request.resource_url(context, 'annotations'),
                    'desc': "Create a new annotation"
                },
                'read': {
                    'method': 'GET',
                    'url': request.resource_url(context, 'annotations', ':id'),
                    'desc': "Get an existing annotation"
                },
                'update': {
                    'method': 'PUT',
                    'url': request.resource_url(context, 'annotations', ':id'),
                    'desc': "Update an existing annotation"
                },
                'delete': {
                    'method': 'DELETE',
                    'url': request.resource_url(context, 'annotations', ':id'),
                    'desc': "Delete an annotation"
                }
            },
            'search': {
                'method': 'GET',
                'url': request.resource_url(context, 'search'),
                'desc': 'Basic search API'
            },
        }
    }


@api_config(context='h.resources.APIResource', name='search')
def api_search(context, request):
    """Search the database for annotations matching with the given query."""
    registry = request.registry

    kwargs = dict()
    params = dict(request.params)

    # Take limit and offset out of the parameters
    if 'offset' in params:
        try:
            kwargs['offset'] = int(params.pop('offset'))
        except ValueError:
            pass  # raise error?

    if 'limit' in params:
        try:
            kwargs['limit'] = int(params.pop('limit'))
        except ValueError:
            pass  # raise error?

    # All remaining parameters are considered searched fields.
    kwargs['query'] = params

    # Lowercase all.
    # See https://github.com/openannotation/annotator-store/issues/77 and 73
    for field in params:
        params[field] = params[field].lower()

    # The search results are filtered for the authenticated user
    user = get_user(request)
    log.debug("Searching with user=%s, for uri=%s",
              user.id if user else 'None',
              params.get('uri'))
    kwargs['user'] = user

    Annotation = registry.queryUtility(interfaces.IAnnotationClass)
    results = Annotation.search(**kwargs)
    total = Annotation.count(**kwargs)

    return {
        'rows': results,
        'total': total,
    }


@api_config(context='h.resources.APIResource', name='token', renderer='string')
def api_token(context, request):
    """Return the user's API authentication token."""
    # Get the OAuth response object and obtain the token string from it
    tokenbody = json.loads(access_token(request).body)
    return tokenbody.get('access_token', '')


@api_config(context='h.resources.AnnotationFactory', request_method='GET')
def annotations_index(context, request):
    """Do a search for all annotations on anything and return results.

    This will use the default limit, 20 at time of writing, and results
    are ordered most recent first.
    """
    Annotation = context.Annotation
    user = get_user(request)
    return Annotation.search(user=user)


@api_config(context='h.resources.AnnotationFactory',
            request_method='POST',
            permission='create')
def create(context, request):
    """Read the POSTed JSON-encoded annotation and persist it."""
    Annotation = context.Annotation

    # Read the annotation that is to be stored
    try:
        fields = request.json_body
    except ValueError:
        return _api_error(request,
                          'No JSON payload sent. Annotation not created.',
                          status=400)  # Client Error: Bad Request

    # Some fields are not to be set by the user, ignore them
    for field in PROTECTED_FIELDS:
        fields.pop(field, None)
    # Create Annotation instance
    annotation = Annotation(fields)

    # Set user and consumer fields
    user = get_user(request)
    assert user is not None  # Because creation requires authentication

    annotation['user'] = user.id
    annotation['consumer'] = user.consumer.key

    log.debug('User: %s' % annotation['user'])
    log.debug('Consumer key: %s' % annotation['consumer'])

    # Save it in the database
    annotation.save()

    # Notify any subscribers
    event = events.AnnotationEvent(request, annotation, 'create')
    request.registry.notify(event)

    # Return it so the client gets to know its ID and such
    return annotation


@api_config(context='h.interfaces.IAnnotationClass',
            request_method='GET',
            permission='read')
def read(context, request):
    """Return the annotation (simply how it was stored in the database)"""
    annotation = context

    # Notify any subscribers
    event = events.AnnotationEvent(request, annotation, 'read')
    request.registry.notify(event)

    return annotation


@api_config(context='h.interfaces.IAnnotationClass',
            request_method='PUT',
            permission='update')
def update(context, request):
    """Update the fields we received and store the updated version"""
    annotation = context

    # Read the new fields for the annotation
    try:
        fields = request.json_body
    except ValueError:
        return _api_error(request,
                          'No JSON payload sent. Annotation not created.',
                          status=400)  # Client Error: Bad Request

    # Some fields are not to be set by the user, ignore them
    for field in PROTECTED_FIELDS:
        fields.pop(field, None)

    # If the user is changing access permissions, check if it's allowed.
    changing_permissions = (
        'permissions' in fields
        and fields['permissions'] != annotation.get('permissions', {})
    )
    if changing_permissions:
        if not request.has_permission('admin', annotation):
            return _api_error(
                request,
                'Not authorized to change annotation permissions.',
                status=401)  # Unauthorized

    # Update the annotation with the new data
    annotation.update(fields)

    # If the annotation is flagged as deleted, remove mentions of the user
    if annotation.get('deleted', False):
        _anonymize_deletes(annotation)

    # Save the annotation in the database, overwriting the old version.
    annotation.save()

    # Notify any subscribers
    event = events.AnnotationEvent(request, annotation, 'update')
    request.registry.notify(event)

    # Return the updated version that was just stored.
    return annotation


@api_config(context='h.interfaces.IAnnotationClass',
            request_method='DELETE',
            permission='delete')
def delete(context, request):
    """Delete the annotation permanently."""
    annotation = context
    id = annotation['id']
    # Delete the annotation from the database.
    annotation.delete()

    # Notify any subscribers
    event = events.AnnotationEvent(request, annotation, 'delete')
    request.registry.notify(event)

    # Return a confirmation
    return {
        'id': id,
        'deleted': True,
    }


def _api_error(request, reason, status_code):
    request.response.status_code = status_code
    response_info = {
        'status': 'failure',
        'reason': reason,
    }
    return response_info


def _anonymize_deletes(annotation):
    """Clear the author and remove the user from the annotation permissions"""

    # Delete the annotation author, if present
    user = annotation.pop('user')

    # Remove the user from the permissions, but keep any others in place.
    permissions = annotation.get('permissions', {})
    for action in permissions.keys():
        filtered = [
            role
            for role in annotation['permissions'][action]
            if role != user
        ]
        annotation['permissions'][action] = filtered


def store_from_settings(settings):
    if 'es.host' in settings:
        es.host = settings['es.host']

    if 'es.index' in settings:
        es.index = settings['es.index']

    if 'es.compatibility' in settings:
        es.compatibility_mode = settings['es.compatibility']

    # We want search results to be filtered according to their read-permissions,
    # which is done in the store itself.
    es.authorization_enabled = True

    return es


def create_db():
    """Create the ElasticSearch index for Annotations and Documents"""
    try:
        es.conn.indices.create(es.index)
    except elasticsearch_exceptions.RequestError as e:
        if not e.error.startswith('IndexAlreadyExistsException'):
            raise
    except elasticsearch_exceptions.ConnectionError as e:
        msg = ('Can not access ElasticSearch at {0}! '
               'Check to ensure it is running.').format(es.host)
        raise elasticsearch_exceptions.ConnectionError('N/A', msg, e)
    es.conn.cluster.health(wait_for_status='yellow')
    # Should we use registry.queryUtility(interfaces.IAnnotationClass) ?
    models.Annotation.update_settings()
    models.Annotation.create_all()
    models.Document.create_all()


def delete_db():
    # Should we use registry.queryUtility(interfaces.IAnnotationClass) ?
    models.Annotation.drop_all()
    models.Document.drop_all()


class JsonLdRenderer(object):
    """Runs the json renderer on the jsonld attribute of a given value.

       Lists and dicts are processed elementwise/valuewise.
    """
    def __init__(self, info):
        pass

    def __call__(self, value, system):
        request = system['request']
        # Obtain the JSON-LD representation of the value
        value_ld = self._convert_to_ld(value)

        # Render it through the normal json renderer
        res = render('json',
                     value_ld,
                     request=request)
        request.response.content_type = 'application/ld+json'
        return res

    def _convert_to_ld(self, obj):
        """Recursively process collections, converting each object with a jsonld
           attribute.
        """

        # We don't use hasattr as it fails silently on erroneous properties..
        # if hasattr(obj, 'jsonld'):
        if 'jsonld' in dir(obj):
            return obj.jsonld
        elif isinstance(obj, dict):
            return {key: self._convert_to_ld(value) for key,value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_ld(element) for element in obj]
        else:
            return obj


def includeme(config):
    registry = config.registry
    settings = registry.settings

    # Configure the token policy
    config.include('h.auth.local.oauth')

    # Configure ElasticSearch
    store_from_settings(settings)

    # Maybe initialize the models
    if asbool(settings.get('basemodel.should_drop_all', False)):
        delete_db()
    if asbool(settings.get('basemodel.should_create_all', True)):
        create_db()

    config.add_renderer('jsonld', JsonLdRenderer)

    config.scan(__name__)
