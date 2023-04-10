from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import backref, declarative_mixin, declared_attr, relationship


@declarative_mixin
class IBMCloudResourceMixin:
    IBM_CLOUD_KEY = "ibm_cloud"

    @declared_attr
    def cloud_id(self):
        return Column('cloud_id', ForeignKey('ibm_clouds.id', ondelete="CASCADE"))

    @declared_attr
    def ibm_cloud(self):
        return relationship(
            "IBMCloud", backref=backref(self.CRZ_BACKREF_NAME, cascade="all, delete-orphan", passive_deletes=True,
                                        lazy="dynamic")
        )


@declarative_mixin
class IBMRegionalResourceMixin(IBMCloudResourceMixin):
    REGION_KEY = "region"

    @declared_attr
    def region_id(self):
        return Column('region_id', ForeignKey('ibm_regions.id', ondelete="CASCADE"))

    @declared_attr
    def _region(self):
        return relationship(
            "IBMRegion", backref=backref(self.CRZ_BACKREF_NAME, cascade="all, delete-orphan", passive_deletes=True,
                                         lazy="dynamic")
        )

    @property
    def region(self):
        return self._region

    @region.setter
    def region(self, region_obj):
        assert region_obj.ibm_cloud, "The region does not have a cloud associated"

        self.ibm_cloud = region_obj.ibm_cloud
        self._region = region_obj


@declarative_mixin
class IBMZonalResourceMixin(IBMRegionalResourceMixin):
    ZONE_KEY = "zone"

    @declared_attr
    def zone_id(self):
        return Column('zone_id', ForeignKey('ibm_zones.id', ondelete="CASCADE"))

    @declared_attr
    def _zone(self):
        return relationship(
            "IBMZone", backref=backref(self.CRZ_BACKREF_NAME, cascade="all, delete-orphan", passive_deletes=True,
                                       lazy="dynamic")
        )

    @property
    def zone(self):
        return self._zone

    @zone.setter
    def zone(self, zone_obj):
        assert zone_obj.ibm_cloud, "The IBMZone does not have an IBMCloud associated"
        assert zone_obj.region, "The IBMZone does not have an IBMRegion associated"

        self.region = zone_obj.region
        self._zone = zone_obj
