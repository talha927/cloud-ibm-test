from .centos import CentOS
from ..consts import PACKAGES_INSTALLATION_FIX


class RedHat(CentOS):
    PACKAGES_INSTALLATION_FIX = PACKAGES_INSTALLATION_FIX

    def __init__(self):
        super().__init__()
        self.reboot = True
