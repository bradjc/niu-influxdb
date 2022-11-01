#!/usr/bin/env python3

import copy
import os

import arrow
import influxdb

import niuApi
from niuApi import apicommands
from niuApi.apicommands import v3
from niuApi.apicommands import v5
from niuApi.apicommands import other


INFLUX_CONFIG_FILE_PATH = "/etc/swarm-gateway/influx.conf"


# Get influxDB config.
influx_config = {}
with open(INFLUX_CONFIG_FILE_PATH) as f:
    for l in f:
        fields = l.split("=")
        if len(fields) == 2:
            influx_config[fields[0].strip()] = fields[1].strip()


def km_to_mi(km):
    conv_fac = 0.621371
    return float(km) * conv_fac


# Data points to send to influx
points = []

# Get all scooters
scooters = niuApi.apicommands.v5.scooter_list()

for scooter in scooters:
    sn = scooter["sn_id"]

    metadata = {
        "device_id": sn,
        "sku": scooter["sku_name"],
        "name": scooter["scooter_name"],
        "type_": scooter["product_type"],
        "carframe_id": scooter["carframe_id"],
        "receiver": "niu-influxdb",
    }

    detail = niuApi.apicommands.v5.scooter_detail(sn)

    metadata["engine_num"] = detail["engine_num"]
    data = {
        "battery_%": detail["battery_level"],
        "battery_cycles": detail["battery_cycle"],
        "range_mi": km_to_mi(detail["estimated_mileage"]),
    }

    mileage = niuApi.apicommands.other.motoinfo_overallTally(sn)
    data["odometer_mi"] = km_to_mi(mileage["totalMileage"])

    point = {
        "measurement": "scooter",
        "fields": data,
        "tags": metadata,
        "time": arrow.now().datetime,
    }
    points.append(point)

    # Get the last published trip.
    last_trip_filename = "./last-trip-{}.txt".format(sn)
    last_trip_id = None
    if os.path.exists(last_trip_filename):
        with open(last_trip_filename) as f:
            last_trip_id = f.read().strip()

    print("last trip: {}".format(last_trip_id))

    newest_trip_id = None

    # Get all trips and publish the new ones.
    trips = niuApi.apicommands.v5.track_list_v2(sn)
    for trip in trips["items"]:
        start = arrow.get(trip["startTime"])
        end = arrow.get(trip["endTime"])

        trip_metadata = copy.deepcopy(metadata)
        trip_metadata["trip_id"] = trip["trackId"]

        if newest_trip_id == None:
            newest_trip_id = trip["trackId"]

        if last_trip_id != None:
            if last_trip_id == trip["trackId"]:
                break

        trip_data = {
            "distance_mi": km_to_mi(float(trip["distance"]) / 1000.0),
            "speed_avg_mph": km_to_mi(trip["avespeed"]),
            "duration_s": trip["ridingtime"],
        }

        trip_event_start = copy.deepcopy(trip_data)
        trip_event_start["event"] = "start"

        trip_event_end = {
            "distance_mi": 0.0,
            "speed_avg_mph": 0.0,
            "duration_s": 0,
        }
        trip_event_end["event"] = "end"

        point = {
            "measurement": "scooter_trip",
            "fields": trip_data,
            "tags": trip_metadata,
            "time": start.datetime,
        }
        points.append(point)
        point = {
            "measurement": "scooter_trip_event",
            "fields": trip_event_start,
            "tags": trip_metadata,
            "time": start.datetime,
        }
        points.append(point)
        point = {
            "measurement": "scooter_trip_event",
            "fields": trip_event_end,
            "tags": trip_metadata,
            "time": end.datetime,
        }
        points.append(point)

    print("newest trip id: {}".format(newest_trip_id))
    if newest_trip_id != None:
        with open(last_trip_filename, "w") as f:
            f.write(newest_trip_id)

print("Publishing {} points".format(len(points)))

client = influxdb.InfluxDBClient(
    influx_config["url"],
    influx_config["port"],
    influx_config["username"],
    influx_config["password"],
    influx_config["database"],
    ssl=True,
    gzip=True,
    verify_ssl=True,
)

client.write_points(points)
print("wrote points")
