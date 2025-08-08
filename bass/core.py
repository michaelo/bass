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
class ExecStatus(Enum):
    OK = 0 # Intentionally to play nice as exit code
    UNKNOWN = 1
    TIMEOUT = 2
    ERROR = 3
    # SKIPPED ?

exec_status_to_otel = {
    0: 1, # OK
    1: 0, # unknown
    2: 2, # ERRPR
    3: 2 # ERROR
}

class IoContext:
    """Provides a convenient way to override realization of basic system/IO operations"""
    def run(self, cmd: list[str], timeout: int) -> tuple[int, str, str]:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return (result.returncode, result.stdout.decode(), result.stderr.decode())
    
    def chdir(self, dir:str):
        return os.chdir(dir)

    def getcwd(self) -> str:
        return os.getcwd()

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

def create_span_sender(traces_endpoint: str, service_name: str, trace_id: str) -> Callable[[str, str, str, datetime.datetime, datetime.datetime, int], None]:
    def span_sender(name: str, parent_span_id: None|str, span_id: str, time_from:datetime.datetime, time_to:datetime.datetime, status: int):
        span = generate_span(trace_id, parent_span_id, span_id, service_name, name, time_from, time_to, status)
        (status, body) = request("POST", traces_endpoint, span, headers={"Content-Type": "application/json"})
        if status != 200:
            logging.error(f"Could not post span. Reason: {body}")

    return span_sender

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

def create_log_sender(logs_endpoint: str, service_name: str, trace_id: str) -> Callable[[str, Severity, str], None]:
    def log_sender(span_id: str, severity: Severity, message: str):
        logging.debug(message)
        log = generate_log(trace_id, span_id, service_name, severity, message)
        (status, body) = request("POST", logs_endpoint, log, headers={"Content-Type": "application/json"})
        if status != 200:
            logging.error(f"Could not post log. Reason: {body}")

    return log_sender

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

def datetime_to_nano(time: datetime.datetime):
    return int(time.timestamp() * 1000000000)

def generate_hex_string(bytes: int):
    return os.urandom(bytes).hex()

def test_generate_hex_string():
    exp = re.compile("^[0-9a-fA-F]+$")
    hexstring = generate_hex_string(128)
    assert exp.match(hexstring)
    assert len(hexstring) == 256

def generate_trace_id():
    return generate_hex_string(16)

def test_generate_trace_id():
    assert len(generate_trace_id()) == 32

def generate_span_id():
    return generate_hex_string(8)

def test_generate_span_id():
    assert len(generate_span_id()) == 16

def any_item_matches(items: list[str], match_criteria: None|str, default=True):
    # No items is all changes
    if not items or len(items) == 0:
        return default

    # No criteria is all criteria
    if not match_criteria:
        return default
    
    # If items provided, and "if-changes-match"-filter set: verify if any of them matches
    exp = re.compile(match_criteria)
    
    for change in items:
        if exp.search(change) != None:
            return True
        
    return False

def test_any_item_matches():
    assert any_item_matches([], None)
    assert any_item_matches(["some/path"], None)
    assert any_item_matches(["some/path", "another/path"], "^another")
    assert not any_item_matches(["some/path"], "^another")

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
    # parser.add_argument("-f", "--force", action="store_true", default=False, help="Will force build all steps")
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

def exec_step(io: IoContext, step) -> tuple[ExecStatus, str, str]:
    """Returns tuple of (status, stdout, stderr)"""
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
        
        # Resolve variables in cmd and execute
        cmd_expanded = [os.path.expandvars(v) for v in cmd]
        (returncode, stdout, stderr) = io.run(cmd_expanded, timeout=timeout)
        return (ExecStatus.OK if returncode == 0 else ExecStatus.ERROR, stdout, stderr)
    except subprocess.TimeoutExpired as e:
        return (ExecStatus.TIMEOUT, e.output, str(e))


