import { createApp } from "vue";

import App from "./App.vue";
import ShowcasePage from "./ShowcasePage.vue";
import "./styles.css";

const isPublicWorkbench = import.meta.env.MODE === "showcase"
  && window.location.pathname.replace(/\/$/, "") === "/workbench";

createApp(import.meta.env.MODE === "showcase" && !isPublicWorkbench ? ShowcasePage : App).mount("#app");
