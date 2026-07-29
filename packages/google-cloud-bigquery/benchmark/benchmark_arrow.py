# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Benchmark for query_and_wait and to_arrow."""

import argparse
import os
import sys
import time

from google.api_core import exceptions
from google.cloud import bigquery


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark query_and_wait and to_arrow."
    )
    parser.add_argument(
        "--BIGQUERY_READ_ROWS_FROM_JOB_ID",
        "--read-rows-from-job-id",
        action="store_true",
        help="Enable BIGQUERY_READ_ROWS_FROM_JOB_ID environment variable.",
    )
    parser.add_argument(
        "--project_id",
        "--project-id",
        type=str,
        default=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        help="GCP Project ID.",
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="The SQL query to execute.",
    )
    parser.add_argument(
        "--location",
        type=str,
        default="US",
        help="Location where the job should run.",
    )
    parser.add_argument(
        "--reruns",
        type=int,
        default=3,
        help="Number of times to run the benchmark.",
    )
    parser.add_argument(
        "--use_query_cache",
        "--use-query-cache",
        action="store_true",
        default=False,
        help="Enable BigQuery query caching (default: False).",
    )
    args = parser.parse_args()

    project_id = getattr(args, "project_id", None)
    if not project_id:
        print(
            "Error: --project_id or GOOGLE_CLOUD_PROJECT environment variable is required.",
            file=sys.stderr,
        )
        sys.exit(1)

    return args


def main():
    args = _parse_args()

    read_rows_from_job_id = getattr(args, "BIGQUERY_READ_ROWS_FROM_JOB_ID", False)
    if read_rows_from_job_id:
        os.environ["BIGQUERY_READ_ROWS_FROM_JOB_ID"] = "true"
        print("BIGQUERY_READ_ROWS_FROM_JOB_ID is ENABLED")
    else:
        os.environ["BIGQUERY_READ_ROWS_FROM_JOB_ID"] = "false"
        print("BIGQUERY_READ_ROWS_FROM_JOB_ID is DISABLED")

    project_id = getattr(args, "project_id", None)
    print(f"Project ID: {project_id}")
    print(f"Location:   {args.location}")
    print(f"Query:      {args.query}")
    print(f"Reruns:     {args.reruns}")
    print("-" * 40)

    client = bigquery.Client(project=project_id, location=args.location)
    job_config = bigquery.QueryJobConfig(use_query_cache=args.use_query_cache)

    successful_runs = 0
    failed_runs = 0
    total_query_time = 0.0
    total_arrow_time = 0.0
    total_exec_time = 0.0

    for i in range(args.reruns):
        print(f"Run {i + 1}/{args.reruns}...")

        try:
            start_time = time.perf_counter()
            row_iterator = client.query_and_wait(
                args.query,
                project=project_id,
                location=args.location,
                job_config=job_config,
            )
            query_end_time = time.perf_counter()

            arrow_table = row_iterator.to_arrow()
            end_time = time.perf_counter()

            query_time = query_end_time - start_time
            arrow_time = end_time - query_end_time
            total_time = end_time - start_time

            total_query_time += query_time
            total_arrow_time += arrow_time
            total_exec_time += total_time
            successful_runs += 1

            print(f"  Query time: {query_time:.4f}s")
            print(f"  Arrow time: {arrow_time:.4f}s")
            print(f"  Total time: {total_time:.4f}s")
            print(
                f"  Rows fetched: {arrow_table.num_rows}, Columns: {arrow_table.num_columns}"
            )
        except exceptions.GoogleAPICallError as exc:
            failed_runs += 1
            print(f"  Run failed (API Error): {exc}", file=sys.stderr)
        except Exception as exc:
            failed_runs += 1
            print(f"  Run failed (Unexpected Error): {exc}", file=sys.stderr)

        print("-" * 40)

    print("\nBenchmark Summary:")
    print(f"  Total runs:      {args.reruns}")
    print(f"  Successful runs: {successful_runs}")
    print(f"  Failed runs:     {failed_runs}")
    if successful_runs > 0:
        avg_query = total_query_time / successful_runs
        avg_arrow = total_arrow_time / successful_runs
        avg_total = total_exec_time / successful_runs
        print(f"  Average Query time: {avg_query:.4f}s")
        print(f"  Average Arrow time: {avg_arrow:.4f}s")
        print(f"  Average Total time: {avg_total:.4f}s")


if __name__ == "__main__":
    main()
