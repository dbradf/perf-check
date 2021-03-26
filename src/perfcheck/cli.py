from collections import defaultdict
from datetime import datetime, timedelta
from pprint import PrettyPrinter
from typing import NamedTuple

import click
from evergreen import EvergreenApi
from perfcheck.cedar import CedarApi

PP = PrettyPrinter()

TASK_FILTER = {"genny_auto_tasks", "genny_patch_tasks"}

order_map = {}


class ResultId(NamedTuple):

    project: str
    variant: str
    task: str
    test_name: str
    metric: str
    thread_level: str


class DataGatherService:

    def __init__(self, evg_api: EvergreenApi, cedar_api: CedarApi, verbose: bool, cutoff: datetime):
        self.evg_api = evg_api
        self.cedar_api = cedar_api
        self.verbose = verbose
        self.cutoff = cutoff

    def gather_build_data(self, build_id: str):
        build = self.evg_api.build_by_id(build_id)
        evg_results = defaultdict(dict)
        cedar_results = defaultdict(dict)
        for task in build.get_tasks():
            if task.display_name in TASK_FILTER:
                continue
            if task.is_success():
                self.from_evg(task.task_id, evg_results)
                self.from_cedar(task.task_id, cedar_results)

        return evg_results, cedar_results

    def from_evg(self, task_id: str, results):
        task = self.evg_api.task_by_id(task_id)
        task_name = task.display_name

        perf_data = self.evg_api.performance_results_by_task_name(task_id, task_name)
        for p in perf_data:
            if p.create_time < self.cutoff:
                continue

            order_map[p.order] = p.revision
            if self.verbose:
                print(f"{p.revision}: {p.order}")
            for tr in p.test_batch.test_runs:
                if self.verbose:
                    print(f"-{tr.test_name}")
                for r in tr.test_results:
                    result_id = ResultId(
                        project=task.project_id,
                        variant=task.build_variant,
                        task=task.display_name,
                        test_name=tr.test_name,
                        metric=r.measurement,
                        thread_level=r.thread_level
                    )
                    results[p.order][result_id] = r.mean_value
                    if self.verbose:
                        print(f"  - {r.measurement} - {r.thread_level}: {r.mean_value}")

        return results

    def from_cedar(self, task_id: str, results):
        task = self.evg_api.task_by_id(task_id)
        perf_data = self.cedar_api.get_test_history(task.display_name, task.build_variant, task.project_id)
        for p in perf_data:
            if p.create_at and p.create_at < self.cutoff:
                continue

            if self.verbose:
                print(f"{p.info.order}")
                print(f"- {p.info.test_name}")
            if not p.rollups.stats:
                continue
            for r in p.rollups.stats:
                result_id = ResultId(
                    project=task.project_id,
                    variant=task.build_variant,
                    task=task.display_name,
                    test_name=p.info.test_name,
                    metric=r.name,
                    thread_level=p.info.get_thread()
                )
                results[p.info.order][result_id] = r.val
                if self.verbose:
                    print(f"  - {r.name} - {p.info.args}: {r.val}")

        return results


@click.command()
@click.option("--build-id")
@click.option("--verbose", default=False, is_flag=True)
@click.option("--weeks-back", default=4, type=int)
def cli(build_id: str, verbose: bool, weeks_back: int) -> None:
    evg_api = EvergreenApi.get_api(use_config_file=True)
    cedar_api = CedarApi(evg_api._auth.username, evg_api._auth.api_key)
    cutoff = datetime.utcnow() - timedelta(weeks=weeks_back)

    service = DataGatherService(evg_api, cedar_api, verbose, cutoff)

    evg_results, cedar_results = service.gather_build_data(build_id)

    min_order = min(cedar_results.keys())

    print("="*80)
    print("Diffs")
    print("="*80)

    correct = 0
    missing_order = []
    missing_result = []
    incorrect = []
    for order in evg_results.keys():
        if order < min_order:
            continue
        evg = evg_results[order]
        cedar = cedar_results.get(order)
        if cedar is None:
            missing_order.append(order)
            print(f"!!!! No cedar results for order: {order}, {order_map[order]} !!!!")
            PP.pprint(evg)
        else:
            for evg_result, evg_value in evg.items():
                if evg_result.thread_level == "max":
                    continue
                if evg_result not in cedar:
                    missing_result.append(evg_result)
                    print(f""" #### No cedar result for result {order} {order_map[order]}: {evg_result} ##### """)
                else:
                    cedar_value = cedar[evg_result]
                    if abs(evg_value - cedar_value) > 0.0001:
                        incorrect.append(evg_result)
                        print(f" $$$$ Mismatch result {order}, evg={evg_value} =/= cedar={cedar_value} $$$$")
                        print(evg_result)
                    else:
                        correct += 1

    print("="*80)
    print(f"Correct: {correct}")
    print(f"Missing Order: {len(missing_order)}")
    print(f"Missing Result: {len(missing_result)}")
    print(f"Incorrect result: {len(incorrect)}")


def main():
    """Entry point into commandline."""
    return cli(obj={})
