# -*- coding: utf-8 -*-
import logging
import os
import urlparse
import uuid

from pyramid.config import Configurator
from pyramid.interfaces import ISessionFactory
from pyramid.path import AssetResolver
from pyramid.response import FileResponse
from pyramid.session import SignedCookieSessionFactory

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

log = logging.getLogger(__name__)


def includeme(config):
    config.set_root_factory('h.resources.RootFactory')

    config.include('pyramid_multiauth')

    config.include('h.api')
    config.include('h.models')
    config.include('h.streamer')
    config.include('h.subscribers')
    config.include('h.views')


def create_app(settings):
    config = Configurator(settings=settings)

    favicon = AssetResolver().resolve('h:favicon.ico')
    config.add_route('favicon', '/favicon.ico')
    config.add_view(
        lambda request: FileResponse(favicon.abspath(), request=request),
        route_name='favicon'
    )

    config.add_route('ok', '/ruok')
    config.add_view(lambda request: 'imok', renderer='string', route_name='ok')

    config.include(includeme)
    config.commit()

    # Register a default session factory if there is still none registered
    if config.registry.queryUtility(ISessionFactory) is None:
        random_secret = uuid.uuid4().hex + uuid.uuid4().hex
        session_factory = SignedCookieSessionFactory(random_secret)
        config.set_session_factory(session_factory)

    return config.make_wsgi_app()


def main(global_config, **settings):
    if 'DATABASE_URL' in os.environ:
        urlparse.uses_netloc.append("postgres")
        urlparse.uses_netloc.append("sqlite")
        url = urlparse.urlparse(os.environ["DATABASE_URL"])
        if url.scheme == 'postgres':
            url.scheme = url.scheme + '+psycopg2'
        settings['sqlalchemy.url'] = urlparse.urlunparse(url)

    if 'MAIL_PORT' in os.environ:
        settings['mail.host'] = os.environ['MAIL_PORT_25_TCP_ADDR']
        settings['mail.port'] = os.environ['MAIL_PORT_25_TCP_PORT']

    settings.update(global_config)

    # Possibly override this setting, for Docker linked containers support
    if 'ELASTICSEARCH_PORT' in os.environ:
        if 'es.host' in settings:
            log.warning("Overwriting es.host setting using ELASTICSEARCH_PORT "
                        "environment variable")
        settings['es.host'] = 'http%s' % (
            os.environ['ELASTICSEARCH_PORT'][3:],
        )

    return create_app(settings)
