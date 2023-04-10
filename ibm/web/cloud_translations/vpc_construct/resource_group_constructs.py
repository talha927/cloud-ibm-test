class ResourceGroup:
    ID_KEY = "id"
    NAME_KEY = "name"

    def __init__(self, id_, name):
        self.id = id_
        self.name = name

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }
