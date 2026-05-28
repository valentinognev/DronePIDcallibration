"""Tests for PX4 ULOG parser."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pidbox.core.loader import list_firmwares
from pidbox.core.parsers.base import PARSERS, get_parser
from pidbox.core.parsers.px4 import Px4Parser, _read_px4_ulg

PRIMARY_ULG = Path(
    "/home/valentin/RL/TESTFLIGHTS/RLCat2_3blades/RLFlights/good/log_5_2026-1-14-11-27-12.ulg"
)
NO_FIFO_ULG = Path("/home/valentin/RL/TESTFLIGHTS/sininput.ulg")


def test_px4_registered():
    assert "px4" in PARSERS
    parser = get_parser("px4")
    assert isinstance(parser, Px4Parser)
    assert parser.display_name == "PX4"


def test_px4_in_firmware_list():
    keys = {f["key"] for f in list_firmwares()}
    assert "px4" in keys


def test_can_parse_ulg():
    parser = Px4Parser()
    assert parser.can_parse(Path("flight.ulg"))
    assert not parser.can_parse(Path("flight.bbl"))


@pytest.mark.skipif(not PRIMARY_ULG.is_file(), reason="Primary PX4 test ULG not available")
def test_load_primary_ulg_with_fifo():
    logs = Px4Parser().parse(PRIMARY_ULG)
    assert len(logs) == 1
    log = logs[0]
    assert log.fw_type == "PX4"
    assert log.metadata.get("has_gyro_fifo") is True
    assert log.metadata.get("gyro_source") == "sensor_gyro_fifo"
    assert log.lograte_khz >= 4.0

    df = log.dataframe
    for col in (
        "time_us",
        "gyroADC_0_",
        "gyroADC_1_",
        "gyroADC_2_",
        "setpoint_0_",
        "setpoint_1_",
        "setpoint_2_",
        "accel_0_",
        "accel_1_",
        "accel_2_",
        "vel_0_",
        "vel_1_",
        "vel_2_",
        "vel_sp_0_",
        "vel_sp_1_",
        "vel_sp_2_",
        "att_roll_",
        "att_pitch_",
        "att_yaw_",
        "att_sp_roll_",
        "att_sp_pitch_",
        "att_sp_yaw_",
    ):
        assert col in df.columns
        assert len(df[col]) > 1000

    assert log.metadata.get("accel_source") == "sensor_combined"
    assert log.metadata.get("accel_unit") == "m/s²"
    assert log.metadata.get("velocity_source") == "vehicle_local_position"
    assert log.metadata.get("velocity_setpoint_source") == "vehicle_local_position_setpoint"
    assert log.metadata.get("velocity_frame") == "NED local"
    assert len(log.setup_info) > 2


@pytest.mark.skipif(not PRIMARY_ULG.is_file(), reason="Primary PX4 test ULG not available")
def test_fifo_higher_rate_than_sensor_combined():
    df_fifo, _, meta = _read_px4_ulg(PRIMARY_ULG)
    assert meta["gyro_source"] == "sensor_gyro_fifo"

    from pyulog import ULog

    ulog = ULog(str(PRIMARY_ULG))
    combined = ulog.get_dataset("sensor_combined")
    ts = np.asarray(combined.data["timestamp"], dtype=float)
    combined_rate_khz = 1000 / np.median(np.diff(ts))

    fifo_rate_khz = 1000 / np.median(np.diff(df_fifo["time_us"].values))
    assert fifo_rate_khz > combined_rate_khz * 5


@pytest.mark.skipif(not NO_FIFO_ULG.is_file(), reason="No-FIFO PX4 test ULG not available")
def test_load_ulg_without_fifo():
    logs = Px4Parser().parse(NO_FIFO_ULG)
    log = logs[0]
    assert log.metadata.get("has_gyro_fifo") is False
    assert log.metadata.get("gyro_source") in ("sensor_combined", "vehicle_angular_velocity")
    df = log.dataframe
    assert "gyroADC_0_" in df.columns
    assert len(df) > 100


def test_read_px4_ulg_mock(monkeypatch):
    """Load path works when only vehicle_angular_velocity is present."""

    class FakeDataset:
        def __init__(self, data):
            self.data = data

    class FakeULog:
        initial_parameters = {"SYS_AUTOSTART": 4001}

        def get_dataset(self, name):
            if name == "sensor_gyro_fifo":
                raise KeyError(name)
            if name == "sensor_combined":
                raise KeyError(name)
            if name == "vehicle_angular_velocity":
                n = 100
                return FakeDataset(
                    {
                        "timestamp": np.arange(n) * 2500 + 1_000_000,
                        "xyz[0]": np.ones(n) * 0.1,
                        "xyz[1]": np.ones(n) * 0.2,
                        "xyz[2]": np.ones(n) * 0.3,
                    }
                )
            if name == "vehicle_rates_setpoint":
                n = 50
                return FakeDataset(
                    {
                        "timestamp": np.arange(n) * 5000 + 1_000_000,
                        "roll": np.zeros(n),
                        "pitch": np.zeros(n),
                        "yaw": np.zeros(n),
                    }
                )
            if name == "vehicle_thrust_setpoint":
                n = 50
                return FakeDataset(
                    {
                        "timestamp": np.arange(n) * 5000 + 1_000_000,
                        "xyz[2]": np.linspace(0, 1, n),
                    }
                )
            raise KeyError(name)

    class FakePX4ULog:
        def __init__(self, ulog):
            self._ulog = ulog

        def add_roll_pitch_yaw(self):
            pass

    monkeypatch.setattr("pyulog.ULog", lambda path: FakeULog())
    monkeypatch.setattr("pyulog.px4.PX4ULog", FakePX4ULog)

    df, setup, meta = _read_px4_ulg(Path("mock.ulg"))
    assert meta["gyro_source"] == "vehicle_angular_velocity"
    assert len(df) == 100
    assert setup[0][1] == "PX4"
