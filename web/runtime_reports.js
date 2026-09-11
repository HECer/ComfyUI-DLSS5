import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "DLSS.RuntimeReports",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (!["DLSS5RuntimeStatus", "DLSS5RuntimeSetup"].includes(nodeData.name)) return;
        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = onExecuted?.apply(this, arguments);
            if (!this.runtimeReport) {
                const element = document.createElement("textarea");
                element.readOnly = true;
                element.setAttribute?.("aria-label", "DLSS runtime report");
                element.style.width = "100%";
                element.style.height = "100%";
                element.style.boxSizing = "border-box";
                this.runtimeReport = this.addDOMWidget("runtime_report", "text", element, {
                    serialize: false,
                });
                this.setSize([this.size[0], Math.max(this.size[1], 260)]);
            }
            this.runtimeReport.element.value = (message.text ?? []).join("\n");
            this.setDirtyCanvas(true, true);
            return result;
        };
    },
});
