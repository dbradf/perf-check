from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

import requests
from pydantic import BaseModel
CEDAR_HOST = "https://cedar.mongodb.com"


class PerfResultInfo(BaseModel):

    project: str
    version: str
    order: int
    variant: str
    task_name: str
    task_id: str
    execution: int
    test_name: str
    trial: int
    parent: str
    args: Optional[Dict[str, Any]]

    def get_thread(self) -> str:
        if not self.args:
            return ""
        if threads := self.args.get("thread_level"):
            return str(threads)
        if threads := self.args.get("threads"):
            return str(threads)
        return ""


class PerfStat(BaseModel):

    name: str
    val: Optional[float]
    version: int
    user: bool


class PerfRollups(BaseModel):

    stats: Optional[List[PerfStat]]
    processed_at: Optional[datetime]


class PerfResult(BaseModel):

    name: str
    info: PerfResultInfo
    create_at: Optional[datetime]
    completed_at: Optional[datetime]
    rollups: PerfRollups


class CedarApi:

    def __init__(self, username: str, api_key: str):
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter()
        self.session.mount(f"{urlparse(CEDAR_HOST).scheme}://", adapter)
        self.session.headers.update({"Api-User": username, "Api-Key": api_key})

    def _create_url(self, endpoint: str) -> str:
        return f"{CEDAR_HOST}/{endpoint}"

    def _call_api(self, url):
        response = self.session.get(url)
        response.raise_for_status()
        return response

    def get_test_history(self, task_name: str, variant: str, project: str):
        endpoint = f"rest/v1/perf/task_name/{task_name}?variant={variant}&project={project}"
        url = self._create_url(endpoint)
        response = self._call_api(url)

        return [PerfResult(**r) for r in response.json()]
