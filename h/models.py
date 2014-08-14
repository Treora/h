# -*- coding: utf-8 -*-

from annotator import annotation, document, openannotation
from pyramid.decorator import reify
from pyramid.i18n import TranslationStringFactory
from pyramid.security import Allow, Authenticated, Everyone, ALL_PERMISSIONS
from zope.interface import implementer

from h import interfaces

_ = TranslationStringFactory(__package__)


@implementer(interfaces.IAnnotationClass)
class Annotation(annotation.Annotation):

    # Specify the base url for our annotations
    jsonld_baseurl = 'https://hypothes.is/a/'

    def __acl__(self):
        acl = []
        # Convert annotator-store roles to pyramid principals
        for action, roles in self.get('permissions', {}).items():
            for role in roles:
                if role.startswith('group:'):
                    if role == 'group:__world__':
                        principal = Everyone
                    elif role == 'group:__authenticated__':
                        principal = Authenticated
                    elif role == 'group:__consumer__':
                        raise NotImplementedError("API consumer groups")
                    else:
                        principal = role
                elif role.startswith('acct:'):
                    principal = role
                else:
                    raise ValueError(
                        "Unrecognized role '%s' in annotation '%s'" %
                        (role, self.get('id'))
                    )

                # Append the converted rule tuple to the ACL
                rule = (Allow, principal, action)
                acl.append(rule)

        if acl:
            return acl
        else:
            # If there is no acl, it's an admin party!
            return [(Allow, Everyone, ALL_PERMISSIONS)]

    __mapping__ = {
        'annotator_schema_version': {'type': 'string'},
        'created': {'type': 'date'},
        'updated': {'type': 'date'},
        'quote': {'type': 'string'},
        'tags': {'type': 'string', 'index': 'analyzed', 'analyzer': 'lower_keyword'},
        'text': {'type': 'string'},
        'deleted': {'type': 'boolean'},
        'uri': {'type': 'string', 'index_analyzer': 'uri_index', 'search_analyzer': 'uri_search'},
        'user': {'type': 'string', 'index': 'analyzed', 'analyzer': 'lower_keyword'},
        'consumer': {'type': 'string', 'index': 'not_analyzed'},
        'target': {
            'properties': {
                'id': {
                    'type': 'multi_field',
                    'path': 'just_name',
                    'fields': {
                        'id': {'type': 'string', 'index': 'not_analyzed'},
                        'uri': {'type': 'string', 'index_analyzer': 'uri_index', 'search_analyzer': 'uri_search'},
                    },
                },
                'source': {
                    'type': 'multi_field',
                    'path': 'just_name',
                    'fields': {
                        'source': {'type': 'string', 'index': 'not_analyzed'},
                        'uri': {'type': 'string', 'index_analyzer': 'uri_index', 'search_analyzer': 'uri_search'},
                    },
                },
                'selector': {
                    'properties': {
                        'type': {'type': 'string', 'index': 'no'},

                        # Annotator XPath+offset selector
                        'startContainer': {'type': 'string', 'index': 'no'},
                        'startOffset': {'type': 'long', 'index': 'no'},
                        'endContainer': {'type': 'string', 'index': 'no'},
                        'endOffset': {'type': 'long', 'index': 'no'},

                        # Open Annotation TextQuoteSelector
                        'exact': {
                            'type': 'multi_field',
                            'path': 'just_name',
                            'fields': {
                                'exact': {'type': 'string'},
                                'quote': {'type': 'string'},
                            },
                        },
                        'prefix': {'type': 'string'},
                        'suffix': {'type': 'string'},

                        # Open Annotation (Data|Text)PositionSelector
                        'start': {'type': 'long'},
                        'end':   {'type': 'long'},
                    }
                }
            }
        },
        'permissions': {
            'index_name': 'permission',
            'properties': {
                'read': {'type': 'string', 'index': 'not_analyzed'},
                'update': {'type': 'string', 'index': 'not_analyzed'},
                'delete': {'type': 'string', 'index': 'not_analyzed'},
                'admin': {'type': 'string', 'index': 'not_analyzed'}
            }
        },
        'references': {'type': 'string', 'index': 'not_analyzed'},
        'document': {
            'properties': document.MAPPING
        },
        'thread': {
            'type': 'string',
            'analyzer': 'thread'
        }
    }
    __settings__ = {
        'analysis': {
            'filter': {
                'uri': {
                    'type': 'pattern_capture',
                    'preserve_original': 1,
                    'patterns': [
                        '([^\\/\\?\\#\\.]+)',
                        '((\\w+|\\d+)(?:\\.(\\w+|\\d+))*)'
                    ]
                }
            },
            'analyzer': {
                'thread': {
                    'tokenizer': 'path_hierarchy'
                },
                'lower_keyword': {
                    'type': 'custom',
                    'tokenizer': 'keyword',
                    'filter': 'lowercase'
                },
                'uri_index': {
                    'tokenizer': 'uax_url_email',
                    'filter': ['uri', 'lowercase', 'unique']
                },
                'uri_search': {
                    'tokenizer': 'keyword',
                    'filter': ['lowercase']
                }
            }
        }
    }

    @classmethod
    def update_settings(cls):
        # pylint: disable=no-member
        cls.es.conn.indices.close(index=cls.es.index)
        try:
            cls.es.conn.indices.put_settings(
                index=cls.es.index,
                body=getattr(cls, '__settings__', {})
            )
        finally:
            cls.es.conn.indices.open(index=cls.es.index)


class OAAnnotation(Annotation, openannotation.OAAnnotation):

    @property
    def has_target(self):
        """The targets of the annotation.

           Returns a SpecificResource (= resource+selector) for each annotation
           target (e.g. quote), If there are no specific targets, the url of the
           page itself is declared as a target.

           If the annotation is a reply to another, that one is also considered
           to be a target.
        """
        targets = self.get('target')
        targets_ld = []
        if not targets:
            # The annotation targets the page as a whole
            targets_ld.append(self.get('uri'))
        else:
            # Build the SpecificResource for each target (probably only one).
            if not isinstance(targets, list):
                targets = [targets]
            for target in targets:
                target_ld = self.semantify_target(target)
                targets_ld.append(target_ld)

        # Each annotation being replied to is also considered a target.
        references = self.get('references')
        if references:
            if not isinstance(references, list):
                references = [references]
            for reference in references:
                # A reference is an annotation id, thus prefixed with the base
                # URI it will be a valid target.
                targets_ld.append(reference)

        return targets_ld

    @classmethod
    def semantify_target(cls, target):
        if target.get('id'):
            # Target is specified by a URI.
            return target['id']
        selectors = target.get('selector')
        if not isinstance(selectors, list):
            selectors = [selectors]
        selectors_ld = map(cls.semantify_selector, selectors)
        if len(selectors_ld)==1:
            selector_ld = selectors_ld[0]
        else:
            # SpecificResource allows only one selector, use oa:Choice.
            selector_ld = {
                '@type': 'oa:Choice',
                'item': selectors_ld,
                # The first selector is assigned to be the default
                'default': selectors_ld[0]['@id'],
            }
        target_ld = {
            '@type': 'oa:SpecificResource',
            'hasSource': target['source'],
            'hasSelector': selector_ld,
        }
        return target_ld

    @staticmethod
    def semantify_selector(selector):
        selector_ld = {
            '@id': '_:selector_%s' % hash(`selector`),
        }
        selector_type = selector.get('type')
        if selector_type == 'RangeSelector':
            selector_ld.update({
                '@type': 'annotator:TextRangeSelector',
                'annotator:startContainer': selector['startContainer'],
                'annotator:endContainer': selector['endContainer'],
                'annotator:startOffset': selector['startOffset'],
                'annotator:endOffset': selector['endOffset'],
            })
        elif selector_type in ('TextPositionSelector',
                               'DataPositionSelector'):
            selector_ld.update({
                '@type': 'oa:%s' % selector_type,
                'start': selector['start'],
                'end': selector['end'],
            })
        elif selector_type == 'TextQuoteSelector':
            selector_ld.update({
                '@type': 'TextQuoteSelector',
                'exact': selector.get('exact'),
                'prefix': selector.get('prefix'),
                'suffix': selector.get('suffix'),
            })
        else:
            raise ValueError("Unsupported Selector type: %s" % selector_type)
        return selector_ld


class Document(document.Document):
    pass


def includeme(config):
    registry = config.registry

    models = [
        (interfaces.IAnnotationClass, Annotation),
    ]

    for iface, imp in models:
        if not registry.queryUtility(iface):
            registry.registerUtility(imp, iface)
