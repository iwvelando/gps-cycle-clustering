#!/usr/bin/python
# -*- mode: sh; tab-width: 4; indent-tabs-mode: nil; -*-
# vim: set expandtab shiftwidth=4 softtabstop=4 ts=4 :

"""
The purpose of this is to parse many GPS courses (in .gpx format) to:
1. Deduplicate the courses so that even if one has multiple loops, only
   one will count
2. Attempt to remove non-cycling activity from courses (e.g. walking)
3. Aggregate the location data and attempt to cluster nearby points
   together; this should give an indication of the popularity of
   certain roads
4. Sort the resultant clustered location data
5. Output a .csv that can be used in e.g. http://www.gpsvisualizer.com/
   that can generate a heat map overlayed on Google Maps that lets us
   view popular roads
6. By making it easy to see the most popular roads, this hopefully
   indicates where the safest roads are
"""

import math
import csv
import datetime
import multiprocessing
import os
import re

def distance_latlon(lat1, lon1, lat2, lon2):
    """
    This calculates the geographic distance between two (lat,lon) coordinate
    pairs. The output is in meters to be consistent with some thresholds
    used later on.
    """
    radius_earth = 6378.137
    d_lat = (lat2 - lat1) * math.pi / 180
    d_lon = (lon2 - lon1) * math.pi / 180
    calc_1 = (math.sin(d_lat/2)**2
              + math.cos(lat1 * math.pi / 180)
              * math.cos(lat2 * math.pi / 180)
              * math.sin(d_lon/2)**2)
    calc_2 = 2*math.atan2(math.sqrt(calc_1), math.sqrt(1-calc_1))
    return radius_earth * calc_2 * 1000

def distance_threshold(threshold, lat1, lon1, lat2, lon2):
    """
    A simple boolean to tell whether the distance between two points is
    less than or equal to a provided threshold value (True).
    """
    distance = distance_latlon(lat1, lon1, lat2, lon2)
    return bool(distance <= threshold)

def quantile(percent, data):
    """
    Compute the quantile such that 100p% of data lies above the output
    value.
    """
    if not data:
        return data
    data.sort()
    index = int(percent*len(data) + 0.5) - 1
    if index < 0:
        index = 0
    return data[index]

def coordinates_dedup(latlon_list):
    """
    Sort the route geographically and then cluster points together; this
    should reduce multiple loops of one course down to one loop only.
    """
    latlon_list_ordered = order_route(latlon_list)
    latlon_list_deduped = []
    for coordinate in latlon_list_ordered:
        if (len(latlon_list_deduped) == 0
            or not distance_threshold(THRESHOLD_DISTANCE_CLUSTER,
                                      latlon_list_deduped[-1][0],
                                      latlon_list_deduped[-1][1],
                                      coordinate[0],
                                      coordinate[1])):
            latlon_list_deduped.append(coordinate)
    return latlon_list_deduped

def coordinates_cluster_parallel():
    """
    Use the multiprocessing module to iterate through the coordinates in
    parallel.
    """
    num_cores = multiprocessing.cpu_count()
    pool = multiprocessing.Pool(processes=num_cores)
    mp_pool = pool.map_async(run_coordinate_cluster,
                             range(n_rows),
                             callback=data_ranked.append)
    mp_pool.wait()

def run_coordinate_cluster(index):
    """
    For each coordinate, find the number of points sufficiently nearby to
    allow us to cluster the coordinates together
    """
    lat = float(latlon_data[index][0])
    lon = float(latlon_data[index][1])
    data_near = [x for x in latlon_data
                 if distance_threshold(THRESHOLD_DISTANCE_CLUSTER,
                                       lat,
                                       lon,
                                       float(x[0]),
                                       float(x[1]))]
    # TODO: because of the way the parallel processing works this isn't
    # always in order - maybe there's a better way
    if index % notification_interval == 0:
        print("{:s} completed {:d} of {:d} coordinates in the main loop"
              .format(str(datetime.datetime.now()), index, n_rows))
    if data_near:
        return [float(data_near[0][0]), float(data_near[0][1]), len(data_near)]
    else:
        return [None, None, None]

