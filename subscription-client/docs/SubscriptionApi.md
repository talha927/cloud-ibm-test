# subscription_client.SubscriptionApi

All URIs are relative to *http://localhost/v1*

Method | HTTP request | Description
------------- | ------------- | -------------
[**get_subscriptions**](SubscriptionApi.md#get_subscriptions) | **GET** /subscriptions | Get subscriptions
[**subscribe_user**](SubscriptionApi.md#subscribe_user) | **POST** /subscriptions | Subscribe user


# **get_subscriptions**
> list[SubscriptionView] get_subscriptions(project_id, user_id=user_id, service_id=service_id, status=status)

Get subscriptions

Get subscriptions for a given user

### Example
```python
from __future__ import print_function
import time
import subscription_client
from subscription_client.rest import ApiException
from pprint import pprint

# Configure API key authorization: bearer
configuration = subscription_client.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'
# Configure API key authorization: internal
configuration = subscription_client.Configuration()
configuration.api_key['X-API-Key'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['X-API-Key'] = 'Bearer'

# create an instance of the API class
api_instance = subscription_client.SubscriptionApi(subscription_client.ApiClient(configuration))
project_id = 'project_id_example' # str | Unique identifier associated with the user project
user_id = 'user_id_example' # str | Unique identifier associated with the user (optional)
service_id = 'service_id_example' # str | Unique identifier associated with the service (optional)
status = 'status_example' # str | Status of the subscription (optional)

try:
    # Get subscriptions
    api_response = api_instance.get_subscriptions(project_id, user_id=user_id, service_id=service_id, status=status)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling SubscriptionApi->get_subscriptions: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | [**str**](.md)| Unique identifier associated with the user project | 
 **user_id** | [**str**](.md)| Unique identifier associated with the user | [optional] 
 **service_id** | [**str**](.md)| Unique identifier associated with the service | [optional] 
 **status** | **str**| Status of the subscription | [optional] 

### Return type

[**list[SubscriptionView]**](SubscriptionView.md)

### Authorization

[bearer](../README.md#bearer), [internal](../README.md#internal)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **subscribe_user**
> SubscriptionView subscribe_user(x_user_email, subscription)

Subscribe user

Subscribe user to a given service

### Example
```python
from __future__ import print_function
import time
import subscription_client
from subscription_client.rest import ApiException
from pprint import pprint

# Configure API key authorization: bearer
configuration = subscription_client.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'
# Configure API key authorization: internal
configuration = subscription_client.Configuration()
configuration.api_key['X-API-Key'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['X-API-Key'] = 'Bearer'

# create an instance of the API class
api_instance = subscription_client.SubscriptionApi(subscription_client.ApiClient(configuration))
x_user_email = 'x_user_email_example' # str | Email of the user
subscription = subscription_client.Subscription() # Subscription | Subscription details

try:
    # Subscribe user
    api_response = api_instance.subscribe_user(x_user_email, subscription)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling SubscriptionApi->subscribe_user: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **x_user_email** | **str**| Email of the user | 
 **subscription** | [**Subscription**](Subscription.md)| Subscription details | 

### Return type

[**SubscriptionView**](SubscriptionView.md)

### Authorization

[bearer](../README.md#bearer), [internal](../README.md#internal)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

