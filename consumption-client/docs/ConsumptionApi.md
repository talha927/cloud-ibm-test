# consumption_client.ConsumptionApi

All URIs are relative to *http://localhost/v1*

Method | HTTP request | Description
------------- | ------------- | -------------
[**add_consumption**](ConsumptionApi.md#add_consumption) | **POST** /consumption | Add consumption details


# **add_consumption**
> ConsumptionView add_consumption(consumption)

Add consumption details

Add consumption details for a given user

### Example
```python
from __future__ import print_function
import time
import consumption_client
from consumption_client.rest import ApiException
from pprint import pprint

# Configure API key authorization: bearer
configuration = consumption_client.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'
# Configure API key authorization: internal
configuration = consumption_client.Configuration()
configuration.api_key['X-API-Key'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['X-API-Key'] = 'Bearer'

# create an instance of the API class
api_instance = consumption_client.ConsumptionApi(consumption_client.ApiClient(configuration))
consumption = consumption_client.Consumption() # Consumption | Consumption to be added

try:
    # Add consumption details
    api_response = api_instance.add_consumption(consumption)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ConsumptionApi->add_consumption: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **consumption** | [**Consumption**](Consumption.md)| Consumption to be added | 

### Return type

[**ConsumptionView**](ConsumptionView.md)

### Authorization

[bearer](../README.md#bearer), [internal](../README.md#internal)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

