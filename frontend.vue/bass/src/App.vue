<script setup lang="ts">
import type { Config } from './api';

const props = defineProps(["config", "title", "pipelines", "pipelineInfo", "setPipeline"])
function traceUriFromId(config: Config, traceId: string) {
    traceId = traceId.padStart(32, "0");
    return config.traceAnalyzeUrl.replace("{TRACEID}", traceId);
};
function logUriFromId(config: Config, traceId: string) {
    traceId = traceId.padStart(32, "0");
    return config.logsAnalyzeUrl.replace("{TRACEID}", traceId);
};
</script>

<template>
  <div class="app">
      <h1>Build overview</h1>

      <nav>
          <h2>Pipelines</h2>
          <ul>
              <li v-for="(pipeline, pipelineName) in pipelines"><a @click="setPipeline(pipelineName)">{{ pipelineName }}</a></li>
              <!-- <li class="healthy"><a href="#1">Pipeline 1</a></li>
              <li class="unhealthy"><a href="#1">Pipeline 2</a></li> -->
          </ul>
      </nav>
      <section>
        <div v-if="pipelineInfo.value != null">
          <h2>{{ title.value }}</h2>
          <div class="result">
          <table class="result-matrix">
              <thead>
                  <tr>
                      <th>Build # / step</th>
                      <th v-for="field in pipelineInfo.value.allStepNames">{{ field }}</th>
                      <th>Conclusion</th>
                  </tr>
              </thead>
              <tbody>
                  <tr v-for="build in pipelineInfo.value.builds">
                      <th scope="row">
                          <span class="title">
                            {{ new Date(build.timeStarted * 1000).toLocaleString() }}
                            <a :href="logUriFromId(config, build.traceId)">L</a> | <a :href="traceUriFromId(config, build.traceId)">T</a></span>
                          <span class="by-title">{{ build.durationSeconds }}s</span>
                      </th>
                      <template v-for="step in pipelineInfo.value.allStepNames">
                        <td v-if="step in build.steps" :class="build.steps[step].status">{{ build.steps[step].durationSeconds }}s</td>
                        <td v-else> - </td>
                      </template>
                      <td :class="build.status">{{ build.status == "ok" ? "Success" : "Failed" }}</td>
                  </tr>
              </tbody>
              <tfoot>

              </tfoot>
          </table>
          </div>
          </div>
      </section>
  </div>
</template>

<style scoped>

</style>
