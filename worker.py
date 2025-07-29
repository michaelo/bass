#!/usr/bin/env python3
import json
import logging
import time
import tempfile
import os
import subprocess
import argparse
from string import Template
import bass
from bass import create_log_sender, notification
from bass.core import ExecStatus, exec_status_to_otel

logging.getLogger().setLevel(logging.INFO)

def handle_notifications(notifications_config: dict, job_status: ExecStatus, variables: dict = {}):
    notification_type = "onSuccess" if job_status == ExecStatus.OK else "onFailure"
    if notification_type in notifications_config:
        if "email" in notifications_config[notification_type]:
            print("got email config")
            email = notifications_config[notification_type]["email"]
            assert "to" in email
            assert "subject" in email
            assert "body" in email
            
            notification.send_email("bass@local", email["to"], Template(email["subject"]).safe_substitute(variables), Template(email["body"]).safe_substitute(variables))
        


def process(job: dict, args) -> ExecStatus:
    logger = create_log_sender(job["otel"]["logs-endpoint"], job["otel"]["service-name"], job["otel"]["trace-id"])
    logging.info("Processing: %s", job["name"])
    status = ExecStatus.UNKNOWN

    # Create workspace specific for the pipeline, ignore if already exists
    # Ensure local clone/workspace represents both pipeline and repository
    repository_escaped = job["pipeline"]["repository"].replace("\\", "-").replace("/", "-")
    tmpdir = f"{args.workspace_root}/pipeline/{job["name"]}/{repository_escaped}"
    tmpfile_changeset = None
    logging.info("Workspace: %s", tmpdir)
    try:
        os.makedirs(tmpdir)
    except FileExistsError:
        pass

    try:
        # TODO: Span for initial steps?
        os.chdir(tmpdir)

        if os.path.exists(f"{tmpdir}/.git"):
            logging.info("Updating repository '%s' in: '%s'", job["pipeline"]["repository"], tmpdir)
            subprocess.call(["git", "clean", "-xdf"])
            subprocess.call(["git", "pull"])
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


            # Get changes - resolve from list of git revisions to list of files
            changed_files = set()
            if "changed-refs" in job and len(job["changed-refs"])>0:
                for changed_ref in job["changed-refs"]:
                    result = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", changed_ref]).decode("utf-8")
                    changed_files = changed_files.union(set(result.splitlines()))
                    # TODO: append directly to file?

            # For very large sets of files we might hit OS-limits for exec arguments. We therefore write them to a temporary file and pass this to the build command
            if len(changed_files) > 0:
                tmpfile_changeset = tempfile.mktemp(prefix=f"bass-{job['name']}-changeset")
                with open(tmpfile_changeset, "w") as f:
                    f.writelines([x + "\n" for x in changed_files])

                command += ["--changeset", tmpfile_changeset]

            logging.info("Executing command: %s", command)
            result = subprocess.run(command, env={**os.environ, **job["env"], **{"PYTHONPATH":os.environ.get("PYTHONPATH", "")}}, capture_output=True)

            # Get response and log it!

            if result.returncode == ExecStatus.OK.value:
                logging.info("Build finished successfully")

                if len(result.stderr) > 0:
                    logger(job["otel"]["root-span-id"], "INFO", result.stderr.decode())

                if len(result.stdout) > 0:
                    logger(job["otel"]["root-span-id"], "INFO", result.stdout.decode())

                logger(job["otel"]["root-span-id"], "INFO", "Build finished successfully")
                status = ExecStatus.OK
            else:
                logging.error(f"Build finished with error code: {result.returncode}")

                if len(result.stderr) > 0:
                    logger(job["otel"]["root-span-id"], "ERROR", result.stderr.decode())

                if len(result.stdout) > 0:
                    logger(job["otel"]["root-span-id"], "ERROR", result.stdout.decode())

                logger(job["otel"]["root-span-id"], "ERROR", f"Build finished with error code: {result.returncode}")
                status = ExecStatus.ERROR

            # Notifications
            if "notifications" in job["pipeline"]:
                # TODO: establish all variables that shall be supported
                notification_variables = {
                    "PIPELINE_NAME": job["name"],
                    "TRACEID": job["otel"]["trace-id"]
                }
                handle_notifications(job["pipeline"]["notifications"], status, notification_variables)
            
        except Exception as e:
            logging.error("Failure during build step")
            logging.exception(e)
            logger(job["otel"]["root-span-id"], "ERROR", f"Failure during build step: {str(e)}")
            status = ExecStatus.ERROR

    except Exception as e:
        logging.error("Exception: ", e)
        status = ExecStatus.ERROR

    # Cleaning up
    if tmpfile_changeset:
        os.remove(tmpfile_changeset)

    return status


def check_for_job(args, api_key):
    (status, body) = bass.request("POST", args.dequeue_endpoint, None, headers={"X-API-KEY": api_key})

    if status == 200:
        return json.loads(body)
    
    if status == 204:
        logging.debug("No job")
    
    if status >= 400:
        logging.error(f"Error checking for job (server error: {status})")

    if status == 0:
        logging.error("Error checking for job (network error?)")

    return None


def main(args, api_key):
    logging.info(f"Dequeue endpoint: {args.dequeue_endpoint}")
    logging.info(f"Workspace root: {args.workspace_root}")

    # Check for new job from orch
    while True:
        try:
            job = check_for_job(args, api_key)
            if not job:
                time.sleep(1)
                continue

            time_start = bass.utcnow()
            status = process(job, args)
            time_finished = bass.utcnow()

            otel_status = exec_status_to_otel[status.value]

            # Finally send root span
            root_span = bass.generate_span(job["otel"]["trace-id"], None, job["otel"]["root-span-id"], job["otel"]["service-name"], f"Build: {job["name"]} - {status.name}", time_start, time_finished, otel_status)
            (code, msg) = bass.request("POST", job["otel"]["traces-endpoint"], root_span, {"Content-Type": "application/json"})
            if code != 200:
                logging.error(f"Could not post root span: {code}, {msg}")

        except Exception as e:
            logging.exception("Exception: %s", e)
            time.sleep(1)


def worker_argparse():
    parser = argparse.ArgumentParser(
            prog = "bass worker",
            description = "Att! Requires env BASS_API_KEY with valid orchestrator api key to retrieve jobs",
            epilog = None,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    
    parser.add_argument("-d", "--dequeue-endpoint", type=str, action="store", default="http://localhost:8080/dequeue", help="URL to bass orchestrator dequeue endpoint")
    # parser.add_argument("-t", "--tags", type=str, action="store", default="", help="Comma-separated list of tags identifying this worker")
    parser.add_argument("-w", "--workspace-root", type=str, action="store", default=tempfile.gettempdir(), help="Root folder under which data required for pipeline processing will be stored")
    # --clean ? To nuke any temp-pipelines
    
    return parser.parse_args()

if __name__ == "__main__":
    args = worker_argparse()
    api_key = os.environ.get("BASS_API_KEY")
    if not api_key:
        print("Could not find valid api key as environment variable 'BASS_API_KEY'")
        exit(1)
    main(args, api_key)

    