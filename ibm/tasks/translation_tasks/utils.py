from urllib.parse import urljoin

import requests

from config import TranslationConfig
from ibm.common.clients.ibm_clients.session_context import get_requests_session
from ibm.common.consts import AWS_CLOUD, AWS_HEADER, AWS_TRANSLATION_URL_TEMPLATE
from ibm.web.cloud_translations.aws_translator import AWSTranslator


def get_cloud_translation_json(task_metadata):
    """
    This function calls the respective cloud service and get the vpc data to translate.
    """
    if task_metadata['source_cloud']["type"] == AWS_CLOUD:
        service_header = AWS_HEADER
        template = AWS_TRANSLATION_URL_TEMPLATE.format(
            resource_id=task_metadata['resource']['id'], cloud_id=task_metadata['source_cloud']['id'],
            resource_type=task_metadata['resource']['type']
        )
    else:
        raise NotImplementedError(
            f"Translation from {task_metadata['source_cloud']['type']} to IBM is not implemented")

    url = urljoin(TranslationConfig.VPCPLUS_LINK, template)
    request = requests.Request("GET", url, headers=service_header)

    with get_requests_session() as req_session:
        request = req_session.prepare_request(request)
        return req_session.send(request, timeout=30)


def initiate_translation(cloud, task_metadata, data_to_translate, resource_group, region, db_image_name_obj_dict=None,
                         instance_profile=None, volume_profile=None, load_balancer_profiles=None):
    """
    This function initialize translation process.
    """
    if not db_image_name_obj_dict:
        db_image_name_obj_dict = dict()
    if not load_balancer_profiles:
        load_balancer_profiles = dict()
    if task_metadata['source_cloud']["type"] == AWS_CLOUD:
        translator = AWSTranslator(
            ibm_cloud=cloud, resource_group=resource_group, region=region,
            source_construct=data_to_translate, db_image_name_obj_dict=db_image_name_obj_dict,
            instance_profile=instance_profile,
            volume_profile=volume_profile, load_balancer_profiles=load_balancer_profiles,
        )
    else:
        raise NotImplementedError(
            f"Translation from {task_metadata['source_cloud']['type']} to IBM is not implemented"
        )

    translator.validate_translation_json()
    translator.execute_translation()
    return translator.to_translated_json(metadata=task_metadata.get("metadata"))
