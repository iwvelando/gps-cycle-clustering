# gps-cycle-clustering

The goal of this project is to parse an arbitrary set of GPX-formatted GPS cycling data to:

1. Deduplicate the courses so that even if one has multiple loops only one will count
2. Attempt to remove non-cycling activity from courses (e.g. walking)
3. Aggregate the location data and attempt to cluster nearby points together; this should give an indication of the popularity of certain roads
4. Sort the resultant clustered location data
5. Output a .csv that can be used in e.g. http://www.gpsvisualizer.com/ that can generate a heat map overlayed on Google Maps that lets us view popular roads
6. By making it easy to see the most popular roads, this hopefully indicates where the safest roads are

![Sample Output](http://blah.jpg)

# Requirements

This code has been tested on python 2.7 and 3.5.

# Configuration

All .gpx files should be placed under the `courses` directory. After that all that's left to do is run `gps_cluster_parallel.py`.
