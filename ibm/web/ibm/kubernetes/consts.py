from config import VeleroConfig

NAMESPACES = ["kube-system", "kube-public", "ibm-cert-store", "ibm-operators", "kube-node-lease", "ibm-system",
              "ibm-observe", "calico-system", "ibm-odf-validation-webhook", "openshift", "openshift-apiserver",
              "openshift-apiserver-operator", "openshift-authentication", "openshift-authentication-operator",
              "openshift-cloud-credential-operator", "openshift-cluster-csi-drivers",
              "openshift-cluster-machine-approver", "openshift-cluster-node-tuning-operator",
              "openshift-cluster-samples-operator", "openshift-cluster-storage-operator", "openshift-cluster-version",
              "openshift-config", "openshift-config-managed", "openshift-config-operator", "openshift-console",
              "openshift-console-operator", "openshift-console-user-settings", "openshift-controller-manager",
              "openshift-controller-manager-operator", "openshift-dns", "openshift-dns-operator", "openshift-etcd",
              "openshift-etcd-operator", "openshift-image-registry", "openshift-infra", "openshift-ingress",
              "openshift-ingress-canary", "openshift-ingress-operator", "openshift-insights", "openshift-kni-infra",
              "openshift-kube-apiserver", "openshift-kube-apiserver-operator", "openshift-kube-controller-manager",
              "openshift-kube-controller-manager-operator", "openshift-kube-proxy", "openshift-kube-scheduler",
              "openshift-kube-scheduler-operator", "openshift-kube-storage-version-migrator",
              "openshift-kube-storage-version-migrator-operator", "openshift-machine-api",
              "openshift-machine-config-operator", "openshift-marketplace", "openshift-monitoring", "openshift-multus",
              "openshift-network-diagnostics", "openshift-network-operator", "openshift-node",
              "openshift-openstack-infra", "openshift-operator-lifecycle-manager", "openshift-operators",
              "openshift-ovirt-infra", "openshift-roks-metrics", "openshift-service-ca",
              "openshift-service-ca-operator", "openshift-user-workload-monitoring", "openshift-vsphere-infra",
              "tigera-operator"]

VELERO_SERVER_URL = VeleroConfig.VELERO_URL
VELERO_HEADERS = {'x-api-key': VeleroConfig.VELERO_API_KEY}

BACKUP = "Backup"
RESTORE = "Restore"

BACKUP_FAILURE_ERROR_MSG = "An internal error occurred while taking backup of the cluster"
RESTORE_FAILURE_ERROR_MSG = "An internal error occurred while restoring the backup"

CLASSIC_BLOCK_STORAGE_CLASSES = ['ibmc-block-bronze', 'ibmc-block-retain-bronze', 'ibmc-block-retain-silver',
                                 'ibmc-block-silver', 'ibmc-block-gold', 'ibmc-block-retain-gold']

CLASSIC_FILE_STORAGE_CLASSES = ["default", 'ibmc-file-bronze', 'ibmc-file-bronze-gid', 'ibmc-file-custom',
                                'ibmc-file-gold', 'ibmc-file-gold-gid', 'ibmc-file-retain-bronze',
                                'ibmc-file-retain-custom', 'ibmc-file-retain-gold', 'ibmc-file-retain-silver',
                                'ibmc-file-silver', 'ibmc-file-silver-gid']

velero_payload = {

    "cluster_name": "", "source_cloud": "IBMCLASSIC", "target_cloud": "IBMVPC", "meta_data": {}, "kube_config": {},
    "hmac": {"access_key_id": "", "secret_access_key": ""}

}

PVC_PAYLOAD = {"name": "", "namespace": "", "provisioner": "", "size": "", "storageClassName": ""}
