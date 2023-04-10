# swagger-client
Manage subscriptions to services offered

This Python package is automatically generated by the [Swagger Codegen](https://github.com/swagger-api/swagger-codegen) project:

- API version: 0.2.0
- Package version: 1.0.0
- Build package: io.swagger.codegen.languages.PythonClientCodegen

## Requirements.

Python 2.7 and 3.4+

## Installation & Usage
### pip install

If the python package is hosted on Github, you can install directly from Github

```sh
pip install git+https://github.com//.git
```
(you may need to run `pip` with root permission: `sudo pip install git+https://github.com//.git`)

Then import the package:
```python
import subscription_client 
```

### Setuptools

Install via [Setuptools](http://pypi.python.org/pypi/setuptools).

```sh
python setup.py install --user
```
(or `sudo python setup.py install` to install the package for all users)

Then import the package:
```python
import subscription_client
```

## Getting Started

Please follow the [installation procedure](#installation--usage) and then run the following:

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

## Documentation for API Endpoints

All URIs are relative to *http://localhost/v1*

Class | Method | HTTP request | Description
------------ | ------------- | ------------- | -------------
*ServiceApi* | [**get_services**](docs/ServiceApi.md#get_services) | **GET** /services | Get services
*SubscriptionApi* | [**get_subscriptions**](docs/SubscriptionApi.md#get_subscriptions) | **GET** /subscriptions | Get subscriptions
*SubscriptionApi* | [**subscribe_user**](docs/SubscriptionApi.md#subscribe_user) | **POST** /subscriptions | Subscribe user


## Documentation For Models

 - [Audit](docs/Audit.md)
 - [Error](docs/Error.md)
 - [ServiceView](docs/ServiceView.md)
 - [Subscription](docs/Subscription.md)
 - [SubscriptionView](docs/SubscriptionView.md)


## Documentation For Authorization


## bearer

- **Type**: API key
- **API key parameter name**: Authorization
- **Location**: HTTP header

## internal

- **Type**: API key
- **API key parameter name**: X-API-Key
- **Location**: HTTP header


## Author


