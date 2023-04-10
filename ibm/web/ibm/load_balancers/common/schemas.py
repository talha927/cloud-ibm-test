from marshmallow import Schema
from marshmallow.fields import Integer, Nested, String
from marshmallow.validate import OneOf

from ibm.models.ibm.load_balancer_models import IBMListenerAndPolicyCommon


class IBMListenerHTTPSRedirectSchema(Schema):
    http_status_code = Integer(
        required=True, allow_none=False,
        validate=OneOf(
            list(map(lambda status_code: int(status_code), IBMListenerAndPolicyCommon.ALL_STATUS_CODES_LIST))),
        description="The HTTP status code for this redirect."
    )
    listener = Nested(
        "IBMResourceRefSchema",
        description="Identifies a load balancer listener by a unique property."
    )
    url = String(
        description="The redirect target URL.",
        example="https://www.redirect.com"
    )

    uri = String(
        description="The redirect relative target URI.",
        example="/example?doc=get"
    )
