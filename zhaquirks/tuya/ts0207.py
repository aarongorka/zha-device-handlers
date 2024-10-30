"""Quirk for TS0207 rain sensors."""

import zigpy.types as t
from zigpy.profiles import zha
from zigpy.quirks import CustomCluster
from zigpy.zcl.clusters.general import (
    Basic,
    Groups,
    Identify,
    OnOff,
    Ota,
    PowerConfiguration,
    Scenes,
    Time,
)
from zigpy.zcl.clusters.lightlink import LightLink
from zigpy.zcl.clusters.measurement import IlluminanceMeasurement
from zigpy.zcl.clusters.security import IasZone
from zhaquirks.const import (
    DEVICE_TYPE,
    ENDPOINTS,
    INPUT_CLUSTERS,
    MODELS_INFO,
    OUTPUT_CLUSTERS,
    PROFILE_ID,
)
from zhaquirks.tuya.mcu import TuyaMCUCluster
from zhaquirks.tuya import (
    DPToAttributeMapping,
    EnchantedDevice,
    TuyaNoBindPowerConfigurationCluster,
)
from zhaquirks import Bus
import logging

ZONE_TYPE = 0x0001

LOGGER = logging.getLogger(__name__)


class TuyaSolarRainSensorCluster(TuyaMCUCluster, CustomCluster):
    """Tuya manufacturer cluster."""

    attributes = TuyaMCUCluster.attributes.copy()
    attributes.update(
        {
            0xEF65: ("light_intensity", t.uint32_t, True),
            0xEF66: ("average_light_intensity_20mins", t.uint32_t, True),
            0xEF67: ("todays_max_light_intensity", t.uint32_t, True),
            0xEF68: ("cleaning_reminder", t.Bool, True),
            0xEF69: ("rain_sensor_voltage", t.uint32_t, True),
        }
    )

    dp_to_attribute: dict[int, DPToAttributeMapping] = {
        101: DPToAttributeMapping(
            TuyaMCUCluster.ep_attribute,
            "light_intensity",
        ),
        102: DPToAttributeMapping(
            TuyaMCUCluster.ep_attribute,
            "average_light_intensity_20mins",
        ),
        103: DPToAttributeMapping(
            TuyaMCUCluster.ep_attribute,
            "todays_max_light_intensity",
        ),
        104: DPToAttributeMapping(
            TuyaMCUCluster.ep_attribute,
            "cleaning_reminder",
        ),
        105: DPToAttributeMapping(
            TuyaMCUCluster.ep_attribute,
            "rain_sensor_voltage",
        ),
    }

    data_point_handlers = {
        101: "_dp_2_attr_update",
        102: "_dp_2_attr_update",
        103: "_dp_2_attr_update",
        104: "_dp_2_attr_update",
        105: "_dp_2_attr_update",
    }

    def _update_attribute(self, attrid, value):
        super()._update_attribute(attrid, value)
        if attrid == 0xEF65 and value is not None and value >= 0:
            self.endpoint.device.illuminance_bus.listener_event(
                "illuminance_reported", value
            )


class TuyaIlluminanceCluster(CustomCluster, IlluminanceMeasurement):
    """Tuya Illuminance cluster."""

    cluster_id = IlluminanceMeasurement.cluster_id
    MEASURED_VALUE_ATTR_ID = 0x0000
    MIN_MEASURED_VALUE_ATTR_ID = 0x0001
    MAX_MEASURED_VALUE_ATTR_ID = 0x0001

    # The value gets passed through `round(pow(10, ((value - 1) / 10000)))` by ZHA
    # https://github.com/zigpy/zha/blob/927e249134c87bd7805139c8fb61e048593ec155/zha/application/platforms/sensor/__init__.py#L782C9-L782C53
    CALIBRATION_FACTOR = 7  # very approximate adjustment, do not expect this to be accurate

    def __init__(self, *args, **kwargs):
        """Init."""
        super().__init__(*args, **kwargs)
        LOGGER.debug("Attaching TuyaIlluminanceCluster to listener...")
        self.endpoint.device.illuminance_bus.add_listener(self)
        LOGGER.debug("TuyaIlluminanceCluster attached to listener.")

    def illuminance_reported(self, value):
        """Illuminance reported."""

        calibrated_value = value * self.CALIBRATION_FACTOR
        self._update_attribute(self.MEASURED_VALUE_ATTR_ID, calibrated_value)
        LOGGER.debug(f"measured_value attribute updated.")


class TuyaIasZone(CustomCluster, IasZone):
    """IAS Zone for rain sensors."""

    _CONSTANT_ATTRIBUTES = {ZONE_TYPE: IasZone.ZoneType.Water_Sensor}


class TuyaSolarRainSensor(EnchantedDevice):
    """TS0207 Rain sensor quirk."""

    def __init__(self, *args, **kwargs) -> None:
        """Init."""
        self.illuminance_bus = Bus()
        LOGGER.debug(f"Bus created.")
        super().__init__(*args, **kwargs)

    signature = {
        MODELS_INFO: [("_TZ3210_tgvtvdoc", "TS0207")],
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.IAS_ZONE,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    PowerConfiguration.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    IasZone.cluster_id,
                    TuyaMCUCluster.cluster_id,
                ],
                OUTPUT_CLUSTERS: [
                    Identify.cluster_id,
                    Groups.cluster_id,
                    OnOff.cluster_id,
                    Time.cluster_id,
                    Ota.cluster_id,
                    LightLink.cluster_id,
                ],
            },
        },
    }

    replacement = {
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.IAS_ZONE,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    TuyaNoBindPowerConfigurationCluster,
                    TuyaIasZone,
                    TuyaSolarRainSensorCluster,
                    TuyaIlluminanceCluster,
                ],
                OUTPUT_CLUSTERS: [
                    Time.cluster_id,
                    Ota.cluster_id,
                ],
            },
        },
    }
