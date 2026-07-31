import { createApp } from "vue";

import App from "./App.vue";
import ShowcasePage from "./ShowcasePage.vue";
import "./styles.css";

createApp(import.meta.env.MODE === "showcase" ? ShowcasePage : App).mount("#app");
