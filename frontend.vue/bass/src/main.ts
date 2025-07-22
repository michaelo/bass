import './assets/main.css'

import { createApp, ref, type Ref } from 'vue'
import App from './App.vue'
import { getPipelines, request, type Config, type Pipeline } from "./api";

const config: Config = {
    pipelinesEndpoint: "http://localhost:8080/pipelines",
    tracesQueryEndpoint: "http://localhost:3299/api/search",
    logsQueryEndpoint: "http://127.0.0.1:3100/loki/api/v1/query",
    logsAnalyzeUrl: "http://localhost:3000/explore?schemaVersion=1&panes=%7B%22t4g%22:%7B%22datasource%22:%22loki%22,%22queries%22:%5B%7B%22expr%22:%22%7Bservice_name%21%3D%5C%22%5C%22%7D%20%7C%20trace_id%20%3D%20%5C%22{TRACEID}%5C%22%22,%22refId%22:%22A%22,%22datasource%22:%7B%22type%22:%22loki%22,%22uid%22:%22loki%22%7D,%22editorMode%22:%22code%22,%22queryType%22:%22range%22,%22direction%22:%22backward%22%7D%5D,%22range%22:%7B%22from%22:%22now-7d%22,%22to%22:%22now%22%7D%7D%7D&orgId=1",
    traceAnalyzeUrl: "http://localhost:3000/explore?schemaVersion=1&panes=%7B%22zxa%22:%7B%22datasource%22:%22tempo%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22datasource%22:%7B%22type%22:%22tempo%22,%22uid%22:%22tempo%22%7D,%22queryType%22:%22traceql%22,%22limit%22:20,%22tableType%22:%22traces%22,%22metricsQueryType%22:%22range%22,%22query%22:%22{TRACEID}%22,%22filters%22:%5B%7B%22id%22:%22608ab610%22,%22operator%22:%22%3D%22,%22scope%22:%22span%22%7D%5D%7D%5D,%22range%22:%7B%22from%22:%22now-30d%22,%22to%22:%22now%22%7D%7D%7D&orgId=1"
};

const searchParams = new URLSearchParams(window.location.search);

const pipelines = await getPipelines(config);
const currentPipeline: Ref<null|Pipeline> = ref(null);
const pipelineInfo: Ref<null | PipelineInfo> = ref(null);
const title = ref("Select pipeline");

type Step = {
    // name: string;
    timeStarted: number;
    durationSeconds: number;
    status: "unknown"|"ok"|"error";
}

type Build = {
    name: string;
    traceId: string;
    timeStarted: number;
    durationSeconds: number;
    steps: { [k: string]: Step };
    status: "unknown"|"ok"|"error";
}

type PipelineInfo = {
    allStepNames: string[];
    builds: Build[];
    spec: Pipeline;
}

const zeroSpan = "0000000000000000";

async function getBuildsForPipeline(config: Config, name: string) : Promise<PipelineInfo> {
    // http://localhost:3200/api/search?q={rootServiceName=%22bass:pipeline:jobname%22}&spss=10
    // Look up traces w spans
    const serviceName = `bass:pipeline:${name}`;
    const nowUnix = Math.round(Date.now()/1000);
    // const query = `${config.tracesQueryEndpoint}?q={rootServiceName=%22${serviceName}%22}|select(span:status,span:name,span:parentID)&spss=10`;
    const query = `${config.tracesQueryEndpoint}?` + new URLSearchParams({
        q: `{rootServiceName="${serviceName}"}|select(span:status,span:name,span:parentID)`,
        spss: "100",
        limit: "100",
        start: String(nowUnix - 3600*72),
        end: String(nowUnix)
    });
    const traceResponse = await request("GET", query);

    // Nothing?
    if(traceResponse.code != 200 || !traceResponse.body) {
        return {
            allStepNames: [],
            builds: [],
            spec: {
                name
            }
        };
    }

    let result: PipelineInfo = {
        allStepNames: [],
        builds: [],
        spec: {
            name
        }
    };

    let stepNames: {[k:string]: number} = {};

    for(const trace of traceResponse.body.traces) {
        const build: Build = {
            name: trace.traceID,
            traceId: trace.traceID,
            timeStarted: Math.round(trace.startTimeUnixNano / 1000000000),
            durationSeconds: trace.durationMs / 1000,
            status: "unknown",
            steps: {}
        };

        for(const span of trace.spanSet.spans) {
            const parentId = (span.attributes as any[]).find(el => el.key == "span:parentID").value.stringValue;
            if (parentId == zeroSpan) {
                build.status = (span.attributes as any[]).find(el => el.key == "status").value.stringValue;
                continue;
            }

            if (!stepNames[span.name] || span.startTimeUnixNano < stepNames[span.name]) {
                stepNames[span.name] = span.startTimeUnixNano;
            }
            
            build.steps[span.name] = {
                durationSeconds: Math.round(span.durationNanos	/ 10000000) / 100,
                status: (span.attributes as any[]).find(el => el.key == "status").value.stringValue,
                timeStarted: span.startTimeUnixNano	/ 1000000000,
            };
        }

        result.builds.push(build);
    }

    result.allStepNames = Object.getOwnPropertyNames(stepNames)
        .map(el => [stepNames[el], el])
        .toSorted((a, b) => a[0] > b[0])
        .map(el => el[1]);

    return result;
}

function setPipeline(name: string) {
    window.history.pushState(null, null, "?pipeline=" + name);
    title.value = name;
    currentPipeline.value = pipelines[name];

    // TODO: get build/trace data
    getBuildsForPipeline(config, name).then(result => {
        pipelineInfo.value = result;
    });
}

const pipeline = searchParams.get("pipeline");
if(pipeline) {
    setPipeline(pipeline);
}

createApp(App, {
    config,
    pipelines,
    title,
    setPipeline,
    pipelineInfo
}).mount('#app');
