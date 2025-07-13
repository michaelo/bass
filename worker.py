#!/usr/bin/env python3
import json
import logging
import time
import tempfile
import os
import subprocess
import argparse
import bass

logging.getLogger().setLevel(logging.DEBUG)

def process(job: dict, args):
    logging.info("Processing: %s", job["name"])

    # TODO: chdir back to origin cwd?

    # tmpdir = tempfile.mkdtemp(prefix="pipeline_", dir=args.workspace_root)
    tmpdir = f"{args.workspace_root}/pipeline_{job["name"]}"
    try:
        os.mkdir(tmpdir)
    except FileExistsError:
        pass

    try:
        # Setup temporary workspace dir

        # TBD: shall this create top level span, or leave that to orchestrator?
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

        # Print exact revision getting built
        try:
            ref = subprocess.check_output(["git", "show-ref"])
            logging.info(f"git show-ref: {ref.decode()}")
        except:
            logging.warning("Could not call git show-ref")

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
            return_code = subprocess.call(command, env={**os.environ, **job["env"], **{"PYTHONPATH":"/Users/michael/dev/bass"}})

            if return_code == 0:
                logging.info("Build finished successfully")
            else:
                logging.error(f"Build finished with error code: {return_code}")
        except Exception as e:
            logging.error("Failure during build step")
            logging.exception(e)

    except Exception as e:
        logging.error("Exception: ", e)
        pass

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

            process(job, args)
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
    parser.add_argument("-s", "--dequeue-api-key", type=str, action="store", default="", help="API-key to authenticate worker towards orchestrator")
    # parser.add_argument("-t", "--tags", type=str, action="store", default="", help="Comma-separated list of tags identifying this worker")
    parser.add_argument("-w", "--workspace-root", type=str, action="store", default=tempfile.gettempdir(), help="Root folder under which data required for pipeline processing will be stored")
    # --clean ? To nuke any temp-pipelines
    
    return parser.parse_args()

if __name__ == "__main__":
    args = worker_argparse()
    main(args)

    