class VolumeAttachmentException(Exception):
    def __init__(self, host):
        super(VolumeAttachmentException, self).__init__(
            "Volume attachment Exception(No Volume attached)\nMachine: {host}\n".format(
                host=host
            )
        )


class OperatingSystemNameException(Exception):
    def __init__(self, os_name):
        super(OperatingSystemNameException, self).__init__(
            "{os_name} does not belong Linux(Ubuntu, CentOS, RedHat, Debian)".format(
                os_name=os_name
            )
        )
