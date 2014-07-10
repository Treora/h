# -*- coding: utf-8 -*-
import logging

from pyramid.interfaces import ILocation
from pyramid.security import Allow, Everyone, Authenticated, ALL_PERMISSIONS
from pyramid import httpexceptions
from zope.interface import implementer

from h import interfaces, security

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


@implementer(ILocation)
class BaseResource(dict):
    """Base Resource class from which all resources are derived"""

    __name__ = None
    __parent__ = None

    def __init__(self, request, **kwargs):
        self.request = request
        super(BaseResource, self).__init__(kwargs)


class InnerResource(BaseResource):
    """Helper Resource class for constructing traversal contexts

    Classes which inherit from this should contain attributes which are either
    class constructors for classes whose instances provide the
    :class:`pyramid.interfaces.ILocation` interface else attributes which are,
    themselves, instances of such a class. Such attributes are treated as
    valid traversal children of the Resource whose path component is the name
    of the attribute.
    """

    def __getitem__(self, name):
        """
        Any class attribute which is an instance providing
        :class:`pyramid.interfaces.ILocation` will be returned as is.

        Attributes which are constructors for implementing classes will
        be replaced with a constructed instance.

        Assignment to the sub-resources `__name__` and `__parent__` properties
        is handled automatically.
        """

        if name in self:
            return super(InnerResource, self).__getitem__(name)

        factory_or_resource = getattr(self, name, None)

        if factory_or_resource:
            try:
                if ILocation.implementedBy(factory_or_resource):
                    inst = factory_or_resource(self.request)
                    inst.__name__ = name
                    inst.__parent__ = self
                    self.__dict__[name] = inst
                    return inst
            except TypeError:
                pass

            try:
                if ILocation.providedBy(factory_or_resource):
                    return factory_or_resource
            except TypeError:
                pass

        raise KeyError(name)


@implementer(interfaces.IStreamResource)
class Stream(BaseResource):
    pass


class UserStreamFactory(BaseResource):
    def __getitem__(self, key):
        return Stream(self.request, stream_type='user', stream_key=key)


class TagStreamFactory(BaseResource):
    def __getitem__(self, key):
        return Stream(self.request, stream_type='tag', stream_key=key)


class AnnotationFactory(BaseResource):
    def __init__(self, request, **kwargs):
        registry = request.registry
        self.Annotation = registry.queryUtility(interfaces.IAnnotationClass)
        super(AnnotationFactory, self).__init__(request, **kwargs)

    def __getitem__(self, key):
        annotation = self.Annotation.fetch(key)
        if annotation is None:
            raise httpexceptions.HTTPNotFound(
                body_template=
                "Either no annotation exists with this identifier, or you "
                "don't have the permissions required for viewing it."
            )
        annotation.__name__ = key
        annotation.__parent__ = self

        return annotation

"""
We create two names for the same resource, so we can distinguish which view to
use. We wish to return the JSON representation when the Annotation has been
created as part of an API call (/api/annotation/<id>), and to return a shiny
HTML page when /a/<id> was requested.
"""
class AnnotationFactory_API(AnnotationFactory):
    pass
class AnnotationFactory_Display(AnnotationFactory):
    pass


class APISearchResource(BaseResource):
    """Triggered on /api/search"""
    pass

class APITokenResource(BaseResource):
    """Triggered on /api/token"""
    pass

class APIResource(InnerResource):
    """Triggered on /api/"""
    annotations = AnnotationFactory_API
    search = APISearchResource
    token = APITokenResource

class RootFactory(Stream, InnerResource):
    a = AnnotationFactory_Display
    t = TagStreamFactory
    u = UserStreamFactory
    api = APIResource
    stream = Stream

    def __acl__(self):  # pylint: disable=no-self-use
        defaultlist = [
            (Allow, 'group:admin', ALL_PERMISSIONS),
            (Allow, Everyone, 'search'),
            (Allow, Authenticated, 'create'),
            (Allow, security.Authorizations, 'account'),
        ]
        return defaultlist
