from marshmallow import Schema, validates_schema
from marshmallow.fields import Nested


class BaseSchema(Schema):
    tags = Nested("AWSTagSchema", required=False, many=True)

    @validates_schema
    def modify_tags(self, data, **kwargs):
        new_tags = list()
        reserve_characters = ['<', '>', '%', '&', '\\', '?', '/']
        for tag in data.get("tags", []):
            skip = False
            for char in reserve_characters:
                if char in tag["key"] or char in tag["value"]:
                    skip = True
                    break

            if not skip:
                new_tags.append(tag)

        data["tags"] = new_tags
        return data

    @validates_schema
    def modify_resource_id(self, data, **kwargs):
        data['resource_id'] = data['resource_id'] if data.get("resource_id") and 2 <= len(
            data['resource_id']) <= 64 else data['id']
        return data
