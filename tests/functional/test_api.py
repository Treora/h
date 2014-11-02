# -*- coding: utf-8 -*-
"""Defines unit tests for h.api."""

from pprint import pprint

import elasticsearch
import pytest
from paste.deploy import appconfig
from webtest import TestApp

import h
from example_annotations import example_annotations

ES_INDEX = 'annotator_functest'


@pytest.fixture(scope='module')
def config():
    config = appconfig('config:../../development.ini', relative_to='.')
    local_conf = config.local_conf
    global_conf = config.global_conf
    local_conf.update({
        'es.index': ES_INDEX,
    })
    return config


@pytest.fixture(scope='module')
def es(config):
    es = elasticsearch.Elasticsearch([config.local_conf['es.host']])
    return es


@pytest.fixture(scope='module')
def testapp(request, config, es):
    """Run app in development configuration, with special Elasticsearch index"""
    app = h.main(config.global_conf, **config.local_conf)

    def delete_index():
        # Remove the test index from Elasticsearch
        es.indices.delete(ES_INDEX)
    request.addfinalizer(delete_index)

    return TestApp(app)


@pytest.fixture()
def annotations(request, es):
    """Populate the database with example annotations"""
    for annotation in example_annotations.values():
        res = es.index(index=ES_INDEX,
                       doc_type='annotation',
                       body=annotation,
                       refresh=True)
    def delete_annotations():
        #es.delete_by_query(doc_type='annotation', index='annotator', body={'query':{'match_all':{}}})
        for annotation in example_annotations.values():
            es.delete(index=ES_INDEX,
                      doc_type='annotation',
                      id=annotation['id'])
    request.addfinalizer(delete_annotations)

    return example_annotations


def _check_headers(response):
    headers = response.headers
    assert headers['content-type'] == 'application/json; charset=UTF-8'


def test_index(testapp):
    "Get the API descriptor at /api"
    res = testapp.get('/api')
    assert res.status_code == 200
    _check_headers(res)
    assert res.json == {
        'message': 'Annotator Store API',
        'links': {
            'annotation': {
                'create': {
                    'desc': 'Create a new annotation',
                    'method': 'POST',
                    'url': 'http://localhost/api/annotations'
                },
                'delete': {
                    'desc': 'Delete an annotation',
                    'method': 'DELETE',
                    'url': 'http://localhost/api/annotations/:id'
                },
                'read': {
                    'desc': 'Get an existing annotation',
                    'method': 'GET',
                    'url': 'http://localhost/api/annotations/:id'
                },
                'update': {
                    'desc': 'Update an existing annotation',
                    'method': 'PUT',
                    'url': 'http://localhost/api/annotations/:id'
                }
            },
            'search': {
                'desc': 'Basic search API',
                'method': 'GET',
                'url': 'http://localhost/api/search'
            }
        },
    }


def test_search(testapp, annotations):
    res = testapp.get('/api/search?uri=http://localhost:5000/')
    _check_headers(res)
    assert res.json['total'] == len(res.json['rows']) == 1, "Expected one search result"
    assert res.json['rows'][0] == annotations['alice_public']


def test_token(testapp):
    pass


def test_annotation_index(testapp, annotations):
    res = testapp.get('/api/annotations')
    _check_headers(res)
    assert len(res.json) == 1, "Expected to see exactly one public annotation"
    assert res.json[0] == annotations['alice_public']


def test_create(testapp):
    pass


def test_read_public(testapp, annotations):
    id = annotations['alice_public']['id']
    res = testapp.get('/api/annotations/%s' % id)
    _check_headers(res)
    assert res.json == annotations['alice_public']


def test_read_private_unauthenticated(testapp, annotations):
    id = annotations['alice_private']['id']
    # Expect 403 Forbidden
    res = testapp.get('/api/annotations/%s' % id,
                      status=403)


def test_update(testapp):
    pass


def test_update_unauthenticated(testapp, annotations):
    id = annotations['alice_public']['id']
    # Expect 403 Forbidden
    res = testapp.put_json('/api/annotations/%s' % id,
                           params={'text': 'new text!'},
                           status=403)


def test_delete(testapp):
    pass


def test_delete_unauthenticated(testapp, annotations):
    id = annotations['alice_public']['id']
    # Expect 403 Forbidden
    res = testapp.delete('/api/annotations/%s' % id,
                         status=403)
