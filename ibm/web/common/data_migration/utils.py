from .exceptions import OperatingSystemNameException
from .linux import CentOS, Debian, RedHat, Ubuntu


def return_class(os_name):
    base_os1 = os_name.split(" ")[0].lower()
    base_os2 = os_name.split("-")[0].lower()
    base_os3 = os_name.split(" ")
    if len(base_os3) == 1:
        base_os3 = None
    else:
        base_os3 = base_os3[1].lower()
    try:
        base_os4 = os_name.split("-")[1].lower()
    except (IndexError, AttributeError):
        base_os4 = None
    class_names = {
        "centos": CentOS(),
        "debian": Debian(),
        "red": RedHat(),
        "redhat": RedHat(),
        "ubuntu": Ubuntu(),
    }
    for os in [base_os1, base_os2, base_os3, base_os4]:
        operating_system = class_names.get(os)
        if operating_system is not None:
            return operating_system
    raise OperatingSystemNameException(os_name=os_name)
