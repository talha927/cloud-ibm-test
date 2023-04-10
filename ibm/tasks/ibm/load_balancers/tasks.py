from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import LoadBalancersClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMCloud, IBMIdleResource, IBMInstance, IBMListener, IBMLoadBalancer, IBMLoadBalancerProfile, \
    IBMNetworkInterface, IBMPool, IBMPoolMember, IBMRegion, IBMResourceGroup, IBMSecurityGroup, IBMSubnet, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.load_balancers.schemas import IBMLoadBalancerInSchema, IBMLoadBalancerResourceSchema


@celery.task(name="create_load_balancer", base=IBMWorkflowTasksBase)
def create_load_balancer(workflow_task_id):
    """
    Create an IBM Load Balancer on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        profile_json = resource_json["profile"]
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]

        region = db_session.query(IBMRegion).filter_by(id=resource_data["region"]["id"], cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        lb_profile: IBMLoadBalancerProfile = db_session.query(IBMLoadBalancerProfile).filter_by(**profile_json).first()
        if not lb_profile:
            LOGGER.error("""
            Please sync the load_balancer profiles first.
            1. POST SERVER_URL/v1/ibm/load_balancer/profiles/sync
            2. GET SERVER_URL/v1/ibm/load_balancer/profiles
            """)
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            return

        if lb_profile.family == "Application":
            del resource_json["profile"]

        member_resource_json_list = []
        target_id_or_address_to_subnet_id_dict = {}
        for pool_resource_json in resource_json.get("pools", []):
            member_resource_json_list.extend(pool_resource_json.get("members", []))

        member_name_id_dict = {}
        for member_resource_json in member_resource_json_list:
            target = member_resource_json["target"]
            target_id = target["id"]
            if member_resource_json["target"]["type"] == "instance":
                instance = db_session.query(IBMInstance).filter_by(id=target_id, cloud_id=cloud_id).first()
                if not instance:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = f"IBM Instance with id: '{target_id}' not found"
                    db_session.commit()
                    LOGGER.error(workflow_task.message)
                    return

                member_resource_json["target"]["id"] = instance.resource_id
                member_name_id_dict[instance.resource_id] = member_resource_json
                target_id_or_address_to_subnet_id_dict[instance.resource_id] = target["subnet"]["id"]

            elif member_resource_json["target"]["type"] == "network_interface":
                network_interface = db_session.query(IBMNetworkInterface). \
                    filter_by(id=target_id, cloud_id=cloud_id).first()
                if not network_interface:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = f"IBMNetworkInterface with id: '{target_id}' not found"
                    db_session.commit()
                    LOGGER.error(workflow_task.message)
                    return

                address = network_interface.primary_ipv4_address
                member_resource_json["target"]["address"] = address
                member_name_id_dict[address] = member_resource_json
                target_id_or_address_to_subnet_id_dict[address] = target["subnet"]["id"]

            if "id" in member_resource_json:
                del member_resource_json["id"]

            del member_resource_json["target"]["type"]
            del member_resource_json["target"]["subnet"]

        region_name = region.name

        # This is not required but would help with code consistency
        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMLoadBalancerInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMLoadBalancerResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        for listener_json in resource_json.get("listeners", []):
            if "id" in listener_json:
                del listener_json["id"]

        for pool_json in resource_json.get("pools", []):
            if "id" in pool_json:
                del pool_json["id"]

    try:
        client = LoadBalancersClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_load_balancer(load_balancer_json=resource_json)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.error(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        load_balancer_status = resp_json["provisioning_status"]
        load_balancer_name = resp_json["name"]
        load_balancer_resource_id = resp_json["id"]
        if load_balancer_status in [IBMLoadBalancer.PROVISIONING_STATUS_ACTIVE,
                                    IBMLoadBalancer.PROVISIONING_STATUS_CREATE_PENDING]:
            metadata = deepcopy(workflow_task.task_metadata)
            metadata["target_id_or_address_to_subnet_id_dict"] = target_id_or_address_to_subnet_id_dict
            metadata["member_name_id_dict"] = member_name_id_dict
            metadata["ibm_resource_id"] = load_balancer_resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Load Balancer {load_balancer_name} for cloud {cloud_id} creation waiting"
            LOGGER.info(message)
        else:
            message = f"IBM Load Balancer {load_balancer_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.error(message)

        db_session.commit()


@celery.task(name="create_wait_load_balancer", base=IBMWorkflowTasksBase)
def create_wait_load_balancer(workflow_task_id):
    """
    Wait for an IBM Load Balancer creation on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]
        target_id_or_address_to_subnet_id_dict = workflow_task.task_metadata["target_id_or_address_to_subnet_id_dict"]
        member_name_id_dict = workflow_task.task_metadata["member_name_id_dict"]

        listener_json_port_protocol_dict = {}
        for listener_json in resource_json.get("listeners", []):
            listener_json_port_protocol_dict[f"{listener_json['port']}-{listener_json['protocol']}"] = listener_json

        pool_json_name_dict = {}
        for pool_json in resource_json.get("pools", []):
            pool_json_name_dict[pool_json["name"]] = pool_json

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = region.name
        resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = LoadBalancersClient(cloud_id=cloud_id, region=region_name)
        load_balancer_json = client.get_load_balancer(load_balancer_id=resource_id)
        if load_balancer_json["provisioning_status"] == IBMLoadBalancer.PROVISIONING_STATUS_ACTIVE:
            profile_json = client.get_load_balancer_profile(
                profile_name=load_balancer_json['profile']['name']
            )
            listeners_json_list = client.list_load_balancer_listeners(load_balancer_id=resource_id)
            pools_json_list = client.list_load_balancer_pools(load_balancer_id=resource_id)
            pool_id_members_json_dict = {}
            for pool in pools_json_list:
                pool_id_members_json_dict[pool['id']] = \
                    client.list_load_balancer_pool_members(resource_id, pool["id"])

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.error(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        load_balancer_status = load_balancer_json["provisioning_status"]
        load_balancer_name = load_balancer_json["name"]
        if load_balancer_status == IBMLoadBalancer.PROVISIONING_STATUS_ACTIVE:
            with db_session.no_autoflush:
                region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
                resource_group = \
                    db_session.query(IBMResourceGroup).filter_by(
                        resource_id=load_balancer_json["resource_group"]["id"], cloud_id=cloud_id
                    ).first()
                if not (resource_group and region):
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery runs"
                    db_session.commit()
                    LOGGER.note(workflow_task.message)
                    return

                load_balancer = IBMLoadBalancer.from_ibm_json_body(json_body=load_balancer_json)
                for subnet in load_balancer_json["subnets"]:
                    ibm_subnet = \
                        db_session.query(IBMSubnet).filter_by(
                            resource_id=subnet["id"], cloud_id=cloud_id
                        ).first()
                    if not ibm_subnet:
                        workflow_task.status = WorkflowTask.STATUS_FAILED
                        workflow_task.message = \
                            "Creation Successful but record update failed. The records will update next time " \
                            "discovery runs"
                        db_session.commit()
                        LOGGER.note(workflow_task.message)
                        return
                    load_balancer.subnets.append(ibm_subnet)

                for security_group in load_balancer_json["security_groups"]:
                    ibm_security_group = \
                        db_session.query(IBMSecurityGroup).filter_by(
                            resource_id=security_group["id"], cloud_id=cloud_id
                        ).first()
                    if not ibm_security_group:
                        workflow_task.status = WorkflowTask.STATUS_FAILED
                        workflow_task.message = \
                            "Creation Successful but record update failed. The records will update next time " \
                            "discovery runs"
                        db_session.commit()
                        LOGGER.note(workflow_task.message)
                        return
                    load_balancer.security_groups.append(ibm_security_group)

                load_balancer_profile = db_session.query(IBMLoadBalancerProfile).filter_by(
                    name=profile_json["name"]
                ).first()
                if not load_balancer_profile:
                    load_balancer_profile = IBMLoadBalancerProfile.from_ibm_json_body(profile_json)
                    load_balancer_profile.region = region

                load_balancer.load_balancer_profile = load_balancer_profile

                pool_resource_id_obj_dict = {}
                for pool_json in pools_json_list:
                    pool = IBMPool.from_ibm_json_body(pool_json)
                    fe_pool_json = pool_json_name_dict[pool.name]
                    if "id" in fe_pool_json:
                        pool.id = fe_pool_json["id"]

                    pool.region = region
                    for member_json in pool_id_members_json_dict[pool.resource_id]:
                        pool_member = IBMPoolMember.from_ibm_json_body(member_json)
                        target_id_or_address = member_json["target"].get("id") or pool_member.target_ip_address
                        fe_member_json = member_name_id_dict[target_id_or_address]
                        if "id" in fe_member_json:
                            pool_member.id = fe_member_json["id"]

                        subnet_id = target_id_or_address_to_subnet_id_dict[target_id_or_address]
                        if member_json["target"].get("id"):
                            instance = db_session.query(IBMInstance). \
                                filter_by(resource_id=member_json["target"]["id"]).first()
                            pool_member.instance = instance

                        pool_member.subnet_id = subnet_id
                        pool.members.append(pool_member)
                    pool_resource_id_obj_dict[pool.resource_id] = pool
                    load_balancer.pools.append(pool)

                for listener_json in listeners_json_list:
                    listener = IBMListener.from_ibm_json_body(listener_json, db_session)
                    fe_listener_json = listener_json_port_protocol_dict[f"{listener.port}-{listener.protocol}"]
                    if "id" in fe_listener_json:
                        listener.id = fe_listener_json["id"]

                    if "default_pool" in listener_json:
                        listener.default_pool = pool_resource_id_obj_dict[listener_json["default_pool"]["id"]]

                    listener.region = region
                    load_balancer.listeners.append(listener)

                check_load_balancer = db_session.query(IBMLoadBalancer).filter_by(cloud_id=cloud_id,
                                                                                  resource_id=load_balancer.resource_id,
                                                                                  region_id=region.id).first()
                load_balancer_id = load_balancer.id
                if check_load_balancer:
                    workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                    workflow_task.resource_id = load_balancer_id
                    message = f"IBM Load Balancer {load_balancer_name} for cloud {cloud_id} creation successful"
                    LOGGER.success(message)
                else:
                    load_balancer.region = region
                    load_balancer.resource_group = resource_group
                    db_session.commit()
                    workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                    workflow_task.resource_id = load_balancer_id
                    message = f"IBM Load Balancer {load_balancer_name} for cloud {cloud_id} creation successful"
                    LOGGER.success(message)
        elif load_balancer_status == IBMLoadBalancer.PROVISIONING_STATUS_CREATE_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Load Balancer {load_balancer_name} for cloud {cloud_id} creation waiting"
            LOGGER.info(message)
        else:
            message = f"IBM Load Balancer {load_balancer_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.error(message)

        db_session.commit()


@celery.task(name="delete_load_balancer", base=IBMWorkflowTasksBase)
def delete_load_balancer(workflow_task_id):
    """
    Delete an IBM Load Balancer
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        load_balancer: IBMLoadBalancer = db_session.get(IBMLoadBalancer, workflow_task.resource_id)
        if not load_balancer:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMLoadBalancer '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cloud_id = load_balancer.cloud_id
        region_name = load_balancer.region.name
        load_balancer_resource_id = load_balancer.resource_id

    try:
        load_balancer_client = LoadBalancersClient(cloud_id, region=region_name)
        load_balancer_client.delete_load_balancer(load_balancer_resource_id)
        load_balancer_json = load_balancer_client.get_load_balancer(load_balancer_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                load_balancer: IBMLoadBalancer = db_session.get(IBMLoadBalancer, workflow_task.resource_id)
                db_session.query(IBMIdleResource).filter_by(cloud_id=load_balancer.cloud_id,
                                                            db_resource_id=load_balancer.id).delete()
                if load_balancer:
                    db_session.delete(load_balancer)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM Load Balancer {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = \
                    f"Cannot delete the load balancer {workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.error(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        load_balancer_status = load_balancer_json["provisioning_status"]
        load_balancer_name = load_balancer_json["name"]
        if load_balancer_status in [IBMLoadBalancer.PROVISIONING_STATUS_DELETE_PENDING,
                                    IBMLoadBalancer.PROVISIONING_STATUS_UPDATE_PENDING,
                                    IBMLoadBalancer.PROVISIONING_STATUS_MAINTENANCE_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Load Balancer {load_balancer_name} for cloud {cloud_id} deletion waiting"
            LOGGER.info(message)
        else:
            message = f"IBM Load Balancer {load_balancer_name} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.error(message)

        db_session.commit()


@celery.task(name="delete_wait_load_balancer", base=IBMWorkflowTasksBase)
def delete_wait_load_balancer(workflow_task_id):
    """
    Wait for an IBM Load Balancer deletion on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        load_balancer: IBMLoadBalancer = db_session.get(IBMLoadBalancer, workflow_task.resource_id)
        if not load_balancer:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.success(f"IBMLoadBalancer '{workflow_task.resource_id}' deletion successful.")
            return

        cloud_id = load_balancer.cloud_id
        region_name = load_balancer.region.name
        load_balancer_resource_id = load_balancer.resource_id

    load_balancer_client = LoadBalancersClient(cloud_id, region=region_name)
    try:
        resp_json = load_balancer_client.get_load_balancer(load_balancer_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                load_balancer: IBMLoadBalancer = db_session.get(IBMLoadBalancer, workflow_task.resource_id)

                db_session.query(IBMIdleResource).filter_by(cloud_id=load_balancer.cloud_id,
                                                            db_resource_id=load_balancer.id).delete()
                if load_balancer:
                    db_session.delete(load_balancer)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM Load Balancer {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")

                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = \
                    f"Cannot delete the load balancer {workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.error(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        load_balancer_name = resp_json["name"]
        if resp_json["provisioning_status"] in [IBMLoadBalancer.PROVISIONING_STATUS_DELETE_PENDING,
                                                IBMLoadBalancer.PROVISIONING_STATUS_UPDATE_PENDING,
                                                IBMLoadBalancer.PROVISIONING_STATUS_MAINTENANCE_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Load Balancer {load_balancer_name} for cloud {cloud_id} deletion waiting"
            LOGGER.info(message)
        else:
            message = f"IBM Load Balancer {load_balancer_name} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.error(message)

        db_session.commit()


@celery.task(name="sync_load_balancer_profiles", base=IBMWorkflowTasksBase)
def sync_load_balancer_profiles(workflow_task_id):
    """
    Sync all IBM Load Balancer Profiles
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["cloud_id"]
        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        regions_list = db_session.query(IBMRegion.id, IBMRegion.name).filter_by(cloud_id=cloud_id).all()
        if not regions_list:
            LOGGER.error(f"No Regions found for IBMCloud '{cloud_id}'")
            return

    lb_profile_name_json_dict = {}
    for region_id, region_name in regions_list:
        LOGGER.info(f"Syncing Load Balancer Profiles for '{region_name}'")
        try:
            load_balancer_client = LoadBalancersClient(cloud_id=cloud_id, region=region_name)
            load_balancer_profiles_list = load_balancer_client.list_load_balancer_profiles()
        except ApiException as ex:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"Syncing Failed. Reason: {str(ex.message)}"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return
        else:
            for lb_profile_json in load_balancer_profiles_list:
                if lb_profile_name_json_dict.get(lb_profile_json["name"]):
                    continue

                lb_profile_name_json_dict[lb_profile_json["name"]] = lb_profile_json

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        load_balancer_profiles_list = []
        for _, profile_json in lb_profile_name_json_dict.items():
            ibm_load_balancer_profile = \
                db_session.query(IBMLoadBalancerProfile).filter_by(name=profile_json["name"]).first()

            load_balancer_profile = IBMLoadBalancerProfile.from_ibm_json_body(profile_json)
            if ibm_load_balancer_profile:
                ibm_load_balancer_profile.update_from_obj(load_balancer_profile)
                db_session.commit()
                continue

            load_balancer_profiles_list.append(profile_json)

            db_session.add(load_balancer_profile)
            db_session.commit()

        workflow_task.resource_id = cloud_id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.result = {"resource_json": load_balancer_profiles_list}
        db_session.commit()
    LOGGER.success(f"IBM Load Balancer Profiles synced successfully for '{cloud_id}'.")
