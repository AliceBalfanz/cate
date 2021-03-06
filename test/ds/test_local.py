import os
import os.path
import tempfile
import unittest
import unittest.mock
import datetime
import shutil
import json
from cate.core.ds import DATA_STORE_REGISTRY, DataAccessError, DataStoreNotice
from cate.core.types import PolygonLike, TimeRangeLike, VarNamesLike
from cate.ds.local import LocalDataStore, LocalDataSource
from cate.ds.esa_cci_odp import EsaCciOdpDataStore
from collections import OrderedDict
from cate.core.types import ValidationError


class LocalDataStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.data_store = LocalDataStore('test', self.tmp_dir)
        self.assertTrue(os.path.isdir(self.tmp_dir))
        self.assertEqual(0, len(os.listdir(self.tmp_dir)))
        self.data_store.add_pattern("ozone", "/DATA/ozone/*/*.nc")
        self.data_store.add_pattern("aerosol", ["/DATA/aerosol/*/*/AERO_V1*.nc", "/DATA/aerosol/*/*/AERO_V2*.nc"])
        self.assertEqual(2, len(os.listdir(self.tmp_dir)))

        self._existing_local_data_store = DATA_STORE_REGISTRY.get_data_store('local')
        DATA_STORE_REGISTRY.add_data_store(LocalDataStore('local', self.tmp_dir))

    def tearDown(self):
        DATA_STORE_REGISTRY.add_data_store(self._existing_local_data_store)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_name_title_and_is_local(self):
        self.assertEqual(self.data_store.id, 'test')
        self.assertEqual(self.data_store.title, 'Local Data Sources')
        self.assertEqual(self.data_store.is_local, True)

    def test_description(self):
        self.assertIsNotNone(self.data_store.description)
        self.assertTrue(len(self.data_store.description) > 40)

    def test_notices(self):
        self.assertIsInstance(self.data_store.notices, list)
        self.assertEqual(1, len(self.data_store.notices))

        notice0 = self.data_store.notices[0]
        self.assertIsInstance(notice0, DataStoreNotice)
        self.assertEqual(notice0.id, "localDataStorage")
        self.assertEqual(notice0.title, "Local Data Storage")
        self.assertEqual(notice0.icon, "info-sign")
        self.assertEqual(notice0.intent, "primary")
        self.assertTrue(len(notice0.content) > 20)

    def test_create_data_source(self):
        new_ds_id = 'test_name.2008'
        new_ds = self.data_store.create_data_source(new_ds_id)
        self.assertEqual("test.%s" % new_ds_id, new_ds.id)

        new_ds_id = 'test_name.2008-10'
        new_ds = self.data_store.create_data_source(new_ds_id)
        self.assertEqual("test.%s" % new_ds_id, new_ds.id)

        new_ds_id = 'test_name.200*'
        with self.assertRaises(ValidationError) as cm:
            self.data_store.create_data_source(new_ds_id)
        self.assertEqual('Unaccepted characters in data source name "{}"'.format(new_ds_id), str(cm.exception))

        new_ds_id = 'test_name.200 '
        with self.assertRaises(ValidationError) as cm:
            self.data_store.create_data_source(new_ds_id)
        self.assertEqual('Unaccepted characters in data source name "{}"'.format(new_ds_id), str(cm.exception))

        new_ds_id = 'test name.2000'
        with self.assertRaises(ValidationError) as cm:
            self.data_store.create_data_source(new_ds_id)
        self.assertEqual('Unaccepted characters in data source name "{}"'.format(new_ds_id), str(cm.exception))

    def test_add_pattern(self):
        data_sources = self.data_store.query()
        self.assertIsNotNone(data_sources)
        self.assertEqual(len(data_sources), 2)

        new_ds_name = 'a_name'
        new_ds = self.data_store.add_pattern(new_ds_name, "a_pat")

        self.assertEqual("test.%s" % new_ds_name, new_ds.id)

        data_sources = self.data_store.query()
        self.assertEqual(len(data_sources), 3)

        with self.assertRaises(DataAccessError) as cm:
            self.data_store.add_pattern("a_name", "a_pat2")
        self.assertEqual('Data source "test.a_name" already exists.'.format(
            self.data_store.id, self.data_store.id, new_ds_name), str(cm.exception))

        data_sources = self.data_store.query()
        self.assertEqual(len(data_sources), 3)

    def test__repr_html(self):
        html = self.data_store._repr_html_()
        self.assertEqual(524, len(html), html)

    def test_init(self):
        data_store2 = LocalDataStore('test', self.tmp_dir)
        data_sources = data_store2.query()
        self.assertIsNotNone(data_sources)
        # self.assertEqual(len(data_sources), 2)

    def test_query(self):
        local_data_store = LocalDataStore('test', os.path.join(os.path.dirname(__file__),
                                                               'resources/datasources/local/'))
        data_sources = local_data_store.query()
        self.assertEqual(len(data_sources), 2)

        data_sources = local_data_store.query(ds_id='local')
        self.assertEqual(len(data_sources), 1)
        self.assertIsNone(data_sources[0].temporal_coverage())

        data_sources = local_data_store.query(ds_id='local_w_temporal')
        self.assertEqual(len(data_sources), 1)
        self.assertIsNotNone(data_sources[0].temporal_coverage())

    def test_load_old_datasource_from_json_dict(self):
        test_data = {
            'name': 'local.test_name',
            'meta_data': {
                'temporal_coverage': "2001-01-01 00:00:00,2001-01-31 23:59:59",
                'spatial_coverage': "-180,-90,180,90",
                'variables': ['var_test_1', 'var_test_2'],
            },
            "meta_info": {
            },
            'files': [['file_1', '2002-02-01 00:00:00', '2002-02-01 23:59:59'],
                      ['file_2', '2002-03-01 00:00:00', '2002-03-01 23:59:59']]
        }
        data_source = LocalDataSource.from_json_dict(json_dict=test_data, data_store=self.data_store)
        self.assertIsNotNone(data_source)
        self.assertEqual(data_source.temporal_coverage(),
                         TimeRangeLike.convert(test_data.get('meta_data').get('temporal_coverage')))
        self.assertEqual(data_source.spatial_coverage(),
                         PolygonLike.convert(test_data.get('meta_data').get('spatial_coverage')))
        self.assertListEqual([var.get('name') for var in data_source.variables_info],
                             test_data.get('meta_data').get('variables'))

        test_data = {
            'name': 'local.test_name',
            'meta_data': {
                'temporal_covrage': "2001-01-01 00:00:00,2001-01-31 23:59:59",
                'spatial_coverage': "-180,-90,180,90",
                'variables': ['var_test_1', 'var_test_2'],
            },
            "meta_info": {
            },
            'files': [['file_1', '2002-02-01 00:00:00', '2002-02-01 23:59:59'],
                      ['file_2', '2002-03-01 00:00:00', '2002-03-01 23:59:59']]
        }
        data_source = LocalDataSource.from_json_dict(json_dict=test_data, data_store=self.data_store)
        self.assertIsNotNone(data_source)
        self.assertEqual(data_source.temporal_coverage(),
                         TimeRangeLike.convert(test_data.get('meta_data').get('temporal_covrage')))
        self.assertEqual(data_source.spatial_coverage(),
                         PolygonLike.convert(test_data.get('meta_data').get('spatial_coverage')))
        self.assertListEqual([var.get('name') for var in data_source.variables_info],
                             test_data.get('meta_data').get('variables'))

    def test_load_datasource_from_json_dict(self):
        test_data = {
            'name': 'local.test_name2',
            "meta_info": {
                "temporal_coverage_start": "2001-01-01T00:00:00",
                "temporal_coverage_end": "2001-01-31T23:59:59",
                "bbox_maxx": "180.0",
                "bbox_maxy": "90.0",
                "bbox_minx": "-180.0",
                "bbox_miny": "-90.0",
                "variables": [
                    {
                        "name": "var_1",
                        "units": "kelvin",
                        "long_name": "var_1 long name..",
                        "standard_name": "std_var_1"
                    },
                    {
                        "name": "var_2",
                        "units": "celsius",
                        "long_name": "var_2 long name..",
                        "standard_name": "std_var_2"
                    }
                ]
            },
            'files': [['file_1', '2002-02-01 00:00:00', '2002-02-01 23:59:59'],
                      ['file_2', '2002-03-01 00:00:00', '2002-03-01 23:59:59']]
        }
        data_source = LocalDataSource.from_json_dict(json_dict=test_data, data_store=self.data_store)
        self.assertIsNotNone(data_source)
        self.assertEqual(data_source.temporal_coverage(),
                         TimeRangeLike.convert("{},{}".format(
                             test_data.get('meta_info').get('temporal_coverage_start'),
                             test_data.get('meta_info').get('temporal_coverage_end')))
                         )
        self.assertEqual(data_source.spatial_coverage(),
                         PolygonLike.convert(",".join([
                             test_data.get('meta_info').get('bbox_minx'),
                             test_data.get('meta_info').get('bbox_miny'),
                             test_data.get('meta_info').get('bbox_maxx'),
                             test_data.get('meta_info').get('bbox_maxy'),
                         ])))
        self.assertListEqual(data_source.variables_info, test_data.get('meta_info').get('variables'))

    def test_cache_synch(self):
        #
        # check if test.asynch is not present
        #
        ds_asynch = self.data_store.query('test.asynch')
        self.assertEqual(len(ds_asynch), 0)
        #
        # manualy create test-asynch dataset to simulate
        # an copy from a second process
        #
        test_asynch = {
            "name": "test.asynch",
            "meta_info": {
                "status": "PROCESSING"
            },
            "files": [
                ["/DATA/asynch/*/*.nc"]
            ]
        }
        json_file = os.path.join(self.data_store.data_store_path, 'test.asynch.json')
        with open(json_file, 'w') as f:
            json.dump(test_asynch, f)
        #
        # check the new dataset is not visible
        #
        ds_asynch = self.data_store.query('test.asynch')
        self.assertEqual(len(ds_asynch), 0)
        #
        # invalidate the cache and check if the new dataset
        # is now visible
        #
        self.data_store.invalidate()
        ds_asynch = self.data_store.query('test.asynch')
        self.assertEqual(len(ds_asynch), 1)


class LocalDataSourceTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self._dummy_store = LocalDataStore('dummy', 'dummy')

        self._local_data_store = LocalDataStore('test', os.path.join(os.path.dirname(__file__),
                                                                     'resources/datasources/local/'))

        self.ds1 = LocalDataSource("ozone",
                                   ["/DATA/ozone/*/*.nc"],
                                   self._dummy_store)
        self.ds2 = LocalDataSource("aerosol",
                                   ["/DATA/aerosol/*/A*.nc", "/DATA/aerosol/*/B*.nc"],
                                   self._dummy_store)

        self.empty_ds = LocalDataSource("empty",
                                        [],
                                        self._dummy_store)

        self.ds3 = LocalDataSource("w_temporal_1",
                                   OrderedDict([
                                       ("/DATA/file1.nc",
                                        (datetime.datetime(2017, 1, 27, 0, 0),
                                         datetime.datetime(2017, 1, 28, 0, 0))),
                                       ("/DATA/file2.nc",
                                        (datetime.datetime(2017, 1, 28, 0, 0),
                                         datetime.datetime(2017, 1, 29, 0, 0)))]),
                                   self._dummy_store)

        self.ds4 = LocalDataSource("w_temporal_2",
                                   OrderedDict(),
                                   self._dummy_store)

        self.assertIsNotNone(self.ds1)
        self.assertIsNotNone(self.ds2)
        self.assertIsNotNone(self.empty_ds)
        self.assertIsNotNone(self.ds3)
        self.assertIsNotNone(self.ds4)

        self._existing_local_data_store = DATA_STORE_REGISTRY.get_data_store('local')
        DATA_STORE_REGISTRY.add_data_store(LocalDataStore('local', self.tmp_dir))

    def tearDown(self):
        DATA_STORE_REGISTRY.add_data_store(self._existing_local_data_store)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_data_store(self):
        self.assertIs(self.ds1.data_store, self._dummy_store)
        self.assertIs(self.ds2.data_store, self._dummy_store)
        self.assertIs(self.empty_ds.data_store, self._dummy_store)
        self.assertIs(self.ds3.data_store, self._dummy_store)
        self.assertIs(self.ds4.data_store, self._dummy_store)

    def test_id(self):
        self.assertEqual(self.ds1.id, 'ozone')
        self.assertEqual(self.ds2.id, 'aerosol')
        self.assertEqual(self.empty_ds.id, 'empty')
        self.assertEqual(self.ds3.id, 'w_temporal_1')
        self.assertEqual(self.ds4.id, 'w_temporal_2')

    def test_schema(self):
        self.assertEqual(self.ds1.schema, None)
        self.assertEqual(self.ds2.schema, None)
        self.assertEqual(self.empty_ds.schema, None)
        self.assertEqual(self.ds3.schema, None)
        self.assertEqual(self.ds4.schema, None)

    def test_info_string(self):
        self.assertEqual('Files: /DATA/ozone/*/*.nc', self.ds1.info_string)
        self.assertEqual('Files: /DATA/aerosol/*/A*.nc /DATA/aerosol/*/B*.nc', self.ds2.info_string)
        self.assertEqual('Files: ', self.empty_ds.info_string)
        self.assertEqual('Files: /DATA/file1.nc /DATA/file2.nc', self.ds3.info_string)
        self.assertEqual('Files: ', self.ds4.info_string)

    def test_temporal_coverage(self):
        self.assertEqual(self.ds1.temporal_coverage(), None)
        self.assertEqual(self.ds2.temporal_coverage(), None)
        self.assertEqual(self.empty_ds.temporal_coverage(), None)
        self.assertEqual(self.ds3.temporal_coverage(), (datetime.datetime(2017, 1, 27, 0, 0),
                                                        datetime.datetime(2017, 1, 29, 0, 0)))
        self.assertEqual(self.ds4.temporal_coverage(), None)

    def test_to_json_dict(self):
        self.assertEqual(self.ds1.to_json_dict().get('name'), 'ozone')
        self.assertEqual(self.ds1.to_json_dict().get('files'),
                         [['/DATA/ozone/*/*.nc']])

        self.assertEqual(self.ds2.to_json_dict().get('name'), 'aerosol')
        self.assertEqual(self.ds2.to_json_dict().get('files'),
                         [["/DATA/aerosol/*/A*.nc"], ["/DATA/aerosol/*/B*.nc"]])

        self.assertEqual(self.empty_ds.to_json_dict().get('name'), 'empty')
        self.assertEqual(self.empty_ds.to_json_dict().get('files'), [])

        self.assertEqual(self.ds3.to_json_dict().get('name'), 'w_temporal_1')
        self.assertEqual(self.ds3.to_json_dict().get('files'),
                         [["/DATA/file1.nc",
                           datetime.datetime(2017, 1, 27, 0, 0), datetime.datetime(2017, 1, 28, 0, 0)],
                          ["/DATA/file2.nc",
                           datetime.datetime(2017, 1, 28, 0, 0), datetime.datetime(2017, 1, 29, 0, 0)]])

        self.assertEqual(self.ds4.to_json_dict().get('name'), 'w_temporal_2')
        self.assertEqual(self.ds4.to_json_dict().get('files'), [])

    @unittest.skip
    def test_add_dataset(self):
        self.ds1.add_dataset('/DATA/ozone2/*/*.nc'),
        self.assertEqual(self.ds1.to_json_dict().get('files'),
                         [('/DATA/ozone/*/*.nc', None), ('/DATA/ozone2/*/*.nc', None)])

        self.ds2.add_dataset('/DATA/aerosol/*/B*.nc', datetime.datetime(2017, 2, 27, 0, 0))
        self.assertEqual(self.ds2.to_json_dict().get('files'),
                         [("/DATA/aerosol/*/A*.nc", None), ("/DATA/aerosol/*/B*.nc", None)])

        self.ds2.add_dataset('/DATA/aerosol/*/B*.nc', datetime.datetime(2017, 2, 27, 0, 0), True)
        self.assertEqual(self.ds2.to_json_dict().get('files'),
                         [("/DATA/aerosol/*/B*.nc", datetime.datetime(2017, 2, 27, 0, 0)),
                          ("/DATA/aerosol/*/A*.nc", None)])

        self.empty_ds.add_dataset('/DATA/test.nc')
        self.assertEqual(self.empty_ds.to_json_dict().get('files'), [('/DATA/test.nc', None)])

        self.ds3.add_dataset('/DATA/file_new.nc', datetime.datetime(2017, 2, 26, 0, 0))
        self.assertEqual(self.ds3.to_json_dict().get('files'),
                         [("/DATA/file_new.nc", datetime.datetime(2017, 2, 26, 0, 0)),
                          ("/DATA/file1.nc", datetime.datetime(2017, 2, 27, 0, 0)),
                          ("/DATA/file2.nc", datetime.datetime(2017, 2, 28, 0, 0))])
        self.assertEqual(self.ds3.temporal_coverage(), (datetime.datetime(2017, 2, 26, 0, 0),
                                                        datetime.datetime(2017, 2, 28, 0, 0)))

    def test_open_dataset(self):
        ds = self._local_data_store.query('local')[0]

        xr = ds.open_dataset()
        self.assertIsNotNone(xr)
        self.assertEqual(xr.coords.dims.get('time'), 3)

        with self.assertRaises(DataAccessError):
            ds.open_dataset(time_range=(datetime.datetime(1978, 11, 14),
                                        datetime.datetime(1978, 11, 15)))

        ds = self._local_data_store.query('local_w_temporal')[0]

        xr = ds.open_dataset()
        self.assertIsNotNone(xr)
        self.assertEqual(xr.coords.dims.get('time'), 3)

        xr = ds.open_dataset(time_range=(datetime.datetime(1978, 11, 14),
                                         datetime.datetime(1978, 11, 15)))
        self.assertIsNotNone(xr)
        self.assertEqual(xr.coords.dims.get('time'), 1)

        with self.assertRaises(DataAccessError):
            ds.open_dataset(time_range=(datetime.datetime(1978, 11, 20),
                                        datetime.datetime(1978, 11, 21)))

    def test_make_local(self):
        data_source = self._local_data_store.query('local_w_temporal')[0]

        with unittest.mock.patch.object(EsaCciOdpDataStore, 'query', return_value=[]):
            new_ds_title = 'from_local_to_local'
            new_ds_time_range = TimeRangeLike.convert((datetime.datetime(1978, 11, 14, 0, 0),
                                                       datetime.datetime(1978, 11, 15, 23, 59)))
            new_ds = data_source.make_local(new_ds_title, time_range=new_ds_time_range)
            self.assertIsNotNone(new_ds)

            self.assertEqual(new_ds.id, "local.%s" % new_ds_title)
            self.assertEqual(new_ds.temporal_coverage(), TimeRangeLike.convert(
                (datetime.datetime(1978, 11, 14, 0, 0),
                 datetime.datetime(1978, 11, 15, 23, 59))))

            new_ds_2_title = 'from_local_to_local_var'
            new_ds_2_time_range = TimeRangeLike.convert((datetime.datetime(1978, 11, 14, 0, 0),
                                                         datetime.datetime(1978, 11, 15, 23, 59)))
            new_ds_2_vars = VarNamesLike.convert(['sm'])

            new_ds_w_one_variable = data_source.make_local(new_ds_2_title,
                                                           time_range=new_ds_2_time_range,
                                                           var_names=new_ds_2_vars)
            self.assertIsNotNone(new_ds_w_one_variable)
            self.assertEqual(new_ds_w_one_variable.id, "local.%s" % new_ds_2_title)
            data_set = new_ds_w_one_variable.open_dataset()
            self.assertSetEqual(set(data_set.variables), {'sm', 'lat', 'lon', 'time'})

            new_ds_3_title = 'from_local_to_local_range'
            new_ds_3_time_range = TimeRangeLike.convert((datetime.datetime(1978, 11, 14, 0, 0),
                                                         datetime.datetime(1978, 11, 15, 23, 59)))
            new_ds_3_vars = VarNamesLike.convert(['sm'])
            new_ds_3_region = PolygonLike.convert("10,10,20,20")

            new_ds_w_region = data_source.make_local(new_ds_3_title,
                                                     time_range=new_ds_3_time_range,
                                                     var_names=new_ds_3_vars,
                                                     region=new_ds_3_region)  # type: LocalDataSource
            self.assertIsNotNone(new_ds_w_region)
            self.assertEqual(new_ds_w_region.id, "local.%s" % new_ds_3_title)
            self.assertEqual(new_ds_w_region.spatial_coverage(), PolygonLike.convert("10,10,20,20"))
            data_set = new_ds_w_region.open_dataset()
            self.assertSetEqual(set(data_set.variables), {'sm', 'lat', 'lon', 'time'})

            no_data = data_source.make_local('no_data',
                                             time_range=(datetime.datetime(2020, 11, 14, 0, 0),
                                                         datetime.datetime(2020, 11, 15, 23, 59)))
            self.assertIsNone(no_data)

    def test_remove_data_source_by_id(self):
        data_sources = self._local_data_store.query('local_w_temporal')
        data_sources_len_before_remove = len(data_sources)
        self.assertGreater(data_sources_len_before_remove, 0)

        with unittest.mock.patch.object(os, 'remove', return_value=None):
            self._local_data_store.remove_data_source('local_w_temporal')
        data_sources = self._local_data_store.query('local_w_temporal')
        data_sources_len_after_remove = len(data_sources)
        self.assertGreater(data_sources_len_before_remove, data_sources_len_after_remove)

    def test_remove_data_source(self):
        data_sources = self._local_data_store.query('local_w_temporal')
        data_sources_len_before_remove = len(data_sources)
        self.assertGreater(data_sources_len_before_remove, 0)

        with unittest.mock.patch.object(os, 'remove', return_value=None):
            self._local_data_store.remove_data_source(data_sources[0])
        data_sources = self._local_data_store.query('local_w_temporal')
        data_sources_len_after_remove = len(data_sources)
        self.assertGreater(data_sources_len_before_remove, data_sources_len_after_remove)

    def test_validation_error(self):
        ds = self._local_data_store.query('local')[0]
        with self.assertRaises(ValidationError):
            ds.open_dataset(time_range=(datetime.datetime(1974, 1, 1),
                                        datetime.datetime(1975, 1, 1)),
                            region=(1, -1, 3, 6),
                            var_names=('pippo', ))
