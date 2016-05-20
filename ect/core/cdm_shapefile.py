"""
Module Description
==================

Implements the `ESRI Shapefile`_ adapter for the ECT common data model.


.. _ESRI Shapefile: https://www.esri.com/library/whitepapers/pdfs/shapefile.pdf

Module Reference
================
"""

# import fiona
# import shapefile

from .cdm import DatasetAdapter, DatasetCollection


class ShapefileDatasetAdapter(DatasetAdapter):
    def __init__(self, shapefile):
        super(ShapefileDatasetAdapter, self).__init__(shapefile)

    def subset(self, spatial_roi=None, temporal_roi=None):
        # implement me using fiona or pyshp API
        return self

    def close(self):
        # implement me using fiona or pyshp API
        pass


def add_shapefile_dataset(container: DatasetCollection, shapefile):
    container.add_dataset(ShapefileDatasetAdapter(shapefile))

DatasetCollection.add_shapefile_dataset = add_shapefile_dataset
