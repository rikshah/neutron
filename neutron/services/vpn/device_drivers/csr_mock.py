# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 Cisco Systems, Inc.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# @author: Paul Michali, Cisco Systems, Inc.
# REMOVE import json

"""Mock requests to Cisco Cloud Services Router."""

from functools import wraps
from httmock import urlmatch, all_requests
import requests
from webob import exc as wexc

DEBUG = False


def repeat(n):
    """Decorator to limit the number of times a handler is called.

    Will allow the wrapped function (handler) to be called 'n' times.
    After that, this will return None for any additional calls,
    allowing other handlers, if any, to be invoked.
    """

    class static:
        retries = n

    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if static.retries == 0:
                return None
            static.retries -= 1
            return func(*args, **kwargs)
        return wrapped
    return decorator


def filter(methods, resource):
    """Decorator to invoke handler once for a specific resource.

    This will call the handler only for a specific resource using
    a specific method(s). Any other resource request or method will
    return None, allowing other handlers, if any, to be invoked.
    """

    class static:
        target_methods = [m.upper() for m in methods]
        target_resource = resource

    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if (args[1].method in static.target_methods and
                static.target_resource in args[0].path):
                return func(*args, **kwargs)
            else:
                return None  # Not for this resource
        return wrapped
    return decorator


@urlmatch(netloc=r'localhost')
def token(url, request):
    if 'auth/token-services' in url.path:
        return {'status_code': wexc.HTTPCreated.code,
                'content': {'token-id': 'dummy-token'}}


@urlmatch(netloc=r'localhost')
def token_unauthorized(url, request):
    if 'auth/token-services' in url.path:
        return {'status_code': wexc.HTTPUnauthorized.code}


@urlmatch(netloc=r'wrong-host')
def token_wrong_host(url, request):
    raise requests.ConnectionError()


@all_requests
def token_timeout(url, request):
    raise requests.Timeout()


@all_requests
def timeout(url, request):
    """Simulated timeout of a normal request.

    This handler is conditional, and will only apply to unit test
    cases that match the resource.
    """

    if ('global/host-name' in url.path or
        'interfaces/GigabitEthernet' in url.path or
        'global/local-users' in url.path):
        if not request.headers.get('X-auth-token', None):
            return {'status_code': wexc.HTTPUnauthorized.code}
        raise requests.Timeout()


@urlmatch(netloc=r'localhost')
def no_such_resource(url, request):
    """Indicate not found error, when invalid resource requested."""
    if 'no/such/request' in url.path:
        return {'status_code': wexc.HTTPNotFound.code}


@urlmatch(netloc=r'localhost')
def get(url, request):
    if request.method != 'GET':
        return
    if DEBUG:
        print "DEBUG: GET mock for", url
    if 'global/host-name' in url.path:
        if not request.headers.get('X-auth-token', None):
            return {'status_code': wexc.HTTPUnauthorized.code}
        return {'status_code': wexc.HTTPOk.code,
                'content': {u'kind': u'object#host-name',
                            u'host-name': u'Router'}}
    if 'global/local-users' in url.path:
        if not request.headers.get('X-auth-token', None):
            return {'status_code': wexc.HTTPUnauthorized.code}
        return {'status_code': wexc.HTTPOk.code,
                'content': {u'kind': u'collection#local-user',
                            u'users': ['peter', 'paul', 'mary']}}
    if 'interfaces/GigabitEthernet' in url.path:
        if not request.headers.get('X-auth-token', None):
            return {'status_code': wexc.HTTPUnauthorized.code}
        actual_interface = url.path.split('/')[-1]
        ip = actual_interface[-1]
        return {'status_code': wexc.HTTPOk.code,
                'content': {u'kind': u'object#interface',
                            u'description': u'Nothing yet',
                            u'if-name': actual_interface,
                            u'proxy-arp': True,
                            u'subnet-mask': u'255.255.255.0',
                            u'icmp-unreachable': True,
                            u'nat-direction': u'',
                            u'icmp-redirects': True,
                            u'ip-address': u'192.168.200.%s' % ip,
                            u'verify-unicast-source': False,
                            u'type': u'ethernet'}}


@filter(['get'], 'global/host-name')
@repeat(1)
@urlmatch(netloc=r'localhost')
def expired_request(url, request):
    """Simulate access denied failure on first request for this resource.

    Intent here is to simulate that the token has expired, by failing
    the first request to the resource. Because of the repeat=1, this
    will only be called once, and subsequent calls will not be handled
    by this function, but instead will access the normal handler and
    will pass. Currently configured for a GET request, but will work
    with POST and PUT as well. For DELETE, would need to filter on a
    different resource (e.g. 'global/local-users')
    """

    return {'status_code': wexc.HTTPUnauthorized.code}


@urlmatch(netloc=r'localhost')
def post(url, request):
    if request.method != 'POST':
        return
    if DEBUG:
        print"DEBUG: POST mock for", url
    if 'interfaces/GigabitEthernet' in url.path:
        if not request.headers.get('X-auth-token', None):
            return {'status_code': wexc.HTTPUnauthorized.code}
        return {'status_code': wexc.HTTPNoContent.code}
    if 'global/local-users' in url.path:
        if not request.headers.get('X-auth-token', None):
            return {'status_code': wexc.HTTPUnauthorized.code}
        return {'status_code': wexc.HTTPCreated.code}


@urlmatch(netloc=r'localhost')
def put(url, request):
    if request.method != 'PUT':
        return
    if DEBUG:
        print "DEBUG: PUT mock for", url
    if not request.headers.get('X-auth-token', None):
        return {'status_code': wexc.HTTPUnauthorized.code}
    # Any resource
    return {'status_code': wexc.HTTPNoContent.code}


@urlmatch(netloc=r'localhost')
def delete(url, request):
    if request.method != 'DELETE':
        return
    if DEBUG:
        print "DEBUG: DELETE mock for", url
    if not request.headers.get('X-auth-token', None):
        return {'status_code': wexc.HTTPUnauthorized.code}
    # Any resource
    return {'status_code': wexc.HTTPNoContent.code}


@urlmatch(netloc=r'localhost')
def delete_unknown(url, request):
    if request.method != 'DELETE':
        return
    if DEBUG:
        print "DEBUG: DELETE unknown mock for", url
    if not request.headers.get('X-auth-token', None):
        return {'status_code': wexc.HTTPUnauthorized.code}
    # Any resource
    return {'status_code': wexc.HTTPNotFound.code}


@urlmatch(netloc=r'localhost')
def delete_not_allowed(url, request):
    if request.method != 'DELETE':
        return
    if DEBUG:
        print "DEBUG: DELETE not allowed mock for", url
    if not request.headers.get('X-auth-token', None):
        return {'status_code': wexc.HTTPUnauthorized.code}
    # Any resource
    return {'status_code': wexc.HTTPMethodNotAllowed.code}
