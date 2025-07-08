#!/usr/env python3
import logging
import http.server as server
import json

# The list of acceptable jobs for the orchestrator etc
config = {}

# The job queue to be processed
job_queue = []

# jobOrderTemplate = {
#     "name": ""
# }

# Generate a request as if from bitbucket or somewhere
def simulateWebhook():
    pass

# The entry point of orchestrator to handle an incoming job order - in case of push
def onIncomingJob(job: dict):
    scheduleJob(job)

# Called periodically to check all registered jobs who require pull-checks
# Att! Requires local state. Can be in-memory to begin with, but would need persistence at some point
def checkForPullChanges():
    # eventually scheduleJob(...)
    pass


# Result of either onIncomingJob or checkForPullChanges to schedule a job to be done
def scheduleJob(job: dict):
    job_queue.append(job)

def parse_path(path_raw: str) -> tuple[str, dict[str:str]]:
    """Tremendously naive path-path-of-URL-parser. Does e.g. not support multiple params with same key. URL-encoding? Schmurlencoding!"""
    splits = path_raw.split("?", 1)
    base = ""
    query = None
    params = {}

    if len(splits)==1:
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



agent_secret = "supersecret"
class HTTPRequestHandler(server.SimpleHTTPRequestHandler):
    """
    SimpleHTTPServer with added bonus of:

    - handle PUT requests
    - log headers in GET request
    """

    def do_GET(self):
        print("got GET")
        # server.SimpleHTTPRequestHandler.do_GET(self)
        # logging.warning(self.headers)

    def do_PUT(self):
        print("got PUT")

    def do_POST_webhook(self, params: dict) -> None:
        if "pipeline" not in params:
            self.send_error(400, "Invalid request")
            return

        if params["pipeline"] not in config["pipelines"]:
            self.send_error(404, "No such job")
            return

        scheduleJob({
            "env": {}, # Get from server/pipeline config?
            "pipeline": config["pipelines"][params["pipeline"]]
        })

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"")

    def do_POST_dequeue(self, params: dict) -> None:
        # Check for /webhook eller /dequeue
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
        print("got POST", self.path)
        (path, params) = parse_path(self.path)

        if path == "/dequeue":
            return self.do_POST_dequeue(params)
        elif path == "/webhook":
            return self.do_POST_webhook(params)


    
def validate_config(config: dict):
    return True

if __name__ == '__main__':
    with(open("./orchestrator-config.json", "r") as f):
        tmp_config = json.load(f)
        if validate_config(tmp_config):
            config = tmp_config

        print("config", config)

    server.test(HandlerClass=HTTPRequestHandler, port=8080)
