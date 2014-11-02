"""
Annotations for testing.
"""
example_annotations = {
    'alice_private': {
        "updated": "2014-11-02T12:53:02.417907+00:00",
        "target": [
            {
                "source": "http://localhost:5000/",
                "pos": {
                "top": 125.44999694824,
                "height": 30
                },
                "selector": [
                {
                    "type": "RangeSelector",
                    "startContainer": "/div[1]/article[1]/section[1]/h2[1]",
                    "endContainer": "/div[1]/article[1]/section[1]/h2[1]",
                    "startOffset": 0,
                    "endOffset": 15
                },
                {
                    "start": 41,
                    "end": 56,
                    "type": "TextPositionSelector"
                },
                {
                    "type": "TextQuoteSelector",
                    "prefix": "is The Internet, peer reviewed.",
                    "exact": "Getting started",
                    "suffix": "Great, you've got the server up"
                }
                ]
            }
        ],
        "created": "2014-11-02T12:51:27.981394+00:00",
        "text": "bla bla bla.",
        "tags": [
            "test",
            "bla"
        ],
        "uri": "http://localhost:5000/",
        "user": "acct:alice@localhost",
        "document": {
            "eprints": {

            },
            "title": "Hypothesis",
            "twitter": {

            },
            "dc": {

            },
            "prism": {

            },
            "highwire": {

            },
            "facebook": {

            },
            "reply_to": [

            ],
            "link": [
                {
                    "href": "http://localhost:5000/"
                }
            ]
        },
        "consumer": "00000000-0000-0000-0000-000000000000",
        "id": "V-F9Eo1OSViuWwteYDzn-Q",
        "permissions": {
            "admin": [
                "acct:alice@localhost"
            ],
            "read": [
                "acct:alice@localhost"
            ],
            "update": [
                "acct:alice@localhost"
            ],
            "delete": [
                "acct:alice@localhost"
            ]
        }
    },

    'alice_public': {
        "updated": "2014-11-02T12:52:30.290450+00:00",
        "target": [
            {
                "source": "http://localhost:5000/",
                "pos": {
                    "top": 64.600006103516,
                    "height": 18
                },
                "selector": [
                {
                    "type": "RangeSelector",
                    "startContainer": "/div[1]/div[1]/header[1]/hgroup[1]/h2[1]",
                    "endContainer": "/div[1]/div[1]/header[1]/hgroup[1]/h2[1]",
                    "startOffset": 0,
                    "endOffset": 28
                },
                {
                    "start": 12,
                    "end": 40,
                    "type": "TextPositionSelector"
                },
                {
                    "type": "TextQuoteSelector",
                    "prefix": "Hypothes.is",
                    "exact": "The Internet, peer reviewed.",
                    "suffix": "Getting started Great, you've g"
                }
                ]
            }
        ],
        "created": "2014-11-02T12:52:30.290431+00:00",
        "text": "pompidom",
        "tags": [

        ],
        "uri": "http://localhost:5000/",
        "user": "acct:alice@localhost",
        "document": {
            "eprints": {

            },
            "title": "Hypothesis",
            "twitter": {

            },
            "dc": {

            },
            "prism": {

            },
            "highwire": {

            },
            "link": [
                {
                    "href": "http://localhost:5000/"
                }
            ],
            "reply_to": [

            ],
            "facebook": {

            }
        },
        "consumer": "00000000-0000-0000-0000-000000000000",
        "id": "sYjOa4jRTIG6AA0H5yuyuw",
        "permissions": {
            "admin": [
                "acct:alice@localhost"
            ],
            "read": [
                "acct:alice@localhost",
                "group:__world__"
            ],
            "update": [
                "acct:alice@localhost"
            ],
            "delete": [
                "acct:alice@localhost"
            ]
        }
    }
}

