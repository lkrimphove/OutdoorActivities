from input_parser import ACTIVITY_TYPES, parse_activities, parse_activities_s3
from utils import timedelta_formatter

import os
import logging

import pandas as pd
import numpy as np
import folium
from folium import plugins as folium_plugins

import boto3



logger = logging.getLogger()

if 'AWS_EXECUTION_ENV' in os.environ and 'LOG_LVL' in os.environ:
    LOG_LVL = os.environ['LOG_LVL']
    logger.setLevel(level=LOG_LVL)
else:
    logger.setLevel(level='DEBUG')

if 'START_LATITUDE' in os.environ and 'START_LONGITUDE' in os.environ:
    LOCATION = [float(os.environ['START_LATITUDE']),
                float(os.environ['START_LONGITUDE'])]
else:
    LOCATION = None

if 'ZOOM_START' in os.environ:
    ZOOM_START = int(os.environ['ZOOM_START'])
else:
    ZOOM_START = 10



def create_map_html(input_directory, output_filepath):
    map = create_map(input_directory)
    map.save(output_filepath)


def create_map(input_directory):
    try:
        activities, df = parse_activities(input_directory)
    except Exception as e:
        print(e)
        activities, df = None

    if LOCATION:
        location = LOCATION
    elif df is not None:
        location = [df.Latitude.mean(), df.Longitude.mean()]
    else:
        location = None

    map = folium.Map(location=location, zoom_start=ZOOM_START, tiles=None)
    folium.TileLayer('OpenStreetMap', name='OpenStreet Map').add_to(map)
    folium.TileLayer('Stamen Terrain', name='Stamen Terrain').add_to(map)

    if df is not None and activities is not None:
        create_activity_trails(activities, map)

    map.add_child(folium.LayerControl(position='bottomright'))
    folium_plugins.Fullscreen(position='topright').add_to(map)

    return map


def create_activity_trails(activities, map):
    feature_groups = {}
    for activity_type in activities:
        color = ACTIVITY_TYPES[activity_type]['color']
        icon = ACTIVITY_TYPES[activity_type]['icon']

        for activity_group in activities[activity_type]:
            # create and store feature groups
            # this allows different activity types in the same feature group
            if activity_group not in feature_groups:
                # create new feature group
                fg = folium.FeatureGroup(name=activity_group, show=True)
                feature_groups[activity_group] = fg
                map.add_child(fg)
            else:
                # use existing
                fg = feature_groups[activity_group]

            for activity in activities[activity_type][activity_group]:
                # create line on map
                points = activity['points']
                line = folium.PolyLine(
                    points, color=color, weight=4.5, opacity=.5)
                fg.add_child(line)

                # create marker
                marker = folium.Marker(points[0], popup=create_activity_popup(activity),
                                       icon=folium.Icon(color=color, icon_color='white', icon=icon, prefix='fa'))
                fg.add_child(marker)


def create_activity_popup(activity):
    df = activity['gpx_df']
    attributes = {
        'Date': {
            'value': df['Time'][df.index[0]].strftime("%m/%d/%Y"),
            'icon': 'calendar'
        },
        'Start': {
            'value': df['Time'][df.index[0]].strftime("%H:%M:%S"),
            'icon': 'clock'
        },
        'End': {
            'value': df['Time'][df.index[-1]].strftime("%H:%M:%S"),
            'icon': 'flag-checkered'
        },
        'Duration': {
            'value': timedelta_formatter(df['Time'][df.index[-1]]-df['Time'][df.index[0]]),
            'icon': 'stopwatch'
        },
        'Distance': {
            'value': f"{np.round(df['Cum_Distance'][df.index[-1]] / 1000, 2)} km",
            'icon': 'arrows-left-right'
        },
        'Average Speed': {
            'value': f'{np.round(df.Speed.mean() * 3.6, 2)} km/h',
            'icon': 'gauge-high'
        },
        'Max. Elevation': {
            'value': f'{np.round(df.Elevation.max(), 2)} m',
            'icon': 'mountain'
        },
        'Uphill': {
            'value': f"{np.round(df[df['Elevation_Diff']>0]['Elevation_Diff'].sum(), 2)} m",
            'icon': 'arrow-trend-up'
        },
        'Downhill': {
            'value': f"{np.round(abs(df[df['Elevation_Diff']<0]['Elevation_Diff'].sum()), 2)} m",
            'icon': 'arrow-trend-down'
        },
    }
    html = f"<h4>{activity['name'].upper()}</h4>"
    for attribute in attributes:
        html += f'<i class="fa-solid fa-{attributes[attribute]["icon"]}" title="{attribute}">  {attributes[attribute]["value"]}</i></br>'
    return folium.Popup(html, max_width=300)


# HANDLERS

def lambda_handler(event, context):
    logger.info('## ENVIRONMENT VARIABLES')
    logger.info(os.environ)
    logger.info('## EVENT')
    logger.info(event)

    try:
        activities, df = parse_activities_s3(os.environ['INPUT_BUCKET'])
    except Exception as e:
        logger.error(e, exc_info=True)
        activities = None
        df = None

    if LOCATION:
        location = LOCATION
    elif df is not None:
        location = [df.Latitude.mean(), df.Longitude.mean()]
    else:
        location = None

    map = folium.Map(location=location, zoom_start=ZOOM_START, tiles=None)
    folium.TileLayer('OpenStreetMap', name='OpenStreet Map').add_to(map)
    folium.TileLayer('Stamen Terrain', name='Stamen Terrain').add_to(map)

    if df is not None and activities is not None:
        create_activity_trails(activities, map)

    map.add_child(folium.LayerControl(position='bottomright'))
    folium_plugins.Fullscreen(position='topright').add_to(map)

    html_string = map.get_root().render()


    # Save html_string to S3 bucket
    s3_client = boto3.client('s3')
    s3_bucket = os.environ['OUTPUT_BUCKET']
    s3_key = 'map.html'

    try:
        response = s3_client.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=html_string,
            ContentType='text/html'
        )
        logger.info(f"HTML file successfully saved to S3 bucket: s3://{s3_bucket}/{s3_key}")
    except Exception as e:
        logger.error(f"Error saving HTML file to S3 bucket: {e}")

    cf_client = boto3.client('cloudfront')

    # Create an invalidation request for the distribution
    cloudfront_distribution_id = os.environ['CLOUDFRONT_DISTRIBUTION_ID']
    invalidation_response = cf_client.create_invalidation(
        DistributionId=cloudfront_distribution_id,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': [f'/{s3_key}']
            },
            'CallerReference': 'lambda-invalidation'
        }
    )
    logger.info(f"CloudFront cache invalidation request created: {invalidation_response}")

    return {
        'statusCode': 200,
        'body': 'HTML file successfully saved to S3 bucket.'
    }    
