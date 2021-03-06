import json
import requests

from automon.log import Logging
from automon.integrations.elasticsearch.client import ElasticsearchClient
from automon.integrations.elasticsearch.config import ElasticsearchConfig


class Snapshot:
    def __init__(self, snapshot: dict):
        self._log = Logging(Snapshot.__name__, Logging.DEBUG)

        self.snapshot = snapshot
        self.id = snapshot.get('id')
        self.status = snapshot.get('status')
        self.start_epoch = snapshot.get('start_epoch')
        self.start_time = snapshot.get('start_time')
        self.end_epoch = snapshot.get('end_epoch')
        self.end_time = snapshot.get('end_time')
        self.duration = snapshot.get('duration')
        self.indices = snapshot.get('indices')
        self.successful_shards = snapshot.get('successful_shards')
        self.failed_shards = snapshot.get('failed_shards')
        self.total_shards = snapshot.get('total_shards')

    def __eq__(self, other):
        if not isinstance(other, Snapshot):
            self._log.error(NotImplemented)
            return NotImplemented

        return self.snapshot == other.snapshot


class ElasticsearchSnapshotMonitor:
    def __init__(self, endpoint: str, elasticsearch_repository: str, snapshots_prefix: str):
        self._log = Logging(ElasticsearchSnapshotMonitor.__name__, Logging.DEBUG)

        self._config = ElasticsearchConfig(endpoint)
        self._client = ElasticsearchClient(self._config)

        self._endpoint = self._client.config.es_hosts
        self._repository = elasticsearch_repository
        self._snapshots_prefix = snapshots_prefix

        self.snapshots = []
        self.total_snapshots = None
        self.good_snapshots = []
        self.bad_snapshots = []
        self.error = None

    def _get_all_snapshots(self) -> bool:
        url = f'{self._endpoint}/_cat/snapshots/{self._repository}?format=json&pretty'

        self._log.info('Downloading snapshots list')
        content = self._client.rest(url)

        if content:
            snapshots = json.loads(content)
            return self._process_snapshots(snapshots)

        return False

    def _process_snapshots(self, snapshots: dict) -> bool:
        self._log.info('Processing snapshots')

        try:
            self.total_snapshots = list(snapshots).__len__()

            self._log.info(f'{self.total_snapshots} snapshots')

            for snapshot in snapshots:

                s = Snapshot(snapshot)

                id = s.id
                status = s.status

                if self._snapshots_prefix in id:

                    self.snapshots.append(s)

                    if status == 'SUCCESS' or status == 'success':
                        self.good_snapshots.append(s)
                    else:
                        self.bad_snapshots.append(s)

            return True

        except:
            self._log.error('Unable to get snapshots')
            self.error = SnapshotError(snapshots)
            return False

    def read_file(self, file_path):
        self._log.info('Reading snapshots from file')

        with open(file_path, 'rb') as snapshots:
            snapshots = json.load(snapshots)

        self._process_snapshots(snapshots)

    def check_snapshots(self):
        self._log.info('Checking snapshots')
        return self._get_all_snapshots()


# class ElasticsearchSnapshotMonitorDepreciated:
#     def __init__(self, elasticsearch_endpoint, elasticsearch_repository, snapshots_prefix):
#
#         self.endpoint = elasticsearch_endpoint
#         self.repository = elasticsearch_repository
#         self.snapshots_prefix = snapshots_prefix
#         self.snapshots = []
#         self.good_snapshots = []
#         self.bad_snapshots = []
#
#     def _get_all_snapshots(self, file=None):
#         url = f'{self.endpoint}/_cat/snapshots/{self.repository}?format=json&pretty'
#
#         if file:
#             with open(file, 'rb') as snapshots:
#                 snapshots = json.load(snapshots)
#         else:
#             snapshots = requests.get(url).content
#             snapshots = json.loads(snapshots)
#
#         for snapshot in snapshots:
#
#             s = Snapshot(snapshot)
#             id = s.id
#             status = s.status
#
#             if self.snapshots_prefix in id:
#
#                 self.snapshots.append(s)
#
#                 if status == 'SUCCESS' or status == 'success':
#                     self.good_snapshots.append(s)
#                 else:
#                     self.bad_snapshots.append(s)
#
#     def read_file(self, file):
#         self._get_all_snapshots(file)
#
#     def check_snapshots(self):
#         self._get_all_snapshots()


class SnapshotError:
    def __init__(self, error: dict):
        self._log = Logging(SnapshotError.__name__, Logging.DEBUG)

        self.error = error.get('error')

        if self.error:
            self.root_cause = self.error.get('root_cause')
            self.type = self.error.get('type')
            self.reason = self.error.get('reason')
            if self.error.get('caused_by'):
                self.cause_by_type = self.error.get('caused_by')['type']
                self.cause_by_reason = self.error.get('caused_by')['reason']
                self.cause_by_type_nested = self.error.get('caused_by')['caused_by']['type']
                self.cause_by_reason_nested = self.error.get('caused_by')['caused_by']['reason']
            self.status = error.get('status')

    def __eq__(self, other):
        if not isinstance(other, SnapshotError):
            self._log.error(NotImplemented)
            return NotImplemented
        return self.error == other.error
