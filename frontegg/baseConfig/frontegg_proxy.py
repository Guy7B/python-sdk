from frontegg.baseConfig.frontegg_authenticator import FronteggAuthenticator
from frontegg.helpers.frontegg_urls import frontegg_urls
from urllib.parse import urljoin
import typing
from frontegg.helpers.frontegg_headers import frontegg_headers
from frontegg.helpers.exceptions import HttpException
from .identity_mixin import IdentityClientMixin


class FronteggProxy(FronteggAuthenticator, IdentityClientMixin):
    __routes_config = None

    def proxy_request(self, request, method: str, path: str, host: str, params: dict,
                      body: typing.Optional[any], cookies: typing.Optional[dict] = None,
                      headers: typing.Optional[dict] = {}):
        if not request:
            raise Exception('request is required')

        if not method:
            raise Exception('method is required')

        if not path:
            raise Exception('path is required')

        path_without_frontegg = path.replace('/frontegg/', '').replace('frontegg/', '')

        public_route = self.is_public_route(path_without_frontegg, params, method)

        if self.authentication_middleware is not None and not public_route:
            try:
                self.authentication_middleware(request)
            except HttpException as response:
                return response
            except:
                return HttpException('Something went wrong', 500)

        url = urljoin(frontegg_urls.base_url, path_without_frontegg)
        headers = self.clean_headers(headers, host)
        headers = self.set_context(headers, request)

        if self.should_refresh_vendor_token:
            self.refresh_vendor_token()

        response = self.vendor_session_request.request(
            method,
            url,
            headers=headers,
            cookies=cookies,
            data=body,
            params=params
        )

        return response

    def clean_headers(self, headers: dict, host: str) -> dict:
        new_headers = dict()
        for key, value in headers.items():
            if 'access-control' not in key.lower() and key.lower() != 'host' and key.lower() != 'authorization':
                new_headers[key] = value

        new_headers[frontegg_headers['vendor_host']] = host
        return new_headers

    def set_context(self, headers: dict, request) -> dict:
        context = self.context_callback(request)
        if context.get('tenant_id'):
            headers[frontegg_headers['tenant_id']] = context['tenant_id']
        if context.get('user_id'):
            headers[frontegg_headers['user_id']] = context['user_id']

        return headers

    @property
    def routes_config(self):
        if self.__routes_config:
            return self.__routes_config
        response = self.vendor_session_request.get(frontegg_urls.routes_config)

        self.__routes_config = response.json()
        return self.__routes_config

    def is_public_route(self, path: str, params: dict, method: str) -> bool:
        public_routes = self.routes_config['vendorClientPublicRoutes']

        for route in public_routes:
            if path != route['url']:
                continue
            if method != route['method'].upper():
                continue
            if route.get('withQueryParams'):
                is_valid = True
                for query_param in route['withQueryParams']:
                    value = params.get(query_param['key'])
                    if not value:
                        is_valid = False
                        break
                    if query_param['value'] and value != query_param['value']:
                        is_valid = False
                        break

                if not is_valid:
                    continue
            return True
        return False