def build_inner(io: IoContext, args, node, parent_span_id, changeset) -> ExecStatus:
    # Check node: if exec: execute directly. If steps: recurse.
    time_step_start = utcnow()
    span_id = generate_span_id()
    aggregated_result = ExecStatus.OK
    
    spanner = create_span_sender(args.traces_endpoint, args.service_name, args.trace_id)
    logger = create_log_sender(args.logs_endpoint, args.service_name, args.trace_id)

    skip_remaining_steps = False

    if not any_item_matches(changeset, node.get("if-changeset-matches", None)):
        spanner(f"step:{node['name']} - skipped", parent_span_id, span_id, utcnow(), utcnow(), 0)
        return ExecStatus.OK

    initial_cwd = io.getcwd()
    if "cwd" in node:
        # TODO: ensure we don't navigate out of repo/workspace?
        io.chdir(f"{initial_cwd}/{node["cwd"]}")
        logging.info(f"Changing chdir to: {os.getcwd()}")

    if "setup" in node:
        step_result = build_inner(io, args, node["setup"], span_id, changeset)
        if step_result != ExecStatus.OK:
            skip_remaining_steps = True

        if step_result.value > aggregated_result.value:
            aggregated_result = step_result

    if not skip_remaining_steps:
        if "exec" in node:
            try:
                (step_result, step_stdout, step_stderr) = exec_step(io, node)
            except Exception as e:
                (step_result, step_stdout, step_stderr) = (ExecStatus.ERROR, "", str(e))

            if step_result.value > aggregated_result.value:
                aggregated_result = step_result

            if len(step_stderr) > 0:
                logger(span_id, "ERROR", step_stderr)

            if len(step_stdout) > 0:
                logger(span_id, "INFO", step_stdout)
        elif "steps" in node:
            if "order" in node and node["order"] == "unordered":
                # TODO: Make num workers configurable
                # TODO: Make threadpool respect timeout?
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = []    
                    for step in node["steps"]:
                        futures.append(executor.submit(build_inner, io, args, step, span_id, changeset))

                    for f in futures:
                        step_result = f.result()
                        if step_result.value > aggregated_result.value:
                            aggregated_result = step_result
            else:
                for i, step in enumerate(node["steps"]):
                    if not skip_remaining_steps:
                        step_result = build_inner(io, args, step, span_id, changeset)
                        if step_result.value > aggregated_result.value:
                            aggregated_result = step_result
                        
                        if aggregated_result != ExecStatus.OK:
                            skip_remaining_steps = True
                    else:
                        spanner(f"step:{step['name']} - skipped", span_id, generate_span_id(), utcnow(), utcnow(), 0)



    if "teardown" in node:
        build_inner(io, args, node["teardown"], span_id, changeset)

    time_step_end = utcnow()

    io.chdir(initial_cwd)

    spanner(f"step:{node['name']}", parent_span_id, span_id, time_step_start, time_step_end, exec_status_to_otel[aggregated_result.value])

    return aggregated_result

def build(pipeline):
    args = job_argparse(pipeline["name"])
    logging.info(args)

    changeset = []
    if args.changeset:
        with open(args.changeset, "r") as f:
            changeset + [x.strip() for x in f.readlines()]

    spanner = create_span_sender(args.traces_endpoint, args.service_name, args.trace_id)
    # logger = create_log_sender(args.logs_endpoint, args.service_name, args.trace_id)
    root_span_id = args.root_span_id

    root_start = utcnow()
    exit_code = build_inner(IoContext(), args, pipeline, root_span_id, changeset)
    root_end = utcnow()
    
    if args.generate_root_span:
        spanner(f"pipeline:{pipeline['name']}", None, root_span_id, root_start, root_end, exec_status_to_otel[exit_code.value])
    
    logging.info(f"Execution concluded with status: {exit_code} / {exit_code.value}")
    exit(exit_code.value)

