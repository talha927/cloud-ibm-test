import collections

import grpc

from mangos_grpc_client.ibm.mangos_ibm_client import MangosGRPCIBMClient, MangosGRPCIBMClient

client_types = {
    'MangosIBMGRPCClientConfigs': MangosGRPCIBMClient,
}


class _GenericClientInterceptor(grpc.UnaryUnaryClientInterceptor,
                                grpc.UnaryStreamClientInterceptor,
                                grpc.StreamUnaryClientInterceptor,
                                grpc.StreamStreamClientInterceptor):

    def __init__(self, interceptor_function):
        self._fn = interceptor_function

    def intercept_unary_unary(self, continuation, client_call_details, request):
        new_details, new_request_iterator, postprocess = self._fn(
            client_call_details, iter((request,)), False, False)
        response = continuation(new_details, next(new_request_iterator))
        return postprocess(response) if postprocess else response

    def intercept_unary_stream(self, continuation, client_call_details,
                               request):
        new_details, new_request_iterator, postprocess = self._fn(
            client_call_details, iter((request,)), False, True)
        response_it = continuation(new_details, next(new_request_iterator))
        return postprocess(response_it) if postprocess else response_it

    def intercept_stream_unary(self, continuation, client_call_details,
                               request_iterator):
        new_details, new_request_iterator, postprocess = self._fn(
            client_call_details, request_iterator, True, False)
        response = continuation(new_details, new_request_iterator)
        return postprocess(response) if postprocess else response

    def intercept_stream_stream(self, continuation, client_call_details,
                                request_iterator):
        new_details, new_request_iterator, postprocess = self._fn(
            client_call_details, request_iterator, True, True)
        response_it = continuation(new_details, new_request_iterator)
        return postprocess(response_it) if postprocess else response_it


class _ClientCallDetails(
    collections.namedtuple(
        '_ClientCallDetails',
        ('method', 'timeout', 'metadata', 'credentials')),
    grpc.ClientCallDetails):
    pass


def header_adder_interceptor(header, value):
    def intercept_call(client_call_details, request_iterator, request_streaming,
                       response_streaming):
        metadata = []
        if client_call_details.metadata is not None:
            metadata = list(client_call_details.metadata)
        metadata.append((
            header,
            value,
        ))
        client_call_details = _ClientCallDetails(
            client_call_details.method, client_call_details.timeout, metadata,
            client_call_details.credentials)
        return client_call_details, request_iterator, None

    return _GenericClientInterceptor(intercept_call)


class GrpcAuth(grpc.AuthMetadataPlugin):
    def __init__(self, key):
        self._key = key

    def __call__(self, context, callback):
        callback((('api-key', self._key),), None)


def create_mangos_client(config):
    from grpc._cython.cygrpc import CompressionAlgorithm
    from grpc._cython.cygrpc import CompressionLevel

    options = [
        ("grpc.max_send_message_length", config.GRPC_MAX_MESSAGE_SIZE),
        ("grpc.max_receive_message_length", config.GRPC_MAX_MESSAGE_SIZE),
        ("grpc.default_compression_algorithm", CompressionAlgorithm.gzip),
        ("grpc.default_compression_level", CompressionLevel.high),
    ]
    if config.USE_TLS == "true":
        with open("/etc/ssl/certs/ca-certificates.crt", 'rb') as f:
            creds = grpc.ssl_channel_credentials(root_certificates=f.read())

        channel = grpc.secure_channel(
            config.MANGOS_GRPC_URL,
            grpc.composite_channel_credentials(
                creds, grpc.metadata_call_credentials(GrpcAuth(config.ENV_MANGOS_IBM_GRPC_API_KEY))
            ),
            options=options
        )
    else:
        channel = grpc.insecure_channel(
            config.MANGOS_GRPC_URL,
            options=options
        )
        header_adder_interceptor_ = header_adder_interceptor(
            'api-key', config.ENV_MANGOS_IBM_GRPC_API_KEY)

        channel = grpc.intercept_channel(channel, header_adder_interceptor_)

    mangos_grpc_client = client_types[config.__name__](channel)
    return mangos_grpc_client


__all__ = [
    "create_mangos_client"
]
