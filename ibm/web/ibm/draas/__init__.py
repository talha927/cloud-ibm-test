from apiflask import APIBlueprint

ibm_draas = APIBlueprint('ibm_draas', __name__, tag="IBM DRaaS")

from .backups import api  # noqa
from .restores import api  # noqa
