from ibm.common.consts import classical_vpc_image_dictionary
from ibm.models import IBMImage
from ibm.web import db as ibmdb


def return_operating_system_objects(image_name, region_id, db_session=None, architecture=False):
    if not db_session:
        db_session = ibmdb.session
    os_list = []
    operating_systems = classical_vpc_image_dictionary.get(image_name)
    # TODO cloud_id is nice to have
    for os_name in operating_systems or []:
        for img in db_session.query(IBMImage).filter(
                IBMImage.name.ilike(f'%{os_name}%'),
                IBMImage.region_id == region_id,
                IBMImage.visibility == IBMImage.TYPE_VISIBLE_PUBLIC
        ).all():
            if architecture:
                data = {}
                data["image"] = img.to_reference_json()
                if img.operating_system:
                    data["operating_system"] = img.operating_system.to_reference_json(architecture=architecture)
                os_list.append(data)
            else:
                if img.operating_system and img.operating_system.to_reference_json(
                        architecture=architecture) not in os_list:
                    os_list.append(img.operating_system.to_reference_json(architecture=architecture))
    return os_list
