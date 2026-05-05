(function () {
  const REMOTE_BUNDLE_URL =
    "https://cdn.jsdelivr.net/gh/logspace-ai/langflow-embedded-chat@v1.0.8/dist/build/static/js/bundle.min.js";

  let bundleLoadPromise;

  function loadRemoteBundle() {
    if (bundleLoadPromise) return bundleLoadPromise;

    bundleLoadPromise = new Promise((resolve, reject) => {
      const existing = document.querySelector(
        `script[data-agentcore-widget="remote-bundle"]`,
      );

      if (existing) {
        existing.addEventListener("load", () => resolve(), { once: true });
        existing.addEventListener(
          "error",
          () => reject(new Error("Failed to load remote widget bundle.")),
          { once: true },
        );
        return;
      }

      const script = document.createElement("script");
      script.src = REMOTE_BUNDLE_URL;
      script.async = true;
      script.defer = true;
      script.setAttribute("data-agentcore-widget", "remote-bundle");
      script.addEventListener("load", () => resolve(), { once: true });
      script.addEventListener(
        "error",
        () => reject(new Error("Failed to load remote widget bundle.")),
        { once: true },
      );
      document.head.appendChild(script);
    });

    return bundleLoadPromise;
  }

  class AgentcoreChatElement extends HTMLElement {
    static get observedAttributes() {
      return [
        "window_title",
        "agent_id",
        "agentId",
        "flow_id",
        "flowId",
        "host_url",
        "hostUrl",
        "api_key",
        "apiKey",
      ];
    }

    connectedCallback() {
      this.mount();
    }

    attributeChangedCallback(name, _oldValue, newValue) {
      if (!this._innerWidget) return;
      if (newValue === null) {
        this._innerWidget.removeAttribute(name);
      } else {
        this._innerWidget.setAttribute(name, newValue);
      }

      // Keep agent/flow aliases in sync for runtimes that read one or the other.
      if (name === "agent_id" || name === "agentId") {
        const val = newValue || "";
        if (val) {
          this._innerWidget.setAttribute("flow_id", val);
          this._innerWidget.setAttribute("flowId", val);
        }
      }
      if (name === "flow_id" || name === "flowId") {
        const val = newValue || "";
        if (val) {
          this._innerWidget.setAttribute("agent_id", val);
          this._innerWidget.setAttribute("agentId", val);
        }
      }
    }

    async mount() {
      try {
        await loadRemoteBundle();
      } catch (error) {
        console.error("[agentcore-widget]", error);
      }

      if (this._innerWidget) return;

      const inner = document.createElement("langflow-chat");
      for (const attr of this.attributes) {
        inner.setAttribute(attr.name, attr.value);
      }

      const idFromAttrs =
        this.getAttribute("flow_id") ||
        this.getAttribute("flowId") ||
        this.getAttribute("agent_id") ||
        this.getAttribute("agentId");

      if (idFromAttrs) {
        inner.setAttribute("flow_id", idFromAttrs);
        inner.setAttribute("flowId", idFromAttrs);
        inner.setAttribute("agent_id", idFromAttrs);
        inner.setAttribute("agentId", idFromAttrs);
      }

      this._innerWidget = inner;
      this.appendChild(inner);
    }
  }

  if (!customElements.get("agentcore-chat")) {
    customElements.define("agentcore-chat", AgentcoreChatElement);
  }
})();
