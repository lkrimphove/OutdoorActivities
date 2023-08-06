import io
import gpxpy
import pandas as pd
import numpy as np
import haversine as hs

from pathlib import Path

import boto3

import logging

logger = logging.getLogger(__name__)


ACTIVITY_TYPES = {
    'Hiking': {
        'icon': 'person-hiking',
        'color': 'green'
    },
    'Running': {
        'icon': 'person-running',
        'color': 'orange'
    },
    'Biking': {
        'icon': 'person-biking',
        'color': 'red'
    },
    'Skiing': {
        'icon': 'person-skiing',
        'color': 'blue'
    }
}



def parse_activities(input_path):
    activities = {}
    frames = []
    for activity_type in ACTIVITY_TYPES:
        activities[activity_type] = {}

        _input_path = f'{input_path}/{activity_type}'
        pathlist = Path(_input_path).glob('**/*.gpx')
        for path in pathlist:
            # exclude hidden directories and files
            # will lead to performance issues if there are lots of hidden files
            if any(part.startswith('.') for part in path.parts):
                continue

            activity_group = path.parts[-2]
            activity_name = path.parts[-1]

            if activity_group not in activities[activity_type]:
                activities[activity_type][activity_group] = []

            gpx = gpxpy.parse(open(path), version='1.0')
            points, gpx_df = parse_gpx(gpx)

            activities[activity_type][activity_group].append({
                'name': activity_name.replace('.gpx', '').replace('_', ' '),
                'points': points,
                'gpx_df': gpx_df
            })
            frames.append(gpx_df)

    if len(frames) > 0:
        df = pd.concat(frames)
    else:
        df = None

    return activities, df


def parse_activities_s3(s3_bucket_id):
    s3 = boto3.resource('s3')
    activities = {}
    frames = []

    bucket = s3.Bucket(s3_bucket_id)
    for obj in bucket.objects.filter():
        if obj.key.endswith('.gpx'):
            parts = obj.key.split('/')
            logger.debug(f'Parts: {parts}')
            if any(part.startswith('.') for part in parts):
                logger.info(f'Skipped {obj.key}')
                continue

            activity_type = parts[0]
            activity_group = parts[-2]
            activity_name = parts[-1]

            if activity_type not in ACTIVITY_TYPES:
                continue

            if activity_type not in activities:
                activities[activity_type] = {}

            if activity_group not in activities[activity_type]:
                activities[activity_type][activity_group] = []

            gpx_file = io.BytesIO(obj.get()['Body'].read())
            gpx = gpxpy.parse(gpx_file, version='1.0')
            points, gpx_df = parse_gpx(gpx)

            activities[activity_type][activity_group].append({
                'name': activity_name.replace('.gpx', '').replace('_', ' '),
                'points': points,
                'gpx_df': gpx_df
            })
            frames.append(gpx_df)

    if len(frames) > 0:
        df = pd.concat(frames)
    else:
        df = None

    logger.info(f'Read {len(frames)} activities')
    return activities, df

def parse_gpx(gpx):
    # parse gpx file
    data = []
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point_idx, point in enumerate(segment.points):
                points.append(tuple([point.latitude, point.longitude]))

                # calculate distances between points
                if point_idx == 0:
                    distance = np.nan
                else:
                    distance = hs.haversine(
                        point1=points[point_idx-1],
                        point2=points[point_idx],
                        unit=hs.Unit.METERS
                    )

                data.append([point.longitude, point.latitude, point.elevation,
                            point.time, segment.get_speed(point_idx), distance])

    columns = ['Longitude', 'Latitude',
               'Elevation', 'Time', 'Speed', 'Distance']

    gpx_df = pd.DataFrame(data, columns=columns)

    gpx_df['Elevation_Diff'] = np.round(gpx_df['Elevation'].diff(), 2)
    gpx_df['Cum_Elevation'] = np.round(gpx_df['Elevation_Diff'].cumsum(), 2)
    gpx_df['Cum_Distance'] = np.round(gpx_df['Distance'].cumsum(), 2)
    gpx_df['Gradient'] = np.round(gpx_df['Elevation_Diff'] / gpx_df['Distance'] * 100, 1)


    return points, gpx_df