def order_route(latlon_list, notify=False):
    """
    Order a route by starting at the first point and adding on the next
    most geographically proximal point at each iteration
    """
    n_points = len(latlon_list)
    if n_points == 0:
        return latlon_list
    point_list = [latlon_list.pop()]
    if notify:
        notification_interval = math.floor(n_points/10)
        if notification_interval == 0:
            notification_interval = 10
    count = 0
    while latlon_list:
        point_list.append(min(latlon_list,
                              key=lambda
                              x: distance_latlon(point_list[-1][0],
                                                 point_list[-1][1],
                                                 x[0], x[1])))
        latlon_list.remove(point_list[-1])
        if notify and count % notification_interval == 0:
            print("{:s} completed ordering {:d} of {:d} coordinates"
                  .format(str(datetime.datetime.now()), count, n_points))
        count += 1
    return point_list

def read_courses(directory):
    """
    Read all .gpx courses in a directory and aggregate/post-process them before
    returning the aggregate list of all coordinates
    """
    global all_coordinates
    all_coordinates = []
    all_courses = []
    for file in os.listdir(directory):
        if file.endswith('.gpx'):
            all_courses.append(directory + file)
    parse_courses_parallel(all_courses)
    # Merge the first level of entries in the list -- TODO find out why this is
    # needed even though we're using extend in the callback
    all_coordinates = [a for b in all_coordinates for a in b]
    # Remove duplicate entries from the list (this will ignore the order of the
    # points, but they should already be unordered)
    all_coordinates_set = set(map(tuple, all_coordinates))
    all_coordinates = list(map(list, all_coordinates_set))
    return all_coordinates

def parse_courses_parallel(course_file_list):
    """
    Use the multiprocessing module to iterate through the coordinates in
    parallel.
    """
    num_cores = multiprocessing.cpu_count()
    pool = multiprocessing.Pool(processes=num_cores)
    mp_pool = pool.map_async(parse_course,
                             course_file_list,
                             callback=all_coordinates.extend)
    mp_pool.wait()

def parse_course(file):
    """
    Perform post-processing on a course to clean it up:
    1. Filter out sequences of too-nearby points; this is meant to remove idle
       activity like walking (because that is not going to help us found safe
       roads for cycling)
    2. Perform deduplication on the course using coordinates_dedup() to remove
       extra loops
    """
    f = open(file, 'r')
    latlon_list = []
    for line in f:
        match = re.search('<trkpt lat="([0-9\.\-]+)" lon="([0-9\.\-]+)"/>',
                          line)
        if match and len(match.groups()) == 2:
            lat, lon = match.group(1, 2)
            latlon_list.append([float(lat), float(lon)])
    # Filter the set of coordinates to consecutive movements of at least 1m;
    # this method will always exclude the last coordinate so handle it
    # separately
    latlon_list_filtered = list(filter(None,
                                       [p0*(distance_latlon(p0[0], p0[1],
                                                            p1[0], p1[1])
                                            >= THRESHOLD_DISTANCE_CONSECUTIVE)
                                        for p0, p1 in
                                        zip(latlon_list,
                                            latlon_list[1:])]))
    if (len(latlon_list) > 2
        and distance_latlon(latlon_list[-2][0],
                            latlon_list[-2][1],
                            latlon_list[-1][0],
                            latlon_list[-1][1])
        > THRESHOLD_DISTANCE_CONSECUTIVE):
        latlon_list_filtered.append([latlon_list[-1][0], latlon_list[-1][1]])
    return coordinates_dedup(latlon_list_filtered)

def read_csv(file):
    """
    Read a CSV file and return it as a list
    """
    with open(file, 'r') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        return list(reader)

