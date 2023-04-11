from . import pyactiveresource
from .pyactiveresource import connection
from .pyactiveresource.activeresource import ActiveResource, ResourceMeta, formats
from . import yamlobjects
from . import mixins as mixins
from .. import shopify
import threading
import sys
from six.moves import urllib
import six

from .collection import PaginatedCollection
from .pyactiveresource.collection import Collection

# Store the response from the last request in the connection object


class ShopifyConnection(pyactiveresource.connection.Connection):
    response = None

    def __init__(self, site, user=None, password=None, timeout=None,
                 format=formats.JSONFormat):
        super(ShopifyConnection, self).__init__(site, user, password, timeout, format)

    def _open(self, *args, **kwargs):
        self.response = None
        try:
            self.response = super(ShopifyConnection, self)._open(*args, **kwargs)
        except pyactiveresource.connection.ConnectionError as err:
            self.response = err.response
            raise
        return self.response

# Inherit from pyactiveresource's metaclass in order to use ShopifyConnection


class ShopifyResourceMeta(ResourceMeta):

    @property
    def connection(cls):
        """HTTP connection for the current thread"""
        local = cls._threadlocal
        if not getattr(local, 'connection', None):
            # Make sure these variables are no longer affected by other threads.
            local.user = cls.user
            local.password = cls.password
            local.site = cls.site
            local.timeout = cls.timeout
            local.headers = cls.headers
            local.format = cls.format
            local.version = cls.version
            local.url = cls.url
            if cls.site is None:
                raise ValueError("No shopify session is active")
            local.connection = ShopifyConnection(
                cls.site, cls.user, cls.password, cls.timeout, cls.format)
        return local.connection

    def get_user(self):
        return getattr(self._threadlocal, 'user', ShopifyResource._user)

    def set_user(self, value):
        self._threadlocal.connection = None
        ShopifyResource._user = self._threadlocal.user = value

    user = property(get_user, set_user, None,
                    "The username for HTTP Basic Auth.")

    def get_password(self):
        return getattr(self._threadlocal, 'password', ShopifyResource._password)

    def set_password(self, value):
        self._threadlocal.connection = None
        ShopifyResource._password = self._threadlocal.password = value

    password = property(get_password, set_password, None,
                        "The password for HTTP Basic Auth.")

    def get_site(self):
        return getattr(self._threadlocal, 'site', ShopifyResource._site)

    def set_site(self, value):
        self._threadlocal.connection = None
        ShopifyResource._site = self._threadlocal.site = value
        if value is not None:
            parts = urllib.parse.urlparse(value)
            host = parts.hostname
            if parts.port:
                host += f":{str(parts.port)}"
            new_site = urllib.parse.urlunparse((parts.scheme, host, parts.path, '', '', ''))
            ShopifyResource._site = self._threadlocal.site = new_site
            if parts.username:
                self.user = urllib.parse.unquote(parts.username)
            if parts.password:
                self.password = urllib.parse.unquote(parts.password)

    site = property(get_site, set_site, None,
                    'The base REST site to connect to.')

    def get_timeout(self):
        return getattr(self._threadlocal, 'timeout', ShopifyResource._timeout)

    def set_timeout(self, value):
        self._threadlocal.connection = None
        ShopifyResource._timeout = self._threadlocal.timeout = value

    timeout = property(get_timeout, set_timeout, None,
                       'Socket timeout for HTTP requests')

    def get_headers(self):
        if not hasattr(self._threadlocal, 'headers'):
            self._threadlocal.headers = ShopifyResource._headers.copy()
        return self._threadlocal.headers

    def set_headers(self, value):
        self._threadlocal.headers = value

    headers = property(get_headers, set_headers, None,
                       'The headers sent with HTTP requests')

    def get_format(self):
        return getattr(self._threadlocal, 'format', ShopifyResource._format)

    def set_format(self, value):
        self._threadlocal.connection = None
        ShopifyResource._format = self._threadlocal.format = value

    format = property(get_format, set_format, None,
                      'Encoding used for request and responses')

    def get_prefix_source(self):
        """Return the prefix source, by default derived from site."""
        try:
            return self.override_prefix()
        except AttributeError:
            if hasattr(self, '_prefix_source'):
                return self.site + self._prefix_source
            else:
                return self.site

    def set_prefix_source(self, value):
        """Set the prefix source, which will be rendered into the prefix."""
        self._prefix_source = value

    prefix_source = property(get_prefix_source, set_prefix_source, None,
                             'prefix for lookups for this type of object.')

    def get_version(self):
        if hasattr(self._threadlocal, 'version') or ShopifyResource._version:
            return getattr(self._threadlocal, 'version', ShopifyResource._version)
        elif ShopifyResource._site is not None:
            return ShopifyResource._site.split('/')[-1]

    def set_version(self, value):
        ShopifyResource._version = self._threadlocal.version = value

    version = property(get_version, set_version, None,
                      'Shopify Api Version')

    def get_url(self):
        return getattr(self._threadlocal, 'url', ShopifyResource._url)

    def set_url(self, value):
        ShopifyResource._url = self._threadlocal.url = value

    url = property(get_url, set_url, None,
                   'Base URL including protocol and shopify domain')


@six.add_metaclass(ShopifyResourceMeta)
class ShopifyResource(ActiveResource, mixins.Countable):
    _format = formats.JSONFormat
    _threadlocal = threading.local()
    _headers = {
        'User-Agent': 'ShopifyPythonAPI/%s Python/%s' % (shopify.VERSION, sys.version.split(' ', 1)[0])}
    _version = None
    _url = None

    def __init__(self, attributes=None, prefix_options=None):
        if attributes is not None and prefix_options is None:
            prefix_options, attributes = self.__class__._split_options(attributes)
        return super(ShopifyResource, self).__init__(attributes, prefix_options)

    def is_new(self):
        return not self.id

    def _load_attributes_from_response(self, response):
        if response.body.strip():
            self._update(self.__class__.format.decode(response.body))

    @classmethod
    def activate_session(cls, session):
        cls.site = session.site
        cls.url = session.url
        cls.user = None
        cls.password = None
        cls.version = session.api_version.name
        cls.headers['X-Shopify-Access-Token'] = session.token

    @classmethod
    def clear_session(cls):
        cls.site = None
        cls.url = None
        cls.user = None
        cls.password = None
        cls.version = None
        cls.headers.pop('X-Shopify-Access-Token', None)

    @classmethod
    def find(cls, id_=None, from_=None, **kwargs):
        """Checks the resulting collection for pagination metadata."""
        collection = super(ShopifyResource, cls).find(id_=id_, from_=from_, **kwargs)
        if isinstance(collection, Collection) and "headers" in collection.metadata:
            return PaginatedCollection(collection, metadata={"resource_class": cls}, **kwargs)
        return collection
