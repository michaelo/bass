import './assets/main.css'

import { createApp, ref, type Ref } from 'vue'
import App from './App.vue'
import { getPipelines, request, type Config, type Pipeline } from "./api";

const config: Config = {
    pipelinesEndpoint: "http://localhost:8080/pipelines",
    tracesQueryEndpoint: "http://localhost:3299/api/search",
    logsQueryEndpoint: "http://127.0.0.1:3100/loki/api/v1/query",
};

const pipelines = await getPipelines(config);
const currentPipeline: Ref<null|Pipeline> = ref(null);
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

const pipelineBuilds = ref([])

type TempoTraceResponse = {
    traces: {
        traceID: string;
    }[];
}

const zeroSpan = "0000000000000000"


async function getBuildsForPipeline(config: Config, name: string) : Promise<PipelineInfo> {
    // http://localhost:3200/api/search?q={rootServiceName=%22bass:pipeline:jobname%22}&spss=10
    // Look up traces w spans
    const serviceName = `bass:pipeline:${name}`;
    const nowUnix = Math.round(Date.now()/1000);
    // const query = `${config.tracesQueryEndpoint}?q={rootServiceName=%22${serviceName}%22}|select(span:status,span:name,span:parentID)&spss=10`;
    const query = `${config.tracesQueryEndpoint}?` + new URLSearchParams({
        q: `{rootServiceName="${serviceName}"}|select(span:status,span:name,span:parentID)`,
        spss: "10",
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
                name: name
            }
        };
    }

    let result: PipelineInfo = {
        allStepNames: [],
        builds: [],
        spec: {
            name: name
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

            if(!stepNames[span.name]) {
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

    result.allStepNames = Object.getOwnPropertyNames(stepNames).map(el => [stepNames[el], el]).toSorted((a, b) => a[0] > b[0]).map(el => el[1]);

    return result;
}

const pipelineInfo: Ref<null | PipelineInfo> = ref(null);


// {
//         "spec": currentPipeline.value,
//         // TODO: be created from all the steps of all builds
//         "allStepNames": ["step1", "step2", "step3"],
//         "builds": [
//             {name: "#001", traceId: "123123123", timeStarted: 0, durationSeconds: 10, status: "ok", steps: {
//                 "step1": {
//                     "timeStarted": 0,
//                     "durationSeconds": 3,
//                     status: "ok"
//                 },
//                 "step2": {
//                     "timeStarted": 1,
//                     "durationSeconds": 6,
//                     status: "ok"
//                 }
//             }},

//             {name: "#002", traceId: "123123121", timeStarted: 2, durationSeconds: 8, status: "error", steps: {
//                 "step1": {
//                     "timeStarted": 0,
//                     "durationSeconds": 3,
//                     status: "ok"
//                 },
//                 "step3": {
//                     "timeStarted": 3,
//                     "durationSeconds": 6,
//                     status: "error"
//                 }
//             }}
//         ]
//     } as PipelineInfo

createApp(App, {
    pipelines,
    currentPipeline,
    title,
    setPipeline: (name: string) => {
        title.value = name;
        currentPipeline.value = pipelines[name];

        // TODO: get build/trace data
        getBuildsForPipeline(config, name).then(result => {
            pipelineInfo.value = result;
        });
    },
    pipelineInfo
}).mount('#app')
