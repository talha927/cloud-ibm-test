from ibm.models import IBMKubernetesCluster, IBMVpcNetwork

DRAAS_RESOURCE_TYPE_TO_MODEL_MAPPER = {
    IBMKubernetesCluster.__name__: IBMKubernetesCluster,
    IBMVpcNetwork.__name__: IBMVpcNetwork
}
