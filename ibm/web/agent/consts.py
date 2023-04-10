import os

AGENT_SERVICE_URL = os.environ.get("AGENT_SERVICE_URL", "https://draas-stage.wanclouds.net/")
POST_AGENT_TASK_PATH = '/v1/tasks/api/{agent_id}'
GET_AGENT_PATH = '/v1/agents?user_id={user_id}'
GET_AGENT = '/v1/internal/agents/{agent_id}'
GET_NODES = '/api/v1/nodes'
GET_NAMESPACES = '/api/v1/namespaces'
GET_NAMESPACES_PODS = '/api/v1/namespaces/{namespace}/pods'
GET_NAMESPACES_PVC = '/api/v1/namespaces/{namespace}/persistentvolumeclaims'
GET_NAMESPACES_SVC = '/api/v1/namespaces/{namespace}/services'
GET_STORAGE_CLASSES = '/apis/storage.k8s.io/v1/storageclasses'
GET_STORAGE_CLASS_BY_NAME = '/apis/storage.k8s.io/v1/storageclasses/{storageclass_name}'