class TestIoContext(IoContext):
    """Simple IO context realization which logs every usage, and provides a way to inject predefined results for command executions"""
    __test__ = False

    predefs = {}
    run_history: list[tuple[list[str], int]] = []
    chdir_history: list[str] = []
    cwd = ""

    def __init__(self, predefs: dict = {}):
        self.run_history = []
        self.chdir_history = []
        self.cwd = ""
        if predefs:
            self.predefs = predefs

    def run(self, cmd: list[str], timeout: int):
        self.run_history.append((cmd, timeout))
        result = self.predefs.get((tuple(cmd), timeout), (0, "", ""))
        return result


    def chdir(self, dir:str):
        self.chdir_history.append(dir)
        self.cwd = dir

    def getcwd(self) -> str:
        return self.cwd


def dummy_argparse():
    """Provides a Namespace-object similar to job_argparse() - to use for testing"""
    return argparse.Namespace(traces_endpoint="http://localhost:4318/v1/traces", logs_endpoint="http://localhost:4318/v1/traces", service_name="test", trace_id="")

def test_pipeline_with_no_commands_executes_nothing():
    ctx = TestIoContext()
    build_inner(ctx, dummy_argparse(), {"name": "root"}, "", [])
    assert len(ctx.run_history) == 0

def test_pipeline_with_command_executes_it():
    ctx = TestIoContext()
    build_inner(ctx, dummy_argparse(), {"name": "root", "exec": "myscript.sh"}, "", [])
    assert len(ctx.run_history) == 1
    assert ctx.run_history[0] == (["myscript.sh"], None)

def test_pipeline_with_cwd_shall_change_to_dir():
    ctx = TestIoContext()
    build_inner(ctx, dummy_argparse(), {"name": "root", "cwd": "somedir"}, "", [])
    assert len(ctx.chdir_history) == 2
    assert ctx.chdir_history[0] == "/somedir"

def test_pipeline_with_changeset_and_filter_shall_skip_step_unless_matched():
    ctx = TestIoContext()
    pipeline = {"name": "root", "if-changeset-matches": "^somedir", "exec": "myscript.sh"}
    build_inner(ctx, dummy_argparse(), pipeline, "", ["somedir/somefile"])
    assert len(ctx.run_history) == 1
    build_inner(ctx, dummy_argparse(), pipeline, "", ["someotherdir/somefile"])
    assert len(ctx.run_history) == 1

def test_pipeline_ordered_pipeline_steps_shall_skip_remaining_steps_after_first_error():
    ctx = TestIoContext(
        {
            (("fail.sh",), None): (1, "", ""),
        })
    pipeline = {
        "name": "root",
        "steps": [
            {"name": "step1", "exec": "success.sh"},
            {"name": "step2", "exec": "fail.sh"},
            {"name": "step3", "exec": "never-executed.sh"},
        ]}
    build_inner(ctx, dummy_argparse(), pipeline, "", [])
    assert len(ctx.run_history) == 2
    assert ctx.run_history == [(["success.sh"], None), (["fail.sh"], None)]

def test_pipeline_if_setup_fails_run_no_steps():
    ctx = TestIoContext({
        (("fail.sh",), None): (1, "", ""),
    })
    pipeline = {
        "name": "root",
        "setup": {"name": "setup", "exec": "fail.sh"},
        "steps": [
            {"name": "step1", "exec": "never-executed.sh"},
        ]}
    build_inner(ctx, dummy_argparse(), pipeline, "", [])
    assert len(ctx.run_history) == 1
    assert ctx.run_history == [(["fail.sh"], None)]

def test_pipeline_if_setup_fails_run_no_exec():
    ctx = TestIoContext({
        (("fail.sh",), None): (1, "", ""),
    })
    pipeline = {
        "name": "root",
        "setup": {"name": "setup", "exec": "fail.sh"},
        "exec": "never-executed.sh"
    }
    build_inner(ctx, dummy_argparse(), pipeline, "", [])
    assert len(ctx.run_history) == 1
    assert ctx.run_history == [(["fail.sh"], None)]