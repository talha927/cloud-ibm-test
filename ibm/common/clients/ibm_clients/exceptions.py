import json

from requests.exceptions import RetryError


class IBMAuthError(Exception):
    """This exception is raised if: Cloud's credentials are invalid."""

    def __init__(self, cloud_id=None):
        self.msg = "Credentials not valid for IBM cloud {}".format(cloud_id or "SECRET")
        super(IBMAuthError, self).__init__(self.msg)


class IBMInvalidRequestError(Exception):
    """ Exception raised when cloud manager is asked to perform a task which is not doable"""

    def __init__(self, message):
        self.msg = message
        super(IBMInvalidRequestError, self).__init__(message)


class IBMConnectError(Exception):
    """ Exception raised when cloud manager can not connect to IBM Cloud"""

    def __init__(self, cloud_id=None):
        self.msg = "Unable to connect to IBM cloud {}".format(cloud_id or "SECRET")
        super(IBMConnectError, self).__init__(self.msg)


class IBMExecuteError(Exception):
    """ Exception raised when the request runs unsuccessfully. HTTP data was invalid or unexpected"""

    def __init__(self, error):
        self.msg, self.status_code, self.trace_id = None, None, None
        self.error_code = None
        try:
            if type(error).__name__ == RetryError.__name__:
                self.status_code = 500
                self.msg = error
            else:
                self.status_code = error.status_code
                data = json.loads(error.content.decode('utf-8'))
                if data:
                    self.trace_id = data.get("trace")
                    data = data.get('errors') or data.get('errorMessage') or data.get('description')
                    if isinstance(data, list) and len(data) > 0:
                        self.msg = data[0]['message']
                        self.error_code = data[0]["code"]
                    elif isinstance(data, dict):
                        self.msg = data['error']['message']
                        self.error_code = data["error"]["code"]
                    else:
                        self.msg = data

        except (ValueError, KeyError, TypeError):
            pass

        message = f"Operation failed, Error-Code: {self.status_code}, Error message: \n{self.msg}"
        if self.error_code:
            message += f"\nRead more about this error at {self.more_info}"
        super(IBMExecuteError, self).__init__(message)

    @property
    def more_info(self):
        return f"https://cloud.ibm.com/docs/vpc?topic=vpc-rias-error-messages#{self.error_code.replace('_', '-')}"
