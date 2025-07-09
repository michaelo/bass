import bass
import json
import logging
import time
import tempfile
import os
import subprocess
import shutil

logging.getLogger().setLevel(logging.DEBUG)

def process(job: dict):
    logging.info("processing: %s", job)

    tmpdir = tempfile.mkdtemp()

    try:
        # Setup temporary workspace dir
        
        # TBD: shall this create top level span, or leave that to orchestrator?
        # TODO: Span for initial steps
        os.chdir(tmpdir)
        logging.info("Cloning repository '%s' to: '%s'", job["pipeline"]["repository"], tmpdir)
        subprocess.call(["git", "clone", job["pipeline"]["repository"], "."])

        # Execute job, will create sub spans
    except Exception as e:
        pass

    shutil.rmtree(tmpdir)

    # clone repo (tbd: cache repo based on some pipeline/job-id?)
    # Checkout appropriate revision
    # Setup environment
    # Execute pipeline script

def check_for_job(url, secret):
    (status, body) = bass.request("POST", url, None, headers={"X-API-KEY": secret})

    if status == 200:
        return json.loads(body)
    
    if status == 204:
        logging.debug("No job")
    
    if status >= 400:
        logging.error("Error checking for job")

    return None

def main(url, secret):
    # Check for new job from orch
    while True:
        try:
            job = check_for_job(url, secret)
            print(job)
            if job:
                process(job)
        except Exception as e:
            logging.exception("Exception: %s", e)

        time.sleep(1)


if __name__ == "__main__":
    orch_url = "http://localhost:8080/dequeue"
    agent_secret = "supersecret"
    main(orch_url, agent_secret)

    