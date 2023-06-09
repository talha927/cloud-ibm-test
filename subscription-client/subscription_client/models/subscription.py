# coding: utf-8

"""
    Subscription-svc

    Manage subscriptions to services offered  # noqa: E501

    OpenAPI spec version: 0.2.0
    
    Generated by: https://github.com/swagger-api/swagger-codegen.git
"""


import pprint
import re  # noqa: F401

import six

from subscription_client.configuration import Configuration


class Subscription(object):
    """NOTE: This class is auto generated by the swagger code generator program.

    Do not edit the class manually.
    """

    """
    Attributes:
      swagger_types (dict): The key is attribute name
                            and the value is attribute type.
      attribute_map (dict): The key is attribute name
                            and the value is json key in definition.
    """
    swagger_types = {
        'user_id': 'str',
        'project_id': 'str',
        'service_id': 'str'
    }

    attribute_map = {
        'user_id': 'user_id',
        'project_id': 'project_id',
        'service_id': 'service_id'
    }

    def __init__(self, user_id=None, project_id=None, service_id=None, _configuration=None):  # noqa: E501
        """Subscription - a model defined in Swagger"""  # noqa: E501
        if _configuration is None:
            _configuration = Configuration()
        self._configuration = _configuration

        self._user_id = None
        self._project_id = None
        self._service_id = None
        self.discriminator = None

        if user_id is not None:
            self.user_id = user_id
        self.project_id = project_id
        self.service_id = service_id

    @property
    def user_id(self):
        """Gets the user_id of this Subscription.  # noqa: E501


        :return: The user_id of this Subscription.  # noqa: E501
        :rtype: str
        """
        return self._user_id

    @user_id.setter
    def user_id(self, user_id):
        """Sets the user_id of this Subscription.


        :param user_id: The user_id of this Subscription.  # noqa: E501
        :type: str
        """

        self._user_id = user_id

    @property
    def project_id(self):
        """Gets the project_id of this Subscription.  # noqa: E501


        :return: The project_id of this Subscription.  # noqa: E501
        :rtype: str
        """
        return self._project_id

    @project_id.setter
    def project_id(self, project_id):
        """Sets the project_id of this Subscription.


        :param project_id: The project_id of this Subscription.  # noqa: E501
        :type: str
        """
        if self._configuration.client_side_validation and project_id is None:
            raise ValueError("Invalid value for `project_id`, must not be `None`")  # noqa: E501

        self._project_id = project_id

    @property
    def service_id(self):
        """Gets the service_id of this Subscription.  # noqa: E501


        :return: The service_id of this Subscription.  # noqa: E501
        :rtype: str
        """
        return self._service_id

    @service_id.setter
    def service_id(self, service_id):
        """Sets the service_id of this Subscription.


        :param service_id: The service_id of this Subscription.  # noqa: E501
        :type: str
        """
        if self._configuration.client_side_validation and service_id is None:
            raise ValueError("Invalid value for `service_id`, must not be `None`")  # noqa: E501

        self._service_id = service_id

    def to_dict(self):
        """Returns the model properties as a dict"""
        result = {}

        for attr, _ in six.iteritems(self.swagger_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, "to_dict") else x,
                    value
                ))
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], "to_dict") else item,
                    value.items()
                ))
            else:
                result[attr] = value
        if issubclass(Subscription, dict):
            for key, value in self.items():
                result[key] = value

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, Subscription):
            return False

        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        if not isinstance(other, Subscription):
            return True

        return self.to_dict() != other.to_dict()
