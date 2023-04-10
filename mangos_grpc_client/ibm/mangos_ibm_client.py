import json

import grpc

from mangos_grpc_client.ibm.exceptions import MangosGRPCError, MangosIBMCloudNotFoundError, MangosIBMCloudNotSyncedError
from mangos_grpc_client.ibm.proto_files import ibm_responses_grpc_def_pb2, ibm_responses_grpc_def_pb2_grpc


class MangosGRPCIBMClient:

    def __init__(self, channel):
        self.stub = ibm_responses_grpc_def_pb2_grpc.IBMResponseCallsStub(channel)
        self.channel = channel

    def add_cloud(self, api_key, api_key_id, account_id):
        message = ibm_responses_grpc_def_pb2.AddCloudRequest(api_key=api_key, api_key_id=api_key_id,
                                                             account_id=account_id)
        response = self.__execute(self.stub.add_cloud, message)
        return response.id

    def get_clouds(self):
        message = ibm_responses_grpc_def_pb2.EmptyRequest()
        response = self.__execute(self.stub.get_clouds, message)
        return response.clouds

    def delete_cloud(self, api_key_id):
        message = ibm_responses_grpc_def_pb2.DeleteCloudRequest(api_key_id=api_key_id)
        response = self.__execute(self.stub.delete_cloud, message)
        return response.status

    def get_resources(self, filterable_parent_resource_id, api_key_id, resource_types_in=None,
                      resource_types_not_in=None):
        if not resource_types_in:
            resource_types_in = list()
        if not resource_types_not_in:
            resource_types_not_in = list()

        message = ibm_responses_grpc_def_pb2.ResourceRequest(
            filterable_parent_resource_id=filterable_parent_resource_id, api_key_id=api_key_id,
            resource_types_in=resource_types_in, resource_types_not_in=resource_types_not_in)

        response = self.__execute(self.stub.get_resources, message)
        return json.loads(response.data)

    def __execute(self, stub_method, message):
        try:
            response = stub_method(message)
        except grpc.RpcError as e:
            raise MangosGRPCError(str(e.details()))
        else:
            if response.status in {201, 200}:
                return response
            elif response.status == 404:
                raise MangosIBMCloudNotFoundError(message.api_key_id)
            elif response.status == 204:
                raise MangosIBMCloudNotSyncedError(message.api_key_id)
