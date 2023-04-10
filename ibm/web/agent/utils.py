import json

import requests
import yaml
from apiflask import abort

from ibm.web.agent.consts import AGENT_SERVICE_URL, GET_AGENT


class AgentClient(object):
    def __init__(self, base_url, api_path, method):
        self.base_url = base_url
        self.api_path = api_path
        self.method = method

    def _exec_api(self, body=None):
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json'
        }
        if body:
            response = requests.request(self.method, self.base_url + self.api_path, data=body, headers=headers)
        else:
            response = requests.request(self.method, self.base_url + self.api_path, headers=headers)
        return response


class AgentBody(object):
    def __init__(self, agent_id, user_id, method, cluster_creds):
        self.agent_id = agent_id
        self.user_id = user_id
        self.method = method
        self.cluster_creds = cluster_creds

    def make_json_request_body(self, api_path, payload=None):
        request = {
            "user_id": self.user_id,
            "url": self.cluster_creds['server'] + api_path,
            "headers": {
                "Accept": "application/json"
            },
            "payload": payload,
            "method": self.method,
            "tls": {
                "type": "x509",
                "cert_data": self.cluster_creds['client_certificate_data'],
                "key_data": self.cluster_creds['client_key_data']
            },
            "retries": 1,
            "type": "API",
            "timeout": 120
        }
        return json.dumps(request)


def make_json_request_body(user_id, api_path, cluster_creds, method, playload=None):
    request = {
        "user_id": user_id,
        "url": cluster_creds['server'] + api_path,
        "headers": {
            "Accept": "application/json"
        },
        "payload": playload,
        "method": method,
        "tls": {
            "type": "x509",
            "cert_data": cluster_creds['client_certificate_data'],
            "key_data": cluster_creds['client_key_data']
        },
        "retries": 1,
        "type": "API",
        "timeout": 120
    }
    return json.dumps(request)


def _execute_api(request_type, PATH, body=None):
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    if body:
        response = requests.request(request_type, AGENT_SERVICE_URL + PATH, data=body, headers=headers)
    else:
        response = requests.request(request_type, AGENT_SERVICE_URL + PATH, headers=headers)
    return response


def response_parser(response):
    res = json.loads(response)
    node_items = res['items']
    no_of_node = len(node_items)
    kube_version = node_items[0]['status']['nodeInfo']['kubeletVersion']
    data = {'worker_count': no_of_node, 'kube_version': kube_version}
    return data


def parse_yaml_file(file):
    _file = file.read()
    file_data = _file.decode("utf-8")
    load_yaml = yaml.load(file_data, Loader=yaml.FullLoader)
    try:
        data = {'server': load_yaml['clusters'][0]['cluster']['server'],
                'client_certificate_data': load_yaml['users'][1]['user']['client-certificate-data'],
                'client_key_data': load_yaml['users'][1]['user']['client-key-data']}
    except (KeyError, IndexError):
        data = {'server': load_yaml['clusters'][0]['cluster']['server'],
                'client_certificate_data': load_yaml['users'][0]['user']['client-certificate-data'],
                'client_key_data': load_yaml['users'][0]['user']['client-key-data']}

    return data


def agent_health(agent_id):
    client = AgentClient(AGENT_SERVICE_URL, GET_AGENT.format(agent_id=agent_id), "GET")
    response = client._exec_api()
    if not response:
        message = f"IBM Agent {agent_id} not found"
        abort(404, message)
        return

    agent = response.json()
    if agent and agent['status'] == 'UP':
        return True
    return False
