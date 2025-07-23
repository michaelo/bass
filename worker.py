#!/usr/bin/env python3
import json
import logging
import time
import tempfile
import os
import subprocess
import argparse
import bass
from bass import create_log_sender
from bass.core import ExecStatus, exec_status_to_otel

logging.getLogger().setLevel(logging.INFO)

# class ProcessState(Enum):
#     GOT_REPO = 0

def process(job: dict, args) -> ExecStatus:
    logger = create_log_sender(job["otel"]["logs-endpoint"], job["otel"]["service-name"], job["otel"]["trace-id"])
    logging.info("Processing: %s", job["name"])
    status = ExecStatus.UNKNOWN

    # Create workspace specific for the pipeline, ignore if already exists
    # Ensure local clone/workspace represents both pipeline and repository
    repository_escaped = job["pipeline"]["repository"].replace("\\", "-").replace("/", "-")
    tmpdir = f"{args.workspace_root}/pipeline/{job["name"]}/{repository_escaped}"
    logging.info("Workspace: %s", tmpdir)
    try:
        os.makedirs(tmpdir)
    except FileExistsError:
        pass

    try:
        # TODO: Span for initial steps
        os.chdir(tmpdir)

        if os.path.exists(f"{tmpdir}/.git"):
            logging.info("Updating repository '%s' in: '%s'", job["pipeline"]["repository"], tmpdir)
            subprocess.call(["git","clean","-xdf"])
            subprocess.call(["git","pull"])
        else:
            logging.info("Cloning repository '%s' to: '%s'", job["pipeline"]["repository"], tmpdir)
            subprocess.call(["git", "clone", job["pipeline"]["repository"], "."])

        logging.info(f"Checking out: {job["pipeline"]["ref"]}")
        subprocess.call(["git", "checkout", job["pipeline"]["ref"], "."])

        if "cwd" in job["pipeline"]:
            os.chdir(job["pipeline"]["cwd"])

        # Print exact revision getting built
        try:
            ref = subprocess.check_output(["git", "show-ref"])
            logging.info(f"git show-ref: {ref.decode()}")
        except:
            logging.warning("Could not call git show-ref")
            logger(job["otel"]["root-span-id"], "WARN", "Could not call git show-ref")

        # Execute job, will create sub spans - pass on trace and root span
        try:
            # Assume job accepts certain arguments
            command = list(job["pipeline"]["exec"]) + [
                "--service-name",
                job["otel"]["service-name"],
                "--trace-id",
                job["otel"]["trace-id"],
                "--root-span-id",
                job["otel"]["root-span-id"],
                "--traces-endpoint",
                job["otel"]["traces-endpoint"],
                "--logs-endpoint",
                job["otel"]["logs-endpoint"],
            ]

            logging.info("Executing command: %s", command)
            result = subprocess.run(command, env={**os.environ, **job["env"], **{"PYTHONPATH":os.environ.get("PYTHONPATH", "")}}, capture_output=True)

            # Get response and log it!
            if len(result.stderr) > 0:
                logger(job["otel"]["root-span-id"], "ERROR", result.stderr.decode())

            if len(result.stdout) > 0:
                logger(job["otel"]["root-span-id"], "INFO", result.stdout.decode())

            if result.returncode == ExecStatus.OK.value:
                logging.info("Build finished successfully")
                logger(job["otel"]["root-span-id"], "INFO", "Build finished successfully")
                status = ExecStatus.OK
            else:
                logging.error(f"Build finished with error code: {result.returncode}")
                logger(job["otel"]["root-span-id"], "INFO", f"Build finished with error code: {result.returncode}")
                status = ExecStatus.ERROR
        except Exception as e:
            logging.error("Failure during build step")
            logging.exception(e)
            status = ExecStatus.ERROR

    except Exception as e:
        logging.error("Exception: ", e)
        status = ExecStatus.ERROR

    return status

    # shutil.rmtree(tmpdir)

    # Checkout appropriate revision
    # Setup environment
    # Execute pipeline script


def check_for_job(args):
    (status, body) = bass.request("POST", args.dequeue_endpoint, None, headers={"X-API-KEY": args.dequeue_api_key})

    if status == 200:
        return json.loads(body)
    
    if status == 204:
        logging.debug("No job")
    
    if status >= 400:
        logging.error(f"Error checking for job (server error: {status})")

    if status == 0:
        logging.error("Error checking for job (network error?)")

    return None


def main(args):
    logging.info(f"Dequeue endpoint: {args.dequeue_endpoint}")
    logging.info(f"Workspace root: {args.workspace_root}")

    # Check for new job from orch
    while True:
        try:
            job = check_for_job(args)
            if not job:
                time.sleep(1)
                continue

            time_start = bass.utcnow()
            status = process(job, args)
            time_finished = bass.utcnow()

            otel_status = exec_status_to_otel[status.value]

            # Update root span
            updated_root_span = bass.generate_span(job["otel"]["trace-id"], None, job["otel"]["root-span-id"], job["otel"]["service-name"], f"Build: {job["name"]} - {status.name}", time_start, time_finished, otel_status)
            (code, msg) = bass.request("POST", job["otel"]["traces-endpoint"], updated_root_span, {"Content-Type": "application/json"})
            if code != 200:
                logging.error(f"Could not post root span: {code}, {msg}")

        except Exception as e:
            logging.exception("Exception: %s", e)
            time.sleep(1)


def worker_argparse():
    parser = argparse.ArgumentParser(
            prog = "bass worker",
            description = None,
            epilog = None,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    
    parser.add_argument("-d", "--dequeue-endpoint", type=str, action="store", default="http://localhost:8080/dequeue", help="URL to bass orchestrator dequeue endpoint")
    # TODO: Move to env
    parser.add_argument("-s", "--dequeue-api-key", type=str, action="store", default="", help="API-key to authenticate worker towards orchestrator")
    # parser.add_argument("-t", "--tags", type=str, action="store", default="", help="Comma-separated list of tags identifying this worker")
    parser.add_argument("-w", "--workspace-root", type=str, action="store", default=tempfile.gettempdir(), help="Root folder under which data required for pipeline processing will be stored")
    # --clean ? To nuke any temp-pipelines
    
    return parser.parse_args()

if __name__ == "__main__":
    args = worker_argparse()
    main(args)

    