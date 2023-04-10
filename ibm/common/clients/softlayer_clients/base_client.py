import logging

import SoftLayer
from SoftLayer import SoftLayerAPIError
from tenacity import retry_if_exception_type, Retrying, stop_after_attempt, wait_random_exponential

from ibm import get_db_session
from ibm.common.clients.softlayer_clients.consts import BACK_OFF_FACTOR, INVALID_API_KEY_CODE, MAX_INTERVAL, RETRY, \
    SL_RATE_LIMIT_FAULT_CODE
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLRateLimitExceededError
from ibm.models import SoftlayerCloud

LOGGER = logging.getLogger(__name__)


class SoftLayerClient:
    """
    SoftLayerClient for softlayer apis
    """

    def __init__(self, cloud_id):
        self.cloud_id = cloud_id
        self.retry = self.requests_retry()

    @property
    def client(self):
        with get_db_session() as db_session:
            softlayer_cloud = db_session.query(SoftlayerCloud).filter_by(id=self.cloud_id).first()
            if not softlayer_cloud:
                raise SLAuthError(self.cloud_id)
        return SoftLayer.create_client_from_env(softlayer_cloud.username, softlayer_cloud.api_key)

    def requests_retry(self):
        self.retry = Retrying(
            stop=stop_after_attempt(RETRY),
            retry=retry_if_exception_type(SLRateLimitExceededError),
            wait=wait_random_exponential(multiplier=BACK_OFF_FACTOR, max=MAX_INTERVAL),
            reraise=True)
        return self.retry

    def authenticate_sl_account(self):
        """
        Authenticate SL accounts with provided credentials
        :return:
        """
        try:
            return self.retry.call(self.client.call, "Account", "getObject")
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)
