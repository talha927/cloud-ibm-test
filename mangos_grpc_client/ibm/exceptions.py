class MangosIBMCloudNotFoundError(Exception):
    """This exception is raised if: IBM cloud with provided api_key_id is not found in Mangos"""

    def __init__(self, api_key_id):
        self.msg = "Cloud with api_key_id {} not found in mangoS".format(api_key_id)
        super(MangosIBMCloudNotFoundError, self).__init__(self.msg)


class MangosIBMCloudNotSyncedError(Exception):
    """ Exception raised when mangos has not yet synced cloud with provided api_key_id"""

    def __init__(self, api_key_id):
        self.msg = "Cloud with api_key_id {} not synced by mangoS yet".format(api_key_id)
        super(MangosIBMCloudNotSyncedError, self).__init__(self.msg)


class MangosGRPCError(Exception):
    """ Exception raised when an error related to GRPC is raised"""

    def __init__(self, error):
        self.msg = error
        super(MangosGRPCError, self).__init__(self.msg)
