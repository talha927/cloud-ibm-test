# coding: utf-8

"""
    Subscription-svc

    Manage subscriptions to services offered  # noqa: E501

    OpenAPI spec version: 0.2.0
    
    Generated by: https://github.com/swagger-api/swagger-codegen.git
"""


from __future__ import absolute_import

import re  # noqa: F401

# python 2 and python 3 compatibility library
import six

from subscription_client.api_client import ApiClient


class SubscriptionApi(object):
    """NOTE: This class is auto generated by the swagger code generator program.

    Do not edit the class manually.
    Ref: https://github.com/swagger-api/swagger-codegen
    """

    def __init__(self, api_client=None):
        if api_client is None:
            api_client = ApiClient()
        self.api_client = api_client

    def get_subscriptions(self, project_id, **kwargs):  # noqa: E501
        """Get subscriptions  # noqa: E501

        Get subscriptions for a given user  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.get_subscriptions(project_id, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str project_id: Unique identifier associated with the user project (required)
        :param str user_id: Unique identifier associated with the user
        :param str service_id: Unique identifier associated with the service
        :param str status: Status of the subscription
        :return: list[SubscriptionView]
                 If the method is called asynchronously,
                 returns the request thread.
        """
        kwargs['_return_http_data_only'] = True
        if kwargs.get('async_req'):
            return self.get_subscriptions_with_http_info(project_id, **kwargs)  # noqa: E501
        else:
            (data) = self.get_subscriptions_with_http_info(project_id, **kwargs)  # noqa: E501
            return data

    def get_subscriptions_with_http_info(self, project_id, **kwargs):  # noqa: E501
        """Get subscriptions  # noqa: E501

        Get subscriptions for a given user  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.get_subscriptions_with_http_info(project_id, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str project_id: Unique identifier associated with the user project (required)
        :param str user_id: Unique identifier associated with the user
        :param str service_id: Unique identifier associated with the service
        :param str status: Status of the subscription
        :return: list[SubscriptionView]
                 If the method is called asynchronously,
                 returns the request thread.
        """

        all_params = ['project_id', 'user_id', 'service_id', 'status']  # noqa: E501
        all_params.append('async_req')
        all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')

        params = locals()
        for key, val in six.iteritems(params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method get_subscriptions" % key
                )
            params[key] = val
        del params['kwargs']
        # verify the required parameter 'project_id' is set
        if self.api_client.client_side_validation and ('project_id' not in params or
                                                       params['project_id'] is None):  # noqa: E501
            raise ValueError("Missing the required parameter `project_id` when calling `get_subscriptions`")  # noqa: E501

        collection_formats = {}

        path_params = {}

        query_params = []
        if 'project_id' in params:
            query_params.append(('project_id', params['project_id']))  # noqa: E501
        if 'user_id' in params:
            query_params.append(('user_id', params['user_id']))  # noqa: E501
        if 'service_id' in params:
            query_params.append(('service_id', params['service_id']))  # noqa: E501
        if 'status' in params:
            query_params.append(('status', params['status']))  # noqa: E501

        header_params = {}

        form_params = []
        local_var_files = {}

        body_params = None
        # HTTP header `Accept`
        header_params['Accept'] = self.api_client.select_header_accept(
            ['application/json'])  # noqa: E501

        # HTTP header `Content-Type`
        header_params['Content-Type'] = self.api_client.select_header_content_type(  # noqa: E501
            ['application/json'])  # noqa: E501

        # Authentication setting
        auth_settings = ['bearer', 'internal']  # noqa: E501

        return self.api_client.call_api(
            '/subscriptions', 'GET',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type='list[SubscriptionView]',  # noqa: E501
            auth_settings=auth_settings,
            async_req=params.get('async_req'),
            _return_http_data_only=params.get('_return_http_data_only'),
            _preload_content=params.get('_preload_content', True),
            _request_timeout=params.get('_request_timeout'),
            collection_formats=collection_formats)

    def subscribe_user(self, x_user_email, subscription, **kwargs):  # noqa: E501
        """Subscribe user  # noqa: E501

        Subscribe user to a given service  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.subscribe_user(x_user_email, subscription, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str x_user_email: Email of the user (required)
        :param Subscription subscription: Subscription details (required)
        :return: SubscriptionView
                 If the method is called asynchronously,
                 returns the request thread.
        """
        kwargs['_return_http_data_only'] = True
        if kwargs.get('async_req'):
            return self.subscribe_user_with_http_info(x_user_email, subscription, **kwargs)  # noqa: E501
        else:
            (data) = self.subscribe_user_with_http_info(x_user_email, subscription, **kwargs)  # noqa: E501
            return data

    def subscribe_user_with_http_info(self, x_user_email, subscription, **kwargs):  # noqa: E501
        """Subscribe user  # noqa: E501

        Subscribe user to a given service  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.subscribe_user_with_http_info(x_user_email, subscription, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str x_user_email: Email of the user (required)
        :param Subscription subscription: Subscription details (required)
        :return: SubscriptionView
                 If the method is called asynchronously,
                 returns the request thread.
        """

        all_params = ['x_user_email', 'subscription']  # noqa: E501
        all_params.append('async_req')
        all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')

        params = locals()
        for key, val in six.iteritems(params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method subscribe_user" % key
                )
            params[key] = val
        del params['kwargs']
        # verify the required parameter 'x_user_email' is set
        if self.api_client.client_side_validation and ('x_user_email' not in params or
                                                       params['x_user_email'] is None):  # noqa: E501
            raise ValueError("Missing the required parameter `x_user_email` when calling `subscribe_user`")  # noqa: E501
        # verify the required parameter 'subscription' is set
        if self.api_client.client_side_validation and ('subscription' not in params or
                                                       params['subscription'] is None):  # noqa: E501
            raise ValueError("Missing the required parameter `subscription` when calling `subscribe_user`")  # noqa: E501

        collection_formats = {}

        path_params = {}

        query_params = []

        header_params = {}
        if 'x_user_email' in params:
            header_params['X-User-Email'] = params['x_user_email']  # noqa: E501

        form_params = []
        local_var_files = {}

        body_params = None
        if 'subscription' in params:
            body_params = params['subscription']
        # HTTP header `Accept`
        header_params['Accept'] = self.api_client.select_header_accept(
            ['application/json'])  # noqa: E501

        # HTTP header `Content-Type`
        header_params['Content-Type'] = self.api_client.select_header_content_type(  # noqa: E501
            ['application/json'])  # noqa: E501

        # Authentication setting
        auth_settings = ['bearer', 'internal']  # noqa: E501

        return self.api_client.call_api(
            '/subscriptions', 'POST',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type='SubscriptionView',  # noqa: E501
            auth_settings=auth_settings,
            async_req=params.get('async_req'),
            _return_http_data_only=params.get('_return_http_data_only'),
            _preload_content=params.get('_preload_content', True),
            _request_timeout=params.get('_request_timeout'),
            collection_formats=collection_formats)
