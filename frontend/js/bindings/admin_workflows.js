function bindAdminWorkflowEditorEvents() {
  $("#adminWorkflowSelect").onchange = async () => loadAdminWorkflow($("#adminWorkflowSelect").value);
  $("#newWorkflowBtn").onclick = newWorkflow;
  $("#saveWorkflowBtn").onclick = saveAdminWorkflow;
  $("#deleteWorkflowBtn").onclick = deleteAdminWorkflow;

  $("#wfAddStepBtn").onclick = () => {
    wfStepsDraft = wfStepsDraft || [];
    wfStepsDraft.push({ step_key: "admin", assignee_kind: "role", assignee_value: "admin" });
    renderWfStepsEditor(wfStepsDraft);
  };

  $("#wfShowJsonBtn").onclick = () => {
    const det = $("#wfStepsJsonDetails");
    if (!det) return;
    det.hidden = !det.hidden;
    if (!det.hidden) {
      $("#wfStepsJson").value = JSON.stringify(readWfStepsEditor(), null, 2);
    }
  };

  $("#wfApplyJsonBtn").onclick = () => {
    $("#wfMsg").textContent = "";
    let arr;
    try {
      arr = JSON.parse($("#wfStepsJson").value || "[]");
    } catch {
      $("#wfMsg").textContent = "JSON 解析失败";
      return;
    }
    if (!Array.isArray(arr)) {
      $("#wfMsg").textContent = "JSON 必须是数组";
      return;
    }
    renderWfStepsEditor(arr);
  };

  if (typeof bindWfStepsGraphEditorEvents === "function") {
    bindWfStepsGraphEditorEvents();
  }
}
