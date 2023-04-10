from ibm.common.clients.softlayer_clients.base_client import SoftLayerClient
from .consts import SUMMARY_PERIOD_FOR_ONE_DAY, SUMMARY_PERIOD_FOR_TWELVE_HOURS


class SoftlayerMonitoringClient(SoftLayerClient):
    """
    Client for Softlayer Monitoring related APIs related to CPU usage, Memory Usage etc.
    """

    def __init__(self, cloud_id):
        super(SoftlayerMonitoringClient, self).__init__(cloud_id)

    def get_memory_usage(self, guest, start_date, end_date, summary_period=SUMMARY_PERIOD_FOR_ONE_DAY):
        """Formats and executes an API call to get memory usage data for a VM on Classic
        returns memory_records, which is the raw data returned from the API
        """
        valid_types = [{"keyName": "MEMORY_USAGE", "summaryType": "average", "unit": "GB"}]
        memory_records = self.client.call(
            'Metric_Tracking_Object', 'getSummaryData', start_date, end_date, valid_types, summary_period,
            id=guest['metricTrackingObjectId'])
        return memory_records

    def get_cpu_usage_per_cpu(self, guest, start_date, end_date, summary_period=SUMMARY_PERIOD_FOR_TWELVE_HOURS):
        """Makes an API call to get CPU usage data for a Virtual Machine on Classic
        Each CPU is tracked individually so its required to know how many CPUs a guest has
        returns cpu_records, which is the raw data returned from the API
        """
        cpu_records = list()
        for i in range(guest['startCpus']):
            valid_types = [{"keyName": "CPU" + str(i), "name": "cpu" + str(i), "summaryType": "max"}]
            result = self.client.call(
                'Metric_Tracking_Object', 'getSummaryData', start_date, end_date, valid_types, summary_period,
                id=guest['metricTrackingObjectId'])

            for entry in result:
                cpu_records.append(entry)

        return cpu_records

    def get_bandwidth_usage(
            self, guest, start_date, end_date, bandwidth_type="OUTBOUND",
            summary_period=SUMMARY_PERIOD_FOR_TWELVE_HOURS):
        """
        Makes an API call to get Bandwidth data for a virtual machine on classic infrastructure.
        """
        bandwidth_key = None
        if bandwidth_type == "OUTBOUND":
            bandwidth_key = "PUBLICOUT_NET_OCTET"
        elif bandwidth_type == "INBOUND":
            bandwidth_key = "PUBLICIN_NET_OCTET"

        valid_types = [{"keyName": bandwidth_key, "summaryType": "average"}]
        bandwidth_records = self.client.call(
            'Metric_Tracking_Object', 'getSummaryData', start_date, end_date, valid_types, summary_period,
            id=guest['metricTrackingObjectId'])

        return bandwidth_records

    def get_virtual_guests(self):
        """This method gets the basic data for each virtual guest on an account
        """
        mask = "mask[id, datacenter.longName, hostname, domain, metricTrackingObjectId, startCpus, maxMemory, " \
               "status, type, regionalGroup[name], operatingSystem[softwareLicense[softwareDescription[name, " \
               "manufacturer, version, longDescription]]], maxCpu]"
        return self.client.call('Account', 'getVirtualGuests', mask=mask)
