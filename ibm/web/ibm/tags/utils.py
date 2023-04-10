from ibm.models.ibm.tag_models import IBMTag

from ibm.web import db as ibmdb


def get_tags(resource_id, session=None):
    """
    Get a list of IBM Tags with resource id and resource type provided e.g. IBMVpc
    :return:
    """
    if not session:
        session = ibmdb.session

    return session.query(IBMTag).filter(IBMTag.resource_id == resource_id).all()
