DRAAS_BACKUP_NOT_FOUND_ERROR = "No Disaster Recovery Backup with ID '{id}' found for the user"
DRAAS_RESOURCE_TO_BACKUP_404 = "No Disaster Recovery Resource to backup with ID {id} and type {type} found " \
                               "for the user"
BACKUP_ALREADY_EXISTS_ERROR = "Backup already exists with the name '{name}'"
BACKUP_ALREADY_MARKED_FOR_DELETION_ERROR = "A backup with 'name' is already marked for 'DELETION'."
DRAAS_BACKUP_OCCUPIED = "There is a Backup in status: {state} with ID: {id}"
KUBERNETES_BACKUP = "KUBERNETES_BACKUP"
KUBERNETES_SCHEDULE = "KUBERNETES_SCHEDULE"
KUBERNETES_DISASTER_RECOVERY = "KUBERNETES_DISASTER_RECOVERY"
VELERO_INST_FAILED = "Velero could not be installed, kindly check internet connectivity of cluster and check the CPU " \
                     "and Memory Limit and Requests "
BACKUP_CREATION_ERROR = "Unable to create backup "
BACKUP_DELETION_ERROR = "Unable to delete the backup "
SCHEDULE_CREATION_ERROR = "Unable to create kubernetes schedule "
SCHEDULE_DELETION_ERROR = "Unable to delete kubernetes schedule "
DISASTER_RECOVERY_WORKFLOW_ERROR = "Unable to create Disaster recovery for the cluster "
DISASTER_RECOVERY_WORKFLOW_DELETION_ERROR = "Unable to delete Disaster recovery for the cluster "
BUCKET_DELETION_ERROR = "Unable to delete backup from bucket "
BUCKET_CREATION_ERROR = "Unable to create a bucket"

RESOURCE_TYPE_IBM_VPC_NETWORK = "IBMVpcNetwork"
RESOURCE_TYPE_IKS = "IKS"
