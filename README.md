# gps-cycle-clustering

The goal of this project is to parse an arbitrary set of GPX-formatted GPS cycling data to:

1. Deduplicate the courses so that even if one has multiple loops only one will count
2. Attempt to remove non-cycling activity from courses (e.g. walking)
3. Aggregate the location data and attempt to cluster nearby points together; this should give an indication of the popularity of certain roads
4. Sort the resultant clustered location data
5. Output a .csv that can be used in e.g. http://www.gpsvisualizer.com/ that can generate a heat map overlayed on Google Maps that lets us view popular roads
6. By making it easy to see the most popular roads, this hopefully indicates where the safest roads are

Here's an example of the result.

![Sample Output](http://i.imgur.com/olMOUs9.png)

The higher values of n (from the color legend) are more popular points, and you can see several roads appearing with a strong consensus. All roads shown have at least a consensus of two different courses.

# Requirements

This code has been tested on python 2.7 and 3.5.

# Configuration

Create a directory called `courses` in the same directory as the python script. All .gpx files should be placed under the `courses` directory. After that all that's left to do is run `gps_cluster_parallel.py`.

# Issues

Most concerning is potential sources of bias. In the example output from the top these courses were attempted to be pruned to exclude organized rides because they may go on roads that are ordinarilly not necessarily safe. This may not be able to be automated. The selection of courses is also a source of bias; the broad question this project wants to answer is what roads are safe by consensus, but if all the courses come from the same source or the same relatively small set of people this could yield misleading results. In the example result above the input data was about 249 .gpx courses publicly available from MapMyRide.
