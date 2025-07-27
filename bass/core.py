from enum import Enum
from urllib import request as urq, error
from typing import Literal, Callable
import json
import os
import datetime
import argparse
import logging
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

type Severity = Literal["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
# otel span status: 0: undefined, 1: ok, 2: error

def generate_span(trace_id: str, parent_span_id: None|str, span_id: str, service: str, name: str, time_from: datetime.datetime, time_to: datetime.datetime, status: int):
    return {
        "resourceSpans": [
            {
                "resource": {
                "attributes": [
                    {
                        "key": "service.name",
                        "value": {
                            "stringValue": service
                        }
                    }
                ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": trace_id,
                                "spanId": span_id,
                                "parentSpanId": parent_span_id,
                                "startTimeUnixNano": datetime_to_nano(time_from),
                                "endTimeUnixNano": datetime_to_nano(time_to),
                                "name": name,
                                "kind": 2,
                                "status": {
                                    "code": status
                                }
                            },
                        ]
                    }
                ]
            }
        ]
    }

def generate_log(trace_id: str, span_id: str, service: str, severity: Severity, message: str):
    sevMap = {
        "TRACE": 1,
        "DEBUG": 5,
        "INFO": 9,
        "WARN": 13,
        "ERROR": 17,
        "FATAL": 21
    }

    return {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "service.name",
                            "value": {
                                "stringValue": service
                            }
                        }
                    ]
                },
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "timeUnixNano": datetime_to_nano(utcnow()),
                                "observedTimeUnixNano": datetime_to_nano(utcnow()),
                                "severityNumber": sevMap[severity],
                                # "severityText": "Information",
                                "traceId": trace_id,
                                "spanId": span_id,
                                "body": {
                                    "stringValue": message
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }

def request(method: Literal["GET", "POST", "PUT", "DELETE"], url, payload=None, headers={}) -> tuple[int, str|None]:
    req = urq.Request(url)
    req.method = method
    if payload:
        req.data = json.dumps(payload).encode("utf-8")

    for k,v in headers.items():
        req.add_header(k, v)

    try:
        with urq.urlopen(req) as response:
            return (response.status, response.read().decode("utf-8"))
    except error.HTTPError as e:
        return (e.code, e.read().decode("utf-8"))
    except error.URLError  as e:
        return (0, e.reason)

def utcnow() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)

def now_nano() -> int:
    """Returns current UNIX timestamp in nanoseconds"""
    return int((utcnow() - datetime.timedelta(seconds=5)).timestamp() * 1000000000)

def datetime_to_nano(time: datetime.datetime):
    return int(time.timestamp() * 1000000000)

def generate_hex_string(bytes: int):
    return os.urandom(bytes).hex()

def generate_trace_id():
    return generate_hex_string(16)

def generate_span_id():
    return generate_hex_string(8)

# Execute lambda and wrap result as span
def execute_span(span_sender: callable, span_name: str, func: callable):
    pass

def check_if_changeset_matches(changeset: list[str], match_criteria: None|str):
    # No changeset is all changes
    if not changeset or len(changeset) == 0:
        return True

    # No criteria is all criteria
    if not match_criteria:
        return True
    
    # If changeset provided, and "if-changes-match"-filter set: verify if any of them matches
    exp = re.compile(match_criteria)
    
    for change in changeset:
        if exp.search(change) != None:
            return True
        
    return False

def test_check_if_changeset_matches():
    assert check_if_changeset_matches([], None)
    assert check_if_changeset_matches(["some/path"], None)
    assert check_if_changeset_matches(["some/path", "another/path"], "^another")
    assert not check_if_changeset_matches(["some/path"], "^another")


def process_step(buildCtx, step):
    # take time
    # execute step, store log and status code
    # take time
    # generate and send span and log entry
    pass


def job_argparse(pipeline_name:str):
    parser = argparse.ArgumentParser(
                    prog = pipeline_name,
                    description = None,
                    epilog = None)
    
    parser.add_argument("-s", "--service-name", type=str, action="store", default=f"bass:pipeline:{pipeline_name}", help="Name to use for otel trace")
    parser.add_argument("-i", "--trace-id", type=str, action="store", default=generate_trace_id(), help="")
    parser.add_argument("-d", "--root-span-id", type=str, action="store", default=generate_span_id(), help="")
    parser.add_argument("-g", "--generate-root-span", action="store_true", default=False, help="")
    parser.add_argument("-t", "--traces-endpoint", type=str, action="store", default="http://localhost:4318/v1/traces", help="")
    parser.add_argument("-l", "--logs-endpoint", type=str, action="store", default="http://localhost:4318/v1/logs", help="")
    parser.add_argument("-f", "--force", action="store_true", default=False, help="Will force build all steps")
    parser.add_argument("-c", "--changeset", type=str, action="store", default=None, help="Path to file with list of modified files, allows steps to be conditionally executed")
    
    return parser.parse_args()


def assert_pipeline(node) -> bool:
    """Asserts that a pipeline is properly setup"""
    # Perform necessary ducktyping on pipeline-object to verify it's structure
    assert "name" in node and type(node["name"]) == str
    assert "steps" in node or "exec" in node
    assert not ("steps" in node and "exec" in node)

    if "if-changeset-matches" in node:
        assert re.compile(node["if-changeset-matches"])    

    if "exec" in node:
        assert type(node["exec"]) == list or type(node["exec"]) == str

    if "steps" in node:
        assert type(node["steps"]) == list
        assert len(node["steps"]) > 0

        for step in node["steps"]:
            assert_pipeline(step)

            # assert callable(step["exec"]) or type(step["exec"]) == list or type(step["exec"]) == str

