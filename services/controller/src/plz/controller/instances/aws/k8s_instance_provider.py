import io
import logging
import socket
import time
from contextlib import closing
from string import Formatter
from typing import Any, Dict, Iterator, Optional
import yaml
import boto3
from kubernetes import client as kubeclient, config as kubeconfig
from kubernetes.client.rest import ApiException

from redis import StrictRedis

from plz.controller.instances.aws.k8s_pod import K8sPod
from plz.controller.images import Images
from plz.controller.instances.instance_base import Instance, \
    InstanceProvider, Parameters
from plz.controller.results.results_base import ResultsStorage
from plz.controller.volumes import Volumes

from .ec2_instance import EC2Instance, InstanceUnavailableException, \
    describe_instances, get_aws_instances, get_tag

log = logging.getLogger(__name__)


class K8sInstanceProvider(InstanceProvider):
    DOCKER_PORT = 2375

    def __init__(self,
                 namespace: str,
                 redis: StrictRedis,
                 results_storage: ResultsStorage,
                 pod_lock_timeout: int):
        super().__init__(results_storage, pod_lock_timeout)
        self.namespace = namespace
        self.redis = redis

    _TEMPLATE = '''
        apiVersion: batch/v1
        kind: Job
        metadata:
          name: plz.{project_name}.{execution_id}
          labels:
            jobgroup: {project_name}
        spec:
          backoffLimit: 1
          template:
            metadata:
              name: {project_name}
              labels:
                jobgroup: {project_name}
            spec:
              containers:
                - name: {project_name}
                  image: {image}
                  imagePullPolicy: Always
              restartPolicy: Never
        '''

    def create_job(self, job_spec, api_instance):
        try:
            api_response = api_instance.create_namespaced_job(self.namespace,
                                                              job_spec)
            return api_response
        except ApiException as e:
            print(
                f"Exception when calling BatchV1Api.create_namespaced"
                f"_job {type(e).__name__}: {e.args}")

    def _k8s_pod_from_pod_data(self, pod_data):
        pod_name = pod_data['metadata']['name']
        return K8sPod(
            redis=self.redis,
            lock_timeout=self.instance_lock_timeout,
            execution_id=self._get_execution_id_from_pod_name(pod_name),
            pod_name=pod_name)

    def _get_execution_id_from_pod_name(self, pod_name):
        return pod_name.rsplit('-', 1)[0].rsplit('.', 1)[1]

    def instance_iterator(self, only_running: bool) -> Iterator[Instance]:
        kubeconfig.load_kube_config()
        core_api_instance = kubeclient.CoreV1Api()
        kwargs = {}
        if only_running:
            kwargs['field_selector'] = 'status.phase=Running'
        try:
            data = core_api_instance.list_namespaced_pod(self.namespace,
                                                         **kwargs)
        except ApiException as e:
            raise RuntimeError(f'Couldn\'t get a list of jobs. '
                               f'Aborting: \n{type(e).__name__}: {e.args}')

        data = data.to_dict()

        for pod_data in data['items']:
            try:
                yield self._k8s_pod_from_pod_data(pod_data)
            except ApiException as e:
                Warning(f'reading logs of {pod["metadata"]["name"]} failed, '
                        f'{type(e).__name__}: {e.args}')

    def get_forensics(self, execution_id) -> dict:
        instance = self.instance_for(execution_id)
        if instance is None:
            return {}
        return instance.get_forensics()

    def run_in_instance(
            self,
            execution_id: str,
            snapshot_id: str,
            parameters: Parameters,
            input_stream: Optional[io.BytesIO],
            instance_market_spec: dict,
            execution_spec: dict,
            max_tries: int = 30,
            delay_in_seconds: int = 5) -> Iterator[Dict[str, Any]]:
        # TODO use docker_run_args and input_stream
        job_spec = yaml.load(
            self._TEMPLATE.format(project_name=execution_spec['project'],
                                  image=f'{images.repository}:{snapshot_id}',
                                  execution_id=execution_id),
            Loader=yaml.SafeLoader)

        kubeconfig.load_kube_config()
        api_instance = kubeclient.BatchV1Api()
        self.create_job(job_spec, api_instance)

    def instance_for(self, execution_id: str) -> Optional[EC2Instance]:
        kubeconfig.load_kube_config()
        core_api_instance = kubeclient.CoreV1Api()
        try:
            data = core_api_instance.list_namespaced_pod(self.namespace,
                                                         field_selector=f'metadata.name=plz.{project_name}.{execution_id}')
        except ApiException as e:
            raise RuntimeError(f'Couldn\'t get a list of jobs. '
                               f'Aborting: \n{type(e).__name__}: {e.args}')

        data = data.to_dict()

        for pod_data in data['items']:
            try:
                yield self._k8s_pod_from_pod_data(pod_data)
            except ApiException as e:
                Warning(f'reading logs of {pod["metadata"]["name"]} failed, '
                        f'{type(e).__name__}: {e.args}')

    def release_instance(self, execution_id: str,
                         fail_if_not_found: bool = True,
                         idle_since_timestamp: Optional[int] = None):
        # TODO make sure that pods aren't deleted when scaling cluster down
        if idle_since_timestamp is None:
            idle_since_timestamp = int(time.time())
        super().release_instance(execution_id,
                                 fail_if_not_found,
                                 idle_since_timestamp)

    def push(self, image_tag):
        self.images.push(image_tag)


def _is_socket_open(host: str, port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex((host, port)) == 0


def _msg(s) -> Dict:
    return {'message': s}
