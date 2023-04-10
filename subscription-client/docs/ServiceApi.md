# subscription_client.ServiceApi

All URIs are relative to *http://localhost/v1*

Method | HTTP request | Description
------------- | ------------- | -------------
[**get_services**](ServiceApi.md#get_services) | **GET** /services | Get services


# **get_services**
> list[ServiceView] get_services(name=name, type=type, external_id=external_id)

Get services

Get services offered

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
api_instance = subscription_client.ServiceApi(subscription_client.ApiClient(configuration))
name = 'name_example' # str | Name of the service (optional)
type = 'type_example' # str | Type of the service (optional)
external_id = 'external_id_example' # str | External identifier associated with the service (optional)

try:
    # Get services
    api_response = api_instance.get_services(name=name, type=type, external_id=external_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ServiceApi->get_services: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **name** | **str**| Name of the service | [optional] 
 **type** | **str**| Type of the service | [optional] 
 **external_id** | **str**| External identifier associated with the service | [optional] 

### Return type

[**list[ServiceView]**](ServiceView.md)

### Authorization

[bearer](../README.md#bearer), [internal](../README.md#internal)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

