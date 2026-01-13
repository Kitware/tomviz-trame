window.tomviz = {
  install(app) {
    app.component("tomviz-dockview-tab", {
      props: ["params"],
      setup(props) {
        const trame = window.Vue.inject("trame");
        const title = window.Vue.ref("3D View");
        const { params } = window.Vue.toRefs(props);
        return { title, params, trame };
      },
      template: `
        <trame-dataclass :instance="params.params.viewState" v-slot="{ dataclass }">
          <div class="d-flex align-center text-subtitle-1 text-no-wrap">
          <v-icon icon="mdi-stop" :color="dataclass.color" />
          {{ title }}
          <v-btn icon="mdi-trash-can-outline" variant="plain" density="compact" size="small" class="ml-2" @click="trame.trigger('remove_view', [dataclass._id])"/>
        </trame-dataclass>`,
    });
  },
};
