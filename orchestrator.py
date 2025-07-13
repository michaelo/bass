#!/usr/bin/env python3
import logging
import http.server as server
import json
import os
import argparse
import bass

logging.getLogger().setLevel(logging.DEBUG)

# The list of acceptable jobs for the orchestrator etc
config = {
    "pipelines": {},
    "env": {},
    "api-keys": {},
    "otel": {
        "traces-endpoint": "http://localhost:4318/v1/traces",
        "logs-endpoint": "http://localhost:4318/v1/logs"
    }
}

# The job queue to be processed
job_queue = []

# Called periodically to check all registered jobs who require pull-checks
# Att! Requires local state. Can be in-memory to begin with, but would need persistence at some point
def checkForPullChanges():
    # eventually scheduleJob(...)
    pass

# Result of either onIncomingJob or checkForPullChanges to schedule a job to be done
def scheduleJob(job: dict):
    job_queue.append(job)

def parse_path(path_raw: str) -> tuple[str, dict[str:str]]:
    """Tremendously naive path-of-URL-parser. Does e.g. not support multiple params with same key. URL-encoding? Schmurlencoding!"""
    splits = path_raw.split("?", 1)
    base = ""
    query = None
    params = {}

    if len(splits) == 1:
        base = splits[0]
    else:
        (base, query) = splits

    if query != None:
        for raw_param in query.split("&"):
            if "=" in raw_param:
                (k, v) = raw_param.split("=", 1)
            else:
                (k, v) = raw_param, True

            params[k] = v

    return (base, params)

    
def test_parse_path():
    assert ("path", {}) == parse_path("path")
    assert ("path", {"key": True}) == parse_path("path?key")
    assert ("path", {"key": "val"}) == parse_path("path?key=val")
    assert ("path", {"key": "val", "some": "else"}) == parse_path("path?key=val&some=else")

class HTTPRequestHandler(server.SimpleHTTPRequestHandler):
    def do_GET(self):
        logging.info("got GET")

    def do_PUT(self):
        logging.info("got PUT")

    def do_POST_webhook(self, params: dict) -> None:
        # Parameter checks
        if "pipeline" not in params:
            self.send_error(400, "Invalid request")
            return

        if params["pipeline"] not in config["pipelines"]:
            self.send_error(404, "No such job")
            return

        # Get it done!
        # TODO: send trace id and root span id
        # Create a preliminary root span which the worker will eventually update?
        trace_id = bass.generate_trace_id()
        root_span_id = bass.generate_span_id()
        service_name = f"bass:pipeline:{params['pipeline']}"

        root_span = bass.generate_span(trace_id, root_span_id, bass.generate_span_id(), service_name, "onSchedule", bass.utcnow(), bass.utcnow(), 1)
        (code, msg) = bass.request("POST", config["otel"]["traces-endpoint"], root_span, {"Content-Type": "application/json"})
        if code != 200:
            logging.error(f"Could not post placeholder root span: {code}, {msg}")


        scheduleJob({
            "name": params["pipeline"],
            "schedule-time": bass.utcnow().isoformat(),
            "env": config["env"],
            "pipeline": config["pipelines"][params["pipeline"]],
            "otel": {**dict(config["otel"]), **{
                "service-name": service_name,
                "trace-id": trace_id,
                "root-span-id": root_span_id
            }}
        })

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"")

    def do_POST_dequeue(self, params: dict) -> None:
        # If auth
        if len(config["api-keys"].keys()) > 0:
            api_key = self.headers.get("X-API-KEY", None)
            if not api_key:
                self.send_error(401, "Unauthenticated")
                return
            
            if not config["api-keys"].get(api_key, False):
                self.send_error(403, "Unauthorized")
                return
            
        # Check for /webhook or /dequeue
        if len(job_queue) > 0:
            job = job_queue.pop(0)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(job).encode("utf-8"))
        else:
            self.send_response(204)
            self.end_headers()
            self.wfile.write(b"")


    def do_POST(self) -> None:
        """Save a file following a HTTP PUT request"""
        logging.info("got POST: %s", self.path)
        (path, params) = parse_path(self.path)

        if path == "/dequeue":
            return self.do_POST_dequeue(params)
        elif path == "/webhook":
            return self.do_POST_webhook(params)
        
def test_HTTPRequestHandler():
    pass

def orch_argparse():
    parser = argparse.ArgumentParser(
            prog = "bass orchestrator",
            description = None,
            epilog = None,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    
    parser.add_argument("-t", "--traces-endpoint", type=str, action="store", default="http://localhost:4318/v1/traces", help="")
    parser.add_argument("-l", "--logs-endpoint", type=str, action="store", default="http://localhost:4318/v1/logs", help="")
    # TBD: support pipeline-config from URL? And live reload/periodic sync?
    parser.add_argument("-f", "--pipelines-file", type=str, action="store", default="orchestrator-pipelines.json", help="Local path to pipeline configurations")
    parser.add_argument("-e", "--env-file", type=str, action="store", default="orchestrator.env", help="Local path to file containing variables definitions as key=value pairs. Supports $envvariable")
    # TBD: listening address?
    parser.add_argument("-p", "--port", type=int, action="store", default=8080, help="Port to listen for requests at")
    # TBD: specify from file? At least store only hashes in memory
    parser.add_argument("-a", "--api-keys", type=str, action="store", default="", help="Comma separated list of allowed API-keys")
    
    return parser.parse_args()


if __name__ == '__main__':
    args = orch_argparse()

    # Load configs
    with(open(args.pipelines_file, "r") as f):
        tmp_pipelines = json.load(f)
        config["pipelines"] = tmp_pipelines

    with(open(args.env_file, "r") as f):
        tmp_env_raw = { k: os.path.expandvars(v) for (k,v) in [l.split("=") for l in f.readlines()]}
        config["env"] = tmp_env_raw

    # TODO: store only hashes
    config["api-keys"] = {x: True for x in args.api_keys.split(",")}

    # Inform of loaded configs
    logging.info("Loaded pipelines:")
    for x in config["pipelines"]:
        logging.info(f" {x}")

    logging.info("Loaded variables:")
    for x in config["env"]:
        logging.info(f" {x}")
    
    server.test(HandlerClass=HTTPRequestHandler, port=args.port)