def list_to_gpx(file, latlon_list):
    """
    Using an input list, write a GPX formatted file
    """
    gpx = open(file, 'w')
    gpx.write('<?xml version="1.0" ?>\n'
              '<gpx xmlns="http://www.topografix.com/GPX/1/1">\n'
              ' <trk>\n'
              '  <name>\n'
              '   Safe roads in Houston\n'
              '  </name>\n'
              '  <trkseg>\n')
    for latlon in latlon_list:
        gpx.write('   <trkpt lat="'
                  +str(latlon[0])
                  +'" lon="'
                  +str(latlon[1])+'"/>\n')
    gpx.write('  </trkseg>\n'
              ' </trk>\n'
              '</gpx>\n')
    gpx.close()

def write_csv(file, data, delim=','):
    """
    Write out a CSV file using a given delimiter
    """
    with open(file, 'w') as csvfile:
        writer = csv.writer(csvfile, delimiter=delim)
        writer.writerows(data)

def main():
    """
    Read in the raw data, parse and aggregate it, and then cluster the
    coordinates
    """
    script_path = os.path.dirname(os.path.realpath(__file__))
    global THRESHOLD_DISTANCE_CLUSTER
    global THRESHOLD_DISTANCE_CONSECUTIVE
    # 7.8 meter 95% confidence interval for GPS accuracy, need twice this value (diameter)
    THRESHOLD_DISTANCE_CLUSTER = 15.6
    # Two points within 1 meter of each other will be considered duplicates
    THRESHOLD_DISTANCE_CONSECUTIVE = 1.0
    p_quantile = 0.30
    dir_courses = script_path + '/courses/'
    file_output_raw = script_path + '/result_raw.csv'
    file_output_heatmap = script_path + '/result_heatmap.csv'
    file_output_gpx = script_path + '/result.gpx'

    global latlon_data
    global latlon_data_course
    global n_rows
    global n_rows_course
    global data_ranked
    global notification_interval
    latlon_data = read_courses(dir_courses)
    list_to_gpx(script_path + "/latlon_data_filtered", latlon_data)
    data_ranked = []
    n_rows = len(latlon_data)
    notification_interval = math.floor(n_rows/10)
    if notification_interval == 0:
        notification_interval = 10

    coordinates_cluster_parallel()

    data_ranked_filtered = [x for x in data_ranked[0] if None not in x]
    # Cheap way of removing duplicates...
    # TODO: find the root cause of duplicates and eliminate it
    data_ranked_filtered_set = set(map(tuple, data_ranked_filtered))
    data_ranked_filtered = list(map(list, data_ranked_filtered_set))
    write_csv(file_output_raw, data_ranked_filtered, ',')
    print("{:s} wrote raw output data to {:s}"
          .format(str(datetime.datetime.now()), file_output_raw))
    ranks = [col[2] for col in data_ranked_filtered]
    threshold_rank = quantile(p_quantile, ranks)
    if threshold_rank <= 1:
        # We ought to never keep a point only one person uses
        threshold_rank = 2
    data_ranked_threshold = [x for x in data_ranked_filtered
                             if x[2] >= threshold_rank]
    print("{:s} finished ranking and filtering the output data using a "
          "threshold of {:d} neighbor minimum"
          .format(str(datetime.datetime.now()), threshold_rank))
    data_ranked_threshold_ordered = order_route(data_ranked_threshold, True)
    print("{:s} finished ordering the output data"
          .format(str(datetime.datetime.now())))
    data_ranked_threshold_ordered_heatmap = [['latitude', 'longitude', 'n']]
    data_ranked_threshold_ordered_heatmap.extend(data_ranked_threshold_ordered)
    write_csv(file_output_heatmap, data_ranked_threshold_ordered_heatmap, ',')
    list_to_gpx(file_output_gpx, data_ranked_threshold_ordered)
    print("{:s} wrote gpx output data to {:s}"
          .format(str(datetime.datetime.now()), file_output_gpx))

if __name__ == '__main__':
    main()