def create_span_sender(traces_endpoint: str, service_name: str, trace_id: str) -> Callable[[str, str, str, datetime.datetime, datetime.datetime, int], None]:
    def span_sender(name: str, parent_span_id: None|str, span_id: str, time_from:datetime.datetime, time_to:datetime.datetime, status: int):
        span = generate_span(trace_id, parent_span_id, span_id, service_name, name, time_from, time_to, status)
        (status, body) = request("POST", traces_endpoint, span, headers={"Content-Type": "application/json"})
        if status != 200:
            logging.error(f"Could not post span. Reason: {body}")

    return span_sender

def create_log_sender(logs_endpoint: str, service_name: str, trace_id: str) -> Callable[[str, Severity, str], None]:
    def log_sender(span_id: str, severity: Severity, message: str):
        logging.debug(message)
        log = generate_log(trace_id, span_id, service_name, severity, message)
        (status, body) = request("POST", logs_endpoint, log, headers={"Content-Type": "application/json"})
        if status != 200:
            logging.error(f"Could not post log. Reason: {body}")

    return log_sender

class ExecStatus(Enum):
    OK = 0
    UNKNOWN = 1
    TIMEOUT = 2
    ERROR = 3

exec_status_to_otel = {
    0: 1, # OK
    1: 0, # unknown
    2: 2, # ERRPR
    3: 2 # ERROR
}


def exec_step(step, changeset) -> tuple[ExecStatus, str, str]:
    """Returns tuple of (status, stdout, stderr). Status: result code"""
    if not check_if_changeset_matches(changeset, step.get("if-changeset-matches", None)):
        return (ExecStatus.OK, f"Skpping step: {step["name"]}", "")
    else:
        timeout = step["timeout"] if "timeout" in step else None
        try:
            cmd = None
            if type(step["exec"]) == str:
                cmd = [step["exec"]]

            if type(step["exec"]) == list:
                cmd = step["exec"]
            
            if not cmd:
                logging.error(f"Unknown command type: {type(exec["step"])}")
                return (ExecStatus.UNKNOWN, "", f"Unknown command type: {type(exec["step"])}")
            
            result = subprocess.run(cmd, capture_output=True, timeout=timeout)
            return (ExecStatus.OK if result.returncode == 0 else ExecStatus.ERROR, result.stdout.decode(), result.stderr.decode())
        except subprocess.TimeoutExpired as e:
            return (ExecStatus.TIMEOUT, e.output, str(e))


def build_inner(args, node, parent_span_id, changeset) -> ExecStatus:
    # Check node: if exec: execute directly. If steps: recurse.
        # Always establish span for sub-nodes
    # Errors need to propagate
    step_start = utcnow()
    span_id = generate_span_id()
    result = ExecStatus.OK
    
    spanner = create_span_sender(args.traces_endpoint, args.service_name, args.trace_id)
    logger = create_log_sender(args.logs_endpoint, args.service_name, args.trace_id)
    
    if "exec" in node:
        try:
            (step_status, step_stdout, step_stderr) = exec_step(node, changeset)
        except Exception as e:
            (step_status, step_stdout, step_stderr) = (ExecStatus.ERROR, "", str(e))

        if step_status.value > result.value:
            result = step_status

        if len(step_stderr) > 0:
            logger(span_id, "ERROR", step_stderr)

        if len(step_stdout) > 0:
            logger(span_id, "INFO", step_stdout)
    elif "steps" in node:
        if "order" in node and node["order"] == "unordered":
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []    
                for step in node["steps"]:
                    futures.append(executor.submit(build_inner, args, step, span_id, changeset))

                for f in futures:
                    step_result = f.result()
                    if step_result.value > result.value:
                        result = step_result
        else:
            for step in node["steps"]:
                step_result = build_inner(args, step, span_id, changeset)
                if step_result.value > result.value:
                    result = step_result

    step_end = utcnow()

    # Send span
    spanner(f"step:{node['name']}", parent_span_id, span_id, step_start, step_end, 1 if result == ExecStatus.OK else 2)

    return result

def build(pipeline):
    args = job_argparse(pipeline["name"])
    print(args)

    changeset = []
    if args.changeset:
        with open(args.changeset, "r") as f:
            changeset + [x.strip() for x in f.readlines()]


    spanner = create_span_sender(args.traces_endpoint, args.service_name, args.trace_id)
    # logger = create_log_sender(args.logs_endpoint, args.service_name, args.trace_id)
    root_span_id = args.root_span_id

    root_start = utcnow()
    exit_code = build_inner(args, pipeline, root_span_id, changeset)
    root_end = utcnow()
    
    if args.generate_root_span:
        spanner(f"pipeline:{pipeline['name']}", None, root_span_id, root_start, root_end, 1 if exit_code == ExecStatus.OK else 2)
    
    logging.info(f"Execution concluded with status: {exit_code} / {exit_code.value}")
    exit(exit_code.value)
