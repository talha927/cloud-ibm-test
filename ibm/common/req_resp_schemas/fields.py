import re

from marshmallow import ValidationError
from marshmallow.fields import String


class IPv4CIDR(String):
    IPv4CIDR_REGEX = r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4]" \
                     r"[0-9]|25[0-5])(\/(3[0-2]|[1-2][0-9]|[0-9]))$"

    def _serialize(self, value, attr, obj, **kwargs):
        ret_val = super(IPv4CIDR, self)._serialize(value, attr, obj, **kwargs)
        if ret_val and not re.match(pattern=self.IPv4CIDR_REGEX, string=value):
            raise ValidationError(f"'{value}' is not a valid IPv4CIDR")

        return ret_val

    def _deserialize(self, value, attr, data, **kwargs):
        ret_val = super(IPv4CIDR, self)._deserialize(value, attr, data, **kwargs)
        if ret_val and not re.match(pattern=self.IPv4CIDR_REGEX, string=value):
            raise ValidationError(f"'{value}' is not a valid IPv4CIDR")

        return ret_val


class IPv4(String):
    IPv4_REGEX = r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4]" \
                 r"[0-9]|25[0-5])$"

    def _serialize(self, value, attr, obj, **kwargs):
        ret_val = super(IPv4, self)._serialize(value, attr, obj, **kwargs)
        if ret_val and not re.match(pattern=self.IPv4_REGEX, string=value):
            raise ValidationError(f"'{value}' is not a valid IPv4 Address")

        return ret_val

    def _deserialize(self, value, attr, data, **kwargs):
        ret_val = super(IPv4, self)._deserialize(value, attr, data, **kwargs)
        if ret_val and not re.match(pattern=self.IPv4_REGEX, string=value):
            raise ValidationError(f"'{value}' is not a valid IPv4 Address")

        return ret_val
