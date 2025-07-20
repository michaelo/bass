export type Config = {
    pipelinesEndpoint: string;
    tracesQueryEndpoint: string;
    logsQueryEndpoint: string;
    logsAnalyzeUrl: string;
    traceAnalyzeUrl: string;
}

export type Pipeline = {
    name: string;
}

type Span = {

}

type Log = {

}

type TraceID = string;
type SpanID = string;

type RequestResponse = {
    code: number;
    body?: any;
}

export async function request(method: "GET" | "POST" | "POST" | "DELETE", url: string, headers: { [k: string]: string } = {}): Promise<RequestResponse> {
    try {
        const response = await fetch(url, {method});
        const json = await response.json();
        return {
                code: response.status,
                body: json
            };
    } catch (error) {
        return {
            code: 0,
            body: `unhandled fetch error: ${error}`
        };
    }
}

export async function getPipelines(config: Config): Promise<{ [k: string]: Pipeline }> {
    return (await request("GET", config.pipelinesEndpoint)).body as { [k: string]: Pipeline };
}

function getSpansForTrace(traceId: TraceID): Span[] {
    return [];
}

function getLogsForTrace(): Log[] {
    return [];
}